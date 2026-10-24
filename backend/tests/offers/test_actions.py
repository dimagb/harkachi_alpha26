from datetime import UTC, datetime, timedelta

import pytest
from pipeline.test_pipeline import drain, providers_for, submit_persona
from sqlalchemy import select
from test_application_offer_view import client_for, completed

from app.models import (
    Application,
    ApplicationEvent,
    Decision,
    Job,
    Offer,
    ReasonCatalog,
)


def path(app_id, action=""):
    return f"/api/v1/applications/{app_id}" + (f"/{action}" if action else "")


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


@pytest.mark.parametrize("code", ["ip_good", "ooo_load"])
def test_accept_and_repeat(actions_factory, persona_data, code):
    app_id, _ = completed(actions_factory, persona_data, code)
    with client_for(actions_factory, code) as client:
        before = client.get(path(app_id)).json()
        response = client.post(path(app_id, "offer/accept"), json={"offer_version": 1})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["state"] == "SIGNING"
        assert data["offer"]["status"] == "ACCEPTED"
        assert data["version"] == before["version"] + 1
        assert data["allowed_actions"] == ["SIGN", "WITHDRAW"]
        assert data["parties"] == before["parties"]
        assert all(p["is_me"] for p in data["parties"])
        assert_error(
            client.post(path(app_id, "offer/accept"), json={"offer_version": 1}),
            409,
            "INVALID_TRANSITION",
        )
    with actions_factory() as session:
        event = session.scalar(
            select(ApplicationEvent).where(
                ApplicationEvent.application_id == app_id,
                ApplicationEvent.event_type == "OFFER_ACCEPTED",
            )
        )
        assert event.actor_type == "CLIENT"
        assert event.actor_id == session.get(Application, app_id).created_by
        assert event.payload == {"offer_id": data["offer"]["id"], "version": 1}
        assert event.reason_code is None


@pytest.mark.parametrize(
    "problem,code",
    [
        ("version", "CONFLICT_VERSION"),
        ("date", "OFFER_EXPIRED"),
        ("status", "OFFER_EXPIRED"),
    ],
)
def test_accept_invalid_offer_is_atomic(actions_factory, persona_data, problem, code):
    app_id, _ = completed(actions_factory, persona_data, "ip_good")
    with actions_factory.begin() as session:
        application = session.get(Application, app_id)
        version = application.version
        offer = session.get(Offer, application.current_offer_id)
        if problem == "date":
            offer.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        if problem == "status":
            offer.status = "EXPIRED"
    with client_for(actions_factory, "ip_good") as client:
        response = client.post(
            path(app_id, "offer/accept"),
            json={"offer_version": 0 if problem == "version" else 1},
        )
    assert_error(response, 409, code)
    with actions_factory() as session:
        application = session.get(Application, app_id)
        assert application.state == "OFFER_ISSUED"
        assert application.version == version
        assert session.get(Offer, application.current_offer_id).status == (
            "EXPIRED" if problem == "status" else "ACTIVE"
        )


@pytest.mark.parametrize("action", ["offer/accept", "offer/reject", "withdraw"])
def test_accountant_cannot_act_after_submission(actions_factory, persona_data, action):
    app_id, _ = completed(actions_factory, persona_data, "ooo_load")
    with client_for(actions_factory, "ooo_load_accountant") as client:
        assert_error(
            client.post(
                path(app_id, action),
                **({"json": {"offer_version": 1}} if action == "offer/accept" else {}),
            ),
            403,
            "SIGN_NOT_ALLOWED",
        )


def test_reject(actions_factory, persona_data):
    app_id, _ = completed(actions_factory, persona_data, "ip_good")
    with client_for(actions_factory, "ip_good") as client:
        response = client.post(path(app_id, "offer/reject"))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["state"] == "WITHDRAWN"
    assert data["stage"]["what_happens"] == "Вы отказались от предложения"
    assert data["offer"]["status"] == "REJECTED"
    assert data["client_reason"] == {
        "code": "CLIENT_REJECTED_OFFER",
        "category": None,
        "text": "Вы отказались от предложения банка",
        "action": "Можно подать новую заявку",
        "retry_after": None,
    }


