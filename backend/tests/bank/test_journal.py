from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.auth.deps import current_user
from app.main import app
from app.models import Application, ApplicationEvent, Decision, User


def test_client_cannot_read_bank_journal():
    app.dependency_overrides[current_user] = lambda: User(
        id=uuid4(), role="CLIENT", login="client", full_name="Клиент", password_hash=""
    )
    try:
        response = TestClient(app).get("/api/v1/bank/applications")
        assert response.status_code == 403, response.text
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_journal_requires_authentication():
    assert TestClient(app).get("/api/v1/bank/applications").status_code == 401


def test_journal_nullable_fields_are_required():
    schema = app.openapi()["components"]["schemas"]["BankListItem"]
    assert set(schema["required"]) == set(schema["properties"])
    for field in ("route_reason", "waiting_since"):
        assert {"type": "null"} in schema["properties"][field]["anyOf"]


@pytest.mark.parametrize("query,field", [("state=FOO", "state"), ("size=101", "size")])
def test_journal_validates_filter(query, field):
    app.dependency_overrides[current_user] = lambda: User(
        id=uuid4(), role="UNDERWRITER", login="bank", full_name="Банк", password_hash=""
    )
    try:
        response = TestClient(app).get(f"/api/v1/bank/applications?{query}")
        assert response.status_code == 422, response.text
        assert field in response.json()["error"]["details"]["fields"]
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_journal_pagination_filter_and_constant_query_count(
    bank_context, pipeline_factory, run_persona
):
    client, _ = bank_context
    ids = [run_persona("ip_good")]
    engine = pipeline_factory.kw["bind"]

    def page_with_count(page, size):
        from app.bank.journal import list_applications

        statements = []

        def count(*args):
            statements.append(args[2])

        event.listen(engine, "before_cursor_execute", count)
        try:
            with pipeline_factory() as session:
                result = list_applications(session, None, page, size)
        finally:
            event.remove(engine, "before_cursor_execute", count)
        assert len(statements) <= 3
        return result

    first = client.get("/api/v1/bank/applications")
    assert first.status_code == 200, first.text
    assert first.json()["items"][0]["waiting_since"] is None
    assert first.json()["items"][0]["grade"] == "A"
    assert first.json()["items"][0]["route_reason"] is None
    assert page_with_count(1, 20).total == 1
    ids.extend(run_persona("ooo_border") for _ in range(10))
    ids.extend(run_persona("ip_bad") for _ in range(10))
    ids.extend(run_persona("ip_good") for _ in range(9))

    page = client.get("/api/v1/bank/applications?page=2&size=20").json()
    assert (len(page["items"]), page["total"], page["page"], page["size"]) == (
        10,
        30,
        2,
        20,
    )
    with pipeline_factory() as session:
        expected = list(
            session.scalars(
                select(Application.id).order_by(
                    Application.updated_at.desc(), Application.id
                )
            )
        )
    assert [item["id"] for item in page["items"]] == list(map(str, expected[20:]))
    assert page_with_count(2, 20).total == 30
    empty = client.get("/api/v1/bank/applications?page=3&size=20").json()
    assert empty == {"items": [], "total": 30, "page": 3, "size": 20}
    manual = client.get("/api/v1/bank/applications?state=MANUAL_REVIEW").json()
    assert manual["total"] == len(manual["items"]) == 10
    assert all(item["state"] == "MANUAL_REVIEW" for item in manual["items"])
    with pipeline_factory() as session:
        entries = {
            str(e.application_id): e.created_at.isoformat()
            for e in session.scalars(
                select(ApplicationEvent).where(
                    ApplicationEvent.to_state == "MANUAL_REVIEW"
                )
            )
        }
    for item in manual["items"]:
        assert item["route_reason"] == "GRADE_C"
        assert item["waiting_since"] == entries[item["id"]]


def test_empty_journal(bank_context):
    client, _ = bank_context
    response = client.get("/api/v1/bank/applications")
    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "total": 0, "page": 1, "size": 20}


@pytest.mark.parametrize(
    "page",
    [
        135637824071393762,
        135637824071393763,
        15052842692487972973998667464704,
    ],
)
@pytest.mark.parametrize(
    "state,total", [(None, 2), ("MANUAL_REVIEW", 1), ("ENRICHMENT", 0)]
)
def test_journal_huge_page_returns_empty_with_filtered_total(
    bank_context, run_persona, page, state, total
):
    client, _ = bank_context
    run_persona("ooo_border")
    run_persona("ip_good")
    params = {} if state is None else {"state": state}
    first = client.get("/api/v1/bank/applications", params=params)
    assert first.status_code == 200, first.text
    assert first.json()["total"] == total
    response = client.get(
        "/api/v1/bank/applications", params={**params, "page": page, "size": 68}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "total": total, "page": page, "size": 68}


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/bank/applications",
        "/api/v1/underwriting/queue",
    ],
)
@pytest.mark.parametrize("route", ["FOO", "", None, 123, {"code": "GRADE_C"}])
def test_invalid_manual_entry_route_falls_back_to_auto(
    bank_context, pipeline_factory, run_persona, path, route
):
    client, _ = bank_context
    identity = run_persona("ooo_border")
    with pipeline_factory.begin() as session:
        entry = session.scalar(
            select(ApplicationEvent).where(
                ApplicationEvent.application_id == identity,
                ApplicationEvent.to_state == "MANUAL_REVIEW",
            )
        )
        entry.payload = {"route_reason": route}
    response = client.get(path)
    assert response.status_code == 200, response.text
    body = response.json()
    if path == "/api/v1/bank/applications":
        item = body["items"][0]
    else:
        item = body[0]
    assert item["route_reason"] == "GRADE_C"


def test_latest_auto_and_manual_entry_override(
    bank_context, pipeline_factory, run_persona
):
    client, _ = bank_context
    identity = run_persona("ooo_border")
    now = datetime.now(UTC)
    with pipeline_factory.begin() as session:
        application = session.get(Application, identity)
        amount, term = application.amount, application.term_months
        for kind, grade, at in (
            ("AUTO", "B", now + timedelta(days=1)),
            ("MANUAL", "D", now + timedelta(days=2)),
        ):
            session.add(
                Decision(
                    application_id=identity,
                    kind=kind,
                    outcome="MANUAL" if kind == "AUTO" else "DECLINE",
                    route_reason="NO_AUTO_CONSENT",
                    grade=grade,
                    score=60,
                    factors=[],
                    rules_fired=[],
                    internal_reasons=[],
                    inputs_snapshot={},
                    config_version=1,
                    created_at=at,
                )
            )
        entry = session.scalar(
            select(ApplicationEvent).where(
                ApplicationEvent.application_id == identity,
                ApplicationEvent.to_state == "MANUAL_REVIEW",
            )
        )
        entry.payload = {"route_reason": "INFO_RESPONSE"}
    item = client.get("/api/v1/bank/applications").json()["items"][0]
    assert item["grade"] == "B"
    assert item["route_reason"] == "INFO_RESPONSE"
    response = client.post(
        f"/api/v1/underwriting/{identity}/decision",
        json={
            "outcome": "APPROVE",
            "amount": amount,
            "term_months": term,
            "comment": "Проверены условия и документы",
        },
    )
    assert response.status_code == 200, response.text
    item = client.get("/api/v1/bank/applications").json()["items"][0]
    assert item["state"] == "OFFER_ISSUED"
    assert item["grade"] == "B"
    assert item["route_reason"] == "NO_AUTO_CONSENT"
    assert item["waiting_since"] is None
