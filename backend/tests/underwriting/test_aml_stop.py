import pytest
from sqlalchemy import func, select

from app.models import Application, ApplicationEvent, Decision, Offer


@pytest.fixture
def aml_persona(persona_data, monkeypatch):
    persona = next(p for p in persona_data["personas"] if p["code"] == "ip_good")
    monkeypatch.setitem(persona["risk"], "aml_flag", True)
    monkeypatch.setitem(persona["demo"]["consents"], "auto_decision", False)


@pytest.fixture
def aml_application(aml_persona, run_persona, pipeline_factory):
    application_id = run_persona("ip_good")
    with pipeline_factory() as session:
        assert session.get(Application, application_id).state == "MANUAL_REVIEW"
        auto = session.scalar(
            select(Decision).where(
                Decision.application_id == application_id, Decision.kind == "AUTO"
            )
        )
        assert auto.route_reason == "NO_AUTO_CONSENT"
        assert auto.recommendation["outcome"] == "DECLINE"
        assert any(rule["code"] == "SF_ADDITIONAL" for rule in auto.rules_fired)
    return application_id


@pytest.mark.parametrize(
    "outcome,amount", [("APPROVE", 1_500_000), ("COUNTER", 1_000_000)]
)
def test_aml_stop_rejects_offer_without_side_effects(
    aml_application, bank_context, pipeline_factory, outcome, amount
):
    client, _ = bank_context
    with pipeline_factory() as session:
        events_before = session.scalar(
            select(func.count())
            .select_from(ApplicationEvent)
            .where(ApplicationEvent.application_id == aml_application)
        )
    response = client.post(
        f"/api/v1/underwriting/{aml_application}/decision",
        json={
            "outcome": outcome,
            "amount": amount,
            "term_months": 24,
            "comment": "Проверены данные компании",
        },
    )
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["fields"] == {
        "outcome": (
            "Заявка не прошла дополнительные проверки банка — одобрение недоступно"
        )
    }
    with pipeline_factory() as session:
        assert session.get(Application, aml_application).state == "MANUAL_REVIEW"
        assert (
            session.scalar(
                select(func.count())
                .select_from(Offer)
                .where(Offer.application_id == aml_application)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(Decision)
                .where(
                    Decision.application_id == aml_application,
                    Decision.kind == "MANUAL",
                )
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ApplicationEvent)
                .where(ApplicationEvent.application_id == aml_application)
            )
            == events_before
        )


@pytest.mark.parametrize(
    "outcome,fields,state",
    [
        ("DECLINE", {"client_reason_category": "Дополнительные проверки"}, "DECLINED"),
        (
            "REQUEST_INFO",
            {"info_questions": ["Предоставьте дополнительные сведения о деятельности"]},
            "INFO_REQUESTED",
        ),
    ],
)
def test_aml_stop_allows_decline_and_info_request(
    aml_application, bank_context, outcome, fields, state
):
    client, _ = bank_context
    response = client.post(
        f"/api/v1/underwriting/{aml_application}/decision",
        json={"outcome": outcome, "comment": "Проверены данные компании", **fields},
    )
    assert response.status_code == 200, response.text
    assert response.json()["state"] == state


def test_credit_stop_still_allows_approval_with_history_note(
    bank_context, persona_data, run_persona, monkeypatch
):
    persona = next(p for p in persona_data["personas"] if p["code"] == "ip_bad")
    monkeypatch.setitem(persona["demo"]["consents"], "auto_decision", False)
    application_id = run_persona("ip_bad")
    client, _ = bank_context
    response = client.post(
        f"/api/v1/underwriting/{application_id}/decision",
        json={
            "outcome": "APPROVE",
            "amount": 700_000,
            "term_months": 12,
            "comment": "Просрочка погашена, сведения проверены",
        },
    )
    assert response.status_code == 200, response.text
    card = response.json()
    assert card["state"] == "OFFER_ISSUED"
    assert any(
        rule["code"] == "SF_OVERDUE"
        for decision in card["decisions"]
        if decision["kind"] == "AUTO"
        for rule in decision["rules_fired"]
    )
    assert any(
        "Решение вопреки стоп-фактору:" in (entry["note"] or "")
        for entry in card["events"]
    )
