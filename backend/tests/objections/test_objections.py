from datetime import UTC, datetime, timedelta

import pytest
from offers.test_actions import assert_error, path
from sqlalchemy import select
from test_application_offer_view import client_for, completed

from app.models import (
    Application,
    ApplicationEvent,
    Decision,
    DecisionConfig,
    Objection,
    Product,
)

TEXT = "Прошу пересмотреть решение: задолженность погашена"


@pytest.mark.parametrize("outcome", ["APPROVE", "COUNTER", "DECLINE"])
def test_objection_and_resolution(actions_factory, persona_data, outcome):
    app_id, _ = completed(actions_factory, persona_data, "ip_bad")
    with client_for(actions_factory, "ip_bad") as client:
        before = client.get(path(app_id)).json()
        assert before["allowed_actions"] == ["OBJECT", "NEW_APPLICATION"]
        invalid = client.post(path(app_id, "objection"), json={"text": "123456789"})
        assert_error(invalid, 422, "VALIDATION_ERROR")
        assert "text" in invalid.json()["error"]["details"]["fields"]
        response = client.post(path(app_id, "objection"), json={"text": TEXT})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["state"] == "MANUAL_REVIEW"
        assert data["version"] == before["version"] + 1
        assert data["objection"]["status"] == "PENDING"
        assert data["objection"]["outcome_text"] is None
        assert (
            data["stage"]["what_happens"]
            == "Заявку рассматривает специалист банка — обычно до 1 рабочего дня"
        )
        assert data["client_reason"] is None
        for internal in ("route_reason", "OBJECTION", "inputs_snapshot", TEXT):
            assert internal not in response.text
        assert_error(
            client.post(path(app_id, "objection"), json={"text": TEXT}),
            403,
            "OBJECTION_NOT_ALLOWED",
        )
    with actions_factory() as session:
        objection = session.scalar(
            select(Objection).where(Objection.application_id == app_id)
        )
        assert objection.text == TEXT
        event = session.scalar(
            select(ApplicationEvent).where(
                ApplicationEvent.application_id == app_id,
                ApplicationEvent.event_type == "OBJECTION_FILED",
            )
        )
        assert event.actor_type == "CLIENT"
        assert event.actor_id == session.get(Application, app_id).created_by
        assert event.payload == {"objection_id": str(objection.id)}
        assert event.reason_code is None
    with client_for(actions_factory, "bank_b09a") as bank:
        queue = bank.get("/api/v1/underwriting/queue")
        assert queue.status_code == 200, queue.text
        assert (
            next(a for a in queue.json() if a["id"] == str(app_id))["route_reason"]
            == "OBJECTION"
        )
        card = bank.get(f"/api/v1/underwriting/applications/{app_id}")
        assert card.status_code == 200, card.text
        assert card.json()["objection"]["status"] == "PENDING"
        assert next(
            e for e in card.json()["events"] if e["event_type"] == "OBJECTION_FILED"
        )["actor"].startswith("Клиент: ")
        body = {"outcome": outcome, "comment": "Проверены дополнительные сведения"}
        if outcome == "DECLINE":
            body["client_reason_category"] = "Кредитная история"
        else:
            body.update(
                amount=before["amount"] if outcome == "APPROVE" else 500_000,
                term_months=before["term_months"],
            )
        result = bank.post(f"/api/v1/underwriting/{app_id}/decision", json=body)
        assert result.status_code == 200, result.text
        assert result.json()["objection"]["status"] == "RESOLVED"
    with client_for(actions_factory, "ip_bad") as client:
        data = client.get(path(app_id)).json()
        assert data["state"] == ("DECLINED" if outcome == "DECLINE" else "OFFER_ISSUED")
        assert data["objection"]["status"] == "RESOLVED"
        assert data["objection"]["outcome_text"] == (
            "Специалист банка повторно проверил заявку и подтвердил отказ"
            if outcome == "DECLINE"
            else "Специалист банка пересмотрел решение — смотрите предложение ниже"
        )
        assert "OBJECT" not in data["allowed_actions"]
    with actions_factory() as session:
        row = session.scalar(
            select(Objection).where(Objection.application_id == app_id)
        )
        assert row.outcome == ("REJECTED" if outcome == "DECLINE" else "UPHELD")
        assert row.resolved_at is not None