@pytest.mark.parametrize(
    "state",
    [
        "DRAFT",
        "SUBMITTED",
        "VALIDATION",
        "ENRICHMENT",
        "ASSESSMENT",
        "INFO_REQUESTED",
        "MANUAL_REVIEW",
        "OFFER_ISSUED",
        "SIGNING",
    ],
)
def test_withdraw_before_signing(actions_factory, persona_data, state):
    persona = next(p for p in persona_data["personas"] if p["code"] == "ooo_load")
    app_id = submit_persona(actions_factory, persona)
    with actions_factory.begin() as session:
        application = session.get(Application, app_id)
        application.state = state
        session.flush()
        version = application.version
    login = "ooo_load_accountant" if state == "DRAFT" else "ooo_load"
    with client_for(actions_factory, login) as client:
        response = client.post(path(app_id, "withdraw"))
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "WITHDRAWN"
    assert response.json()["version"] == version + 1
    assert response.json()["client_reason"]["code"] == "CLIENT_WITHDREW"
    assert response.json()["client_reason"]["category"] is None
    drain(actions_factory, providers_for(persona_data), persona_data)
    with actions_factory() as session:
        assert session.get(Application, app_id).state == "WITHDRAWN"
        assert all(
            j.status == "DONE"
            for j in session.scalars(select(Job).where(Job.application_id == app_id))
        )


def test_withdraw_rejects_accepted_offer(actions_factory, persona_data):
    app_id, _ = completed(actions_factory, persona_data, "ip_good")
    with client_for(actions_factory, "ip_good") as client:
        assert (
            client.post(
                path(app_id, "offer/accept"), json={"offer_version": 1}
            ).status_code
            == 200
        )
        response = client.post(path(app_id, "withdraw"))
    assert response.status_code == 200, response.text
    assert response.json()["offer"]["status"] == "REJECTED"


@pytest.mark.parametrize(
    "state", ["DECLINED", "SIGNED", "DISBURSED", "WITHDRAWN", "EXPIRED"]
)
def test_withdraw_terminal_state(actions_factory, persona_data, state):
    app_id, _ = completed(actions_factory, persona_data, "ip_good")
    with actions_factory.begin() as session:
        session.get(Application, app_id).state = state
    with client_for(actions_factory, "ip_good") as client:
        assert_error(client.post(path(app_id, "withdraw")), 409, "INVALID_TRANSITION")


@pytest.mark.parametrize(
    "action", ["offer/accept", "offer/reject", "withdraw", "objection"]
)
def test_other_company_is_hidden(actions_factory, persona_data, action):
    app_id, _ = completed(actions_factory, persona_data, "ip_good")
    body = (
        {"offer_version": 1}
        if action == "offer/accept"
        else {"text": "Прошу пересмотреть решение"}
        if action == "objection"
        else None
    )
    with client_for(actions_factory, "ip_bad") as client:
        assert_error(
            client.post(path(app_id, action), **({"json": body} if body else {})),
            404,
            "NOT_FOUND",
        )


def test_accountant_cannot_withdraw_submitted(actions_factory, persona_data):
    persona = next(p for p in persona_data["personas"] if p["code"] == "ooo_load")
    app_id = submit_persona(actions_factory, persona)
    with client_for(actions_factory, "ooo_load_accountant") as client:
        assert_error(client.post(path(app_id, "withdraw")), 403, "SIGN_NOT_ALLOWED")


@pytest.mark.parametrize("reason_code", ["EXPIRED_OFFER", "EXPIRED_INFO"])
def test_expiry_reason_comes_from_latest_transition(
    actions_factory, persona_data, reason_code
):
    app_id, _ = completed(actions_factory, persona_data, "ip_good")
    from app.applications.state_machine import transition

    with actions_factory.begin() as session:
        application = session.get(Application, app_id)
        decision = session.scalar(
            select(Decision).where(Decision.application_id == app_id)
        )
        decision.inputs_snapshot = {"client_category": "Кредитная история"}
        reason = session.scalar(
            select(ReasonCatalog).where(ReasonCatalog.code == reason_code)
        )
        reason.client_text = "Срок истёк"
        reason.client_action = "Подайте новую заявку"
        transition(
            session,
            application,
            "EXPIRED",
            actor_type="SYSTEM",
            actor_id=None,
            reason_code=reason_code,
        )
    with client_for(actions_factory, "ip_good") as client:
        response = client.get(path(app_id))
    assert response.status_code == 200, response.text
    assert response.json()["client_reason"] == {
        "code": reason_code,
        "category": None,
        "text": "Срок истёк",
        "action": "Подайте новую заявку",
        "retry_after": None,
    }
