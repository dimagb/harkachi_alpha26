"""Application CRUD through the authenticated HTTP boundary."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session
from test_auth import PERSONAS, api_client

from app.models import Application, ApplicationEvent, Company, User


@contextmanager
def application_context(engine):
    # Service commits stay inside a transaction rolled back by the test.
    with engine.connect() as connection:
        transaction = connection.begin()
        sequence = connection.scalar(
            text("SELECT pg_get_serial_sequence('application', 'number')")
        )
        last_value, is_called = connection.execute(
            text(f"SELECT last_value, is_called FROM {sequence}")
        ).one()
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            with api_client(session) as client:
                yield session, client
        transaction.rollback()
        # PostgreSQL sequences survive rollback. Restore this isolated test DB's
        # sequence too, so these tests do not change the migrated seed fixture.
        connection.execute(
            text("SELECT setval(CAST(:sequence AS regclass), :value, :called)"),
            {"sequence": sequence, "value": last_value, "called": is_called},
        )
        connection.commit()


@pytest.fixture
def application_client(migrated_database):
    with application_context(migrated_database[0]) as context:
        yield context


def authenticate(client, login="ip_good"):
    response = client.post(
        "/auth/login", json={"login": login, "password": "b03-test-password"}
    )
    assert response.status_code == 200, response.text
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"


def create_body(session, persona=None):
    persona = PERSONAS[0] if persona is None else persona
    company = session.scalar(select(Company).where(Company.inn == persona["inn"]))
    demo = persona["demo"]["app"]
    return {
        "company_id": str(company.id),
        "product_code": demo["product"],
        "amount": demo["amount"],
        "term_months": demo["term"],
        "purpose": demo["purpose"],
        "declared_revenue_year": demo["declared_revenue_year"],
        **({"purpose_text": demo["purpose_text"]} if "purpose_text" in demo else {}),
    }


def created(session, client, **changes):
    authenticate(client)
    body = {**create_body(session), **changes}
    response = client.post("/applications", json=body)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    "persona", PERSONAS, ids=lambda persona: persona["users"][0]["login"]
)
def test_each_persona_creates_draft(application_client, persona):
    session, client = application_client
    authenticate(client, persona["users"][0]["login"])
    body = create_body(session, persona)
    response = client.post("/applications", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["state"] == "DRAFT"
    assert data["number"] >= 1001
    assert data["version"] == 1
    application = session.get(Application, UUID(data["id"]))
    user = session.scalar(
        select(User).where(User.login == persona["users"][0]["login"])
    )
    assert application.created_by == user.id
    events = session.scalars(
        select(ApplicationEvent).where(
            ApplicationEvent.application_id == application.id
        )
    ).all()
    assert len(events) == 1
    assert (
        events[0].from_state,
        events[0].to_state,
        events[0].actor_type,
        events[0].actor_id,
    ) == (None, "DRAFT", "CLIENT", user.id)
    assert events[0].event_type == "STATE_CHANGED"
    assert events[0].payload == {}
    read = client.get(f"/applications/{data['id']}")
    assert read.status_code == 200
    assert read.json() == data
    assert {
        "decision",
        "risk_flag",
        "factors",
        "internal_reasons",
        "rules_fired",
        "inputs_snapshot",
    }.isdisjoint(data)
    assert all(
        data[key] is None
        for key in ("offer", "client_reason", "info_request", "objection")
    )


@pytest.mark.parametrize("company", ["foreign", "abc", "missing"])
def test_creation_company_not_found(application_client, company):
    session, client = application_client
    authenticate(client)
    body = create_body(session)
    body["company_id"] = (
        create_body(session, PERSONAS[1])["company_id"]
        if company == "foreign"
        else str(uuid4())
        if company == "missing"
        else "abc"
    )
    response = client.post("/applications", json=body)
    assert response.status_code == 404, response.text
    assert response.json()["error"]["message"] == "Компания не найдена"


@pytest.mark.parametrize(
    "changes,field,text",
    [
        ({"amount": 299999}, "amount", "Сумма от 300 000 до 5 000 000 ₽"),
        ({"term_months": 100}, "term_months", "Срок от 6 до 36 мес."),
        (
            {
                "product_code": "WORKING_CAPITAL",
                "amount": 1500000,
                "purpose": "EQUIPMENT",
            },
            "purpose",
            "Эта цель недоступна для выбранного продукта",
        ),
        ({"purpose": "OTHER"}, "purpose_text", "Укажите цель кредита"),
    ],
)
def test_creation_validates_terms_and_purpose(application_client, changes, field, text):
    session, client = application_client
    authenticate(client)
    response = client.post("/applications", json={**create_body(session), **changes})
    assert response.status_code == 422, response.text
    assert response.json()["error"]["details"]["fields"][field] == text
    assert session.scalar(select(func.count()).select_from(Application)) == 0


def test_patch_versions_and_no_events(application_client):
    session, client = application_client
    data = created(session, client)
    path = f"/applications/{data['id']}"
    response = client.patch(path, headers={"If-Match": "1"}, json={"amount": 1600000})
    assert response.status_code == 200, response.text
    assert (response.json()["version"], response.json()["amount"]) == (2, 1600000)
    assert session.scalar(select(func.count()).select_from(ApplicationEvent)) == 1
    stale = client.patch(path, headers={"If-Match": "1"}, json={"amount": 1700000})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "CONFLICT_VERSION"
    assert (
        stale.json()["error"]["message"]
        == "Заявку изменили в другом окне — обновите страницу"
    )
    assert client.patch(path, json={"amount": 1700000}).status_code == 422


def test_patch_merges_other_purpose_and_clears_text(application_client):
    session, client = application_client
    data = created(
        session, client, purpose="OTHER", purpose_text="Покупка мебели для офиса"
    )
    path = f"/applications/{data['id']}"
    response = client.patch(path, headers={"If-Match": "1"}, json={"purpose": "OTHER"})
    assert response.status_code == 200, response.text
    assert response.json()["purpose_text"] == "Покупка мебели для офиса"
    response = client.patch(
        path,
        headers={"If-Match": str(response.json()["version"])},
        json={"purpose_text": None},
    )
    assert response.status_code == 422
    assert (
        response.json()["error"]["details"]["fields"]["purpose_text"]
        == "Укажите цель кредита"
    )
    response = client.patch(
        path,
        headers={"If-Match": str(session.get(Application, UUID(data["id"])).version)},
        json={"purpose": "WORKING_CAPITAL"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["purpose_text"] is None


@pytest.mark.parametrize(
    "changes,field",
    [
        ({"purpose": "OTHER"}, "purpose_text"),
        ({"product_code": "WORKING_CAPITAL"}, "amount"),
        ({"amount": None}, "amount"),
    ],
)
def test_patch_validates_complete_result(application_client, changes, field):
    session, client = application_client
    data = created(session, client, amount=300000)
    response = client.patch(
        f"/applications/{data['id']}", headers={"If-Match": "1"}, json=changes
    )
    assert response.status_code == 422, response.text
    assert field in response.json()["error"]["details"]["fields"]
    assert client.get(f"/applications/{data['id']}").json() == data


def test_patch_check_order_and_foreign_application(application_client):
    from app.applications.state_machine import transition

    session, client = application_client
    data = created(session, client)
    application = session.get(Application, UUID(data["id"]))
    transition(
        session,
        application,
        "SUBMITTED",
        actor_type="CLIENT",
        actor_id=application.created_by,
    )
    session.commit()
    path = f"/applications/{data['id']}"
    assert (
        client.patch(path, headers={"If-Match": "1"}, json={}).json()["error"]["code"]
        == "CONFLICT_VERSION"
    )
    response = client.patch(
        path, headers={"If-Match": str(application.version)}, json={}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_TRANSITION"
    authenticate(client, PERSONAS[1]["users"][0]["login"])
    for missing in (data["id"], str(uuid4())):
        assert client.get(f"/applications/{missing}").status_code == 404
        response = client.patch(
            f"/applications/{missing}", headers={"If-Match": "0"}, json={}
        )
        assert response.status_code == 404
        assert response.json()["error"]["message"] == "Заявка не найдена"


def test_list_order_company_access_and_multiple_drafts(application_client):
    session, client = application_client
    first, second = created(session, client), created(session, client)
    now = datetime.now(UTC)
    for data, at in [(first, now - timedelta(days=1)), (second, now)]:
        session.execute(
            update(Application)
            .where(Application.id == UUID(data["id"]))
            .values(created_at=at)
        )
    session.commit()
    response = client.get("/applications", params={"company_id": first["company_id"]})
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [second["id"], first["id"]]
    assert set(response.json()[0]) == {
        "id",
        "number",
        "state",
        "stage",
        "product_code",
        "amount",
        "awaiting_signature",
        "updated_at",
    }
    session.execute(update(Application).values(created_at=now))
    session.commit()
    assert [
        item["id"]
        for item in client.get(
            "/applications", params={"company_id": first["company_id"]}
        ).json()
    ] == [second["id"], first["id"]]
    assert (
        client.get(
            "/applications",
            params={"company_id": create_body(session, PERSONAS[1])["company_id"]},
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/applications"),
        ("PATCH", "/applications/{id}"),
        ("GET", "/applications"),
        ("GET", "/applications/{id}"),
    ],
)
def test_underwriter_cannot_use_client_applications(application_client, method, path):
    session, client = application_client
    authenticate(client, "underwriter")
    response = client.request(
        method,
        path.format(id=uuid4()),
        headers={"If-Match": "1"},
        params={"company_id": str(uuid4())},
        json=create_body(session) if method == "POST" else {},
    )
    assert response.status_code == 403, response.text


def test_unknown_login_still_verifies_password(application_client, monkeypatch):
    from app.auth import service

    _, client = application_client
    real_verify = service.verify_password
    calls = []

    def verify(password, hashed):
        calls.append((password, hashed))
        return real_verify(password, hashed)

    monkeypatch.setattr(service, "verify_password", verify)
    response = client.post(
        "/auth/login", json={"login": "unknown", "password": "wrong"}
    )
    assert response.status_code == 401
    assert len(calls) == 1
    assert calls[0][0] == "wrong"


def test_cached_settings_are_shared():
    from app.auth.tokens import settings
    from app.config import get_settings

    assert settings is get_settings()


def test_patch_database_race_returns_version_conflict(application_client):
    session, client = application_client
    data = created(session, client)
    application = session.get(Application, UUID(data["id"]))
    # A competing write advances the database version after this object was read.
    session.execute(
        update(Application)
        .where(Application.id == application.id)
        .values(version=Application.version + 1)
        .execution_options(synchronize_session=False)
    )
    assert application.version == 1
    response = client.patch(
        f"/applications/{application.id}",
        headers={"If-Match": "1"},
        json={"amount": 1700000},
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "CONFLICT_VERSION"
    assert (
        response.json()["error"]["message"]
        == "Заявку изменили в другом окне — обновите страницу"
    )
    assert session.get(Application, UUID(data["id"])).amount == data["amount"]
    assert session.scalar(select(func.count()).select_from(ApplicationEvent)) == 1


def test_patch_explicit_null_and_empty_patch(application_client):
    session, client = application_client
    data = created(session, client, purpose_text="Покупка мебели для офиса")
    path = f"/applications/{data['id']}"
    response = client.patch(
        path, headers={"If-Match": "1"}, json={"purpose_text": None}
    )
    assert response.status_code == 200, response.text
    assert response.json()["purpose_text"] is None
    assert response.json()["version"] == 2
    response = client.patch(path, headers={"If-Match": "2"}, json={})
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 3


def test_patch_cannot_change_state(application_client):
    session, client = application_client
    data = created(session, client)
    response = client.patch(
        f"/applications/{data['id']}",
        headers={"If-Match": "1"},
        json={"state": "SUBMITTED"},
    )
    assert response.status_code == 422, response.text
    assert session.get(Application, UUID(data["id"])).state == "DRAFT"
    assert session.scalar(select(func.count()).select_from(ApplicationEvent)) == 1