@pytest.mark.parametrize("problem", ["company", "manual", "old", "used"])
def test_ineligible_objection(actions_factory, persona_data, problem):
    code = "ooo_aml" if problem == "company" else "ip_bad"
    app_id, _ = completed(actions_factory, persona_data, code)
    with actions_factory.begin() as session:
        decision = session.scalar(
            select(Decision).where(Decision.application_id == app_id)
        )
        if problem == "manual":
            decision.kind = "MANUAL"
        elif problem == "old":
            decision.created_at = datetime.now(UTC) - timedelta(days=31)
        elif problem == "used":
            session.add(
                Objection(
                    application_id=app_id,
                    text=TEXT,
                    resolved_at=datetime.now(UTC),
                    outcome="REJECTED",
                )
            )
    with client_for(actions_factory, code) as client:
        assert "OBJECT" not in client.get(path(app_id)).json()["allowed_actions"]
        assert_error(
            client.post(path(app_id, "objection"), json={"text": TEXT}),
            403,
            "OBJECTION_NOT_ALLOWED",
        )


@pytest.mark.parametrize("state", ["WITHDRAWN", "EXPIRED"])
def test_cancelled_application_hides_pending_objection(
    actions_factory, persona_data, state
):
    app_id, _ = completed(actions_factory, persona_data, "ip_bad")
    with client_for(actions_factory, "ip_bad") as client:
        response = client.post(path(app_id, "objection"), json={"text": TEXT})
        assert response.status_code == 200, response.text
        if state == "WITHDRAWN":
            response = client.post(path(app_id, "withdraw"))
        else:
            with actions_factory.begin() as session:
                session.get(Application, app_id).state = "EXPIRED"
            response = client.get(path(app_id))
        assert response.status_code == 200, response.text
        assert response.json()["objection"] is None


def test_request_info_does_not_resolve(actions_factory, persona_data):
    app_id, _ = completed(actions_factory, persona_data, "ip_bad")
    with client_for(actions_factory, "ip_bad") as client:
        assert (
            client.post(path(app_id, "objection"), json={"text": TEXT}).status_code
            == 200
        )
    with client_for(actions_factory, "bank_b09a") as bank:
        response = bank.post(
            f"/api/v1/underwriting/{app_id}/decision",
            json={
                "outcome": "REQUEST_INFO",
                "comment": "Нужны дополнительные сведения",
                "info_questions": ["Когда погашена задолженность?"],
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["objection"]["status"] == "PENDING"


def test_fallback_rate_uses_decision_config(actions_factory, persona_data):
    app_id, _ = completed(actions_factory, persona_data, "ip_bad")
    with actions_factory.begin() as session:
        decision = session.scalar(
            select(Decision).where(Decision.application_id == app_id)
        )
        decision.policy = None
        cfg = session.scalar(
            select(DecisionConfig).where(
                DecisionConfig.version == decision.config_version
            )
        )
        cfg.params = {"products": {"EXPRESS": {"spread": {"A": 2, "B": 3, "C": 5}}}}
        product = session.scalar(select(Product).where(Product.code == "EXPRESS"))
        product.params = dict(product.params, spread={"A": 10, "B": 11, "C": 12})
    with client_for(actions_factory, "ip_bad") as client:
        response = client.post(path(app_id, "objection"), json={"text": TEXT})
        assert response.status_code == 200, response.text
        application = response.json()
    with client_for(actions_factory, "bank_b09a") as bank:
        response = bank.post(
            f"/api/v1/underwriting/{app_id}/decision",
            json={
                "outcome": "APPROVE",
                "amount": application["amount"],
                "term_months": application["term_months"],
                "comment": "Подтверждены дополнительные сведения",
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["offer"]["rate"] == 19


def test_event_without_actor_has_clean_label(actions_factory, persona_data):
    app_id, _ = completed(actions_factory, persona_data, "ip_bad")
    with actions_factory.begin() as session:
        session.add(
            ApplicationEvent(
                application_id=app_id,
                event_type="OBJECTION_FILED",
                actor_type="CLIENT",
                actor_id=None,
                payload={},
            )
        )
    with client_for(actions_factory, "bank_b09a") as bank:
        response = bank.get(f"/api/v1/underwriting/applications/{app_id}")
    assert response.status_code == 200, response.text
    assert (
        next(
            e for e in response.json()["events"] if e["event_type"] == "OBJECTION_FILED"
        )["actor"]
        == "Клиент"
    )
