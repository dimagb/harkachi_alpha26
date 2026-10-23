"""Client projections exercised through the real committed pipeline."""

import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pipeline.conftest import persona_data as persona_data
from pipeline.conftest import pipeline_factory as pipeline_factory
from pipeline.test_pipeline import drain, providers_for, submit_persona
from sqlalchemy import delete, select, text

from app.auth.deps import current_user
from app.db import get_session
from app.main import app
from app.models import (
    Application,
    Company,
    Decision,
    InfoRequest,
    Offer,
    ReasonCatalog,
    User,
)

CLIENT_EXPLANATIONS = [
    ("business_age", "Бизнес работает больше 3 лет"),
    ("industry_risk", "Отрасль с низким риском"),
    ("mass_registration", "Руководитель и адрес компании не массовые"),
    ("turnover_stability", "Стабильные поступления на счёт"),
    ("turnover_trend", "Поступления на счёт не снижаются"),
    ("zero_months", "Поступления на счёт каждый месяц"),
    ("payment_to_turnover", "Низкая долговая нагрузка"),
    ("debt_to_turnover", "Небольшой долг относительно оборота"),
    ("delinquency_12m", "Нет просрочек по кредитам"),
    ("credit_history_length", "Длинная кредитная история"),
    ("bureau_inquiries_30d", "Мало обращений за кредитами в последний месяц"),
    ("payment_discipline", "Нет долгов по налогам и судебных взысканий"),
]


@pytest.fixture
def seeded_pipeline(pipeline_factory):
    # Load the actual demo seeds in this test's isolated schema.
    with pipeline_factory.begin() as session:
        schema = session.scalar(text("SELECT current_schema()"))
        url = session.get_bind().url.update_query_dict(
            {"options": f"-csearch_path={schema}"}
        )
        # The idempotent seed preserves existing rows; remove fixture placeholders.
        session.execute(delete(ReasonCatalog))
    subprocess.run(
        [sys.executable, "-m", "app.seed"],
        env={
            **os.environ,
            "DATABASE_URL": url.render_as_string(hide_password=False),
            "DEMO_PASSWORD": "b07c-test-password",
        },
        check=True,
        capture_output=True,
    )
    return pipeline_factory


@contextmanager
def client_for(factory, login):
    with factory() as session:
        user = session.scalar(select(User).where(User.login == login))

    def database():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = database
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(current_user, None)


def completed(factory, data, code):
    persona = next(p for p in data["personas"] if p["code"] == code)
    application_id = submit_persona(factory, persona)
    drain(factory, providers_for(data), data)
    return application_id, persona


@pytest.mark.parametrize("code", ["ip_good", "ooo_load"])
def test_pipeline_offer(pipeline_factory, persona_data, code):
    application_id, persona = completed(pipeline_factory, persona_data, code)
    with client_for(pipeline_factory, code) as client:
        response = client.get(f"/api/v1/applications/{application_id}")
    assert response.status_code == 200, response.text
    view = response.json()["offer"]
    assert view is not None
    for key, expected in persona["demo"]["expected"]["offer"].items():
        assert view[key] == expected
    with pipeline_factory() as session:
        application = session.get(Application, application_id)
        offer = session.get(Offer, application.current_offer_id)
        assert view["id"] == str(offer.id)
        assert view["version"] == offer.version
        assert view["status"] == offer.status
        assert datetime.fromisoformat(view["expires_at"]) == offer.expires_at
    assert 1 <= len(view["explanation"]) <= 3
    assert all(
        line in dict(CLIENT_EXPLANATIONS).values() for line in view["explanation"]
    )
    assert "`" not in " ".join(view["explanation"])
    assert "балл" not in " ".join(view["explanation"]).lower()
    if code == "ip_good":
        assert view["kind"] == "APPROVED"
        assert view["requested"] is None
        assert view["counter_reason"] is None
    else:
        assert view["kind"] == "COUNTER"
        assert view["requested"] == {
            "amount": persona["demo"]["app"]["amount"],
            "term_months": persona["demo"]["app"]["term"],
        }
        assert (
            view["counter_reason"]
            == "Платёж по запрошенным условиям был бы слишком большим для текущих "
            "оборотов. Предлагаем условия, при которых платёж не превышает 30% "
            "среднемесячных поступлений на счёт"
        )


@pytest.mark.parametrize(
    "code,reason", [("ip_bad", "SF_OVERDUE"), ("ooo_aml", "ADDITIONAL_CHECKS")]
)
def test_pipeline_decline(seeded_pipeline, persona_data, code, reason):
    pipeline_factory = seeded_pipeline
    application_id, _ = completed(pipeline_factory, persona_data, code)
    with pipeline_factory.begin() as session:
        catalog = session.scalar(
            select(ReasonCatalog).where(ReasonCatalog.code == reason)
        )
        expected_category = catalog.client_category
        expected_text = catalog.client_text
        expected_action = catalog.client_action
        decision = session.scalar(
            select(Decision).where(Decision.application_id == application_id)
        )
        decision.created_at = datetime(2026, 10, 23, 22, 30, tzinfo=UTC)
    with client_for(pipeline_factory, code) as client:
        response = client.get(f"/api/v1/applications/{application_id}")
    assert response.status_code == 200, response.text
    assert response.json()["client_reason"] == {
        "code": reason,
        "category": expected_category,
        "text": expected_text,
        "action": expected_action,
        "retry_after": "2026-11-23" if code == "ip_bad" else None,
    }
    for internal in (
        "SF_ADDITIONAL",
        "internal_reasons",
        "rules_fired",
        "inputs_snapshot",
        "risk_flag",
        '"factors"',
        '"score"',
    ):
        assert internal not in response.text


@pytest.mark.parametrize("offset", [0, 3, 6, 9])
def test_explanation_uses_public_phrases_in_protocol_order(
    pipeline_factory, persona_data, offset
):
    application_id, _ = completed(pipeline_factory, persona_data, "ip_good")
    # Unknown and non-maximal factors must not consume the three public lines.
    selected = CLIENT_EXPLANATIONS[offset:] + CLIENT_EXPLANATIONS[:offset]
    with pipeline_factory.begin() as session:
        decision = session.scalar(
            select(Decision).where(Decision.application_id == application_id)
        )
        template = decision.factors[0]
        decision.factors = [
            dict(template, code="unknown", points=10, max_points=10),
            dict(template, code=selected[-1][0], points=0, max_points=10),
        ] + [
            dict(template, code=code, points=10, max_points=10) for code, _ in selected
        ]
    with client_for(pipeline_factory, "ip_good") as client:
        view = client.get(f"/api/v1/applications/{application_id}").json()["offer"]
    assert view["explanation"] == [text for _, text in selected[:3]]


@pytest.mark.parametrize("factors", ["no_maximum", "empty", "unknown"])
def test_explanation_falls_back_without_public_strengths(
    pipeline_factory, persona_data, factors
):
    application_id, _ = completed(pipeline_factory, persona_data, "ip_good")
    with pipeline_factory.begin() as session:
        decision = session.scalar(
            select(Decision).where(Decision.application_id == application_id)
        )
        if factors == "empty":
            decision.factors = []
        elif factors == "unknown":
            decision.factors = [
                dict(decision.factors[0], code="unknown", points=10, max_points=10)
            ]
        else:
            decision.factors = [dict(factor, points=0) for factor in decision.factors]
    with client_for(pipeline_factory, "ip_good") as client:
        view = client.get(f"/api/v1/applications/{application_id}").json()["offer"]
    assert view["explanation"] == ["Условия рассчитаны по данным о вашем бизнесе"]


@pytest.mark.parametrize(
    "code", ["ip_good", "ip_bad", "ooo_load", "ooo_gap", "ooo_border", "ooo_aml"]
)
def test_client_json_has_no_internal_details(seeded_pipeline, persona_data, code):
    pipeline_factory = seeded_pipeline
    application_id, _ = completed(pipeline_factory, persona_data, code)
    with client_for(pipeline_factory, code) as client:
        response = client.get(f"/api/v1/applications/{application_id}")
    assert response.status_code == 200, response.text
    if code == "ooo_aml":
        assert response.json()["client_reason"] == {
            "code": "ADDITIONAL_CHECKS",
            "category": "Дополнительные проверки",
            "text": "Заявка не прошла дополнительные проверки банка",
            "action": None,
            "retry_after": None,
        }
    for internal in (
        "SF_ADDITIONAL",
        "internal_reasons",
        "rules_fired",
        "inputs_snapshot",
        "risk_flag",
        '"factors"',
        '"score"',
        "grade",
        "points",
        "max_points",
        "route_reason",
        "turnover_cv",
        "`",
    ):
        assert internal not in response.text


def test_age_reason_uses_first_eligible_day(pipeline_factory, persona_data):
    application_id, _ = completed(pipeline_factory, persona_data, "ip_bad")
    with pipeline_factory.begin() as session:
        application = session.get(Application, application_id)
        session.get(Company, application.company_id).reg_date = date(2026, 4, 15)
        decision = session.scalar(
            select(Decision).where(Decision.application_id == application_id)
        )
        decision.client_reason_code = "SF_AGE"
        catalog = session.scalar(
            select(ReasonCatalog).where(ReasonCatalog.code == "SF_AGE")
        )
        catalog.client_action = "Подайте заявку после {date}"
    with client_for(pipeline_factory, "ip_bad") as client:
        reason = client.get(f"/api/v1/applications/{application_id}").json()[
            "client_reason"
        ]
    assert reason["retry_after"] == "2026-10-01"
    assert reason["action"] == "Подайте заявку после 30.09.2026"


def test_latest_unanswered_info_request(pipeline_factory, persona_data):
    application_id, _ = completed(pipeline_factory, persona_data, "ooo_gap")
    with pipeline_factory.begin() as session:
        session.add(
            InfoRequest(
                application_id=application_id,
                source="UNDERWRITER",
                items=[
                    {
                        "item_code": "UNDERWRITER_QUESTION",
                        "question": "Уточните данные",
                        "requires_value": False,
                    }
                ],
                due_at=datetime.now(UTC) + timedelta(days=2),
                responded_at=datetime.now(UTC),
                created_at=datetime.now(UTC) + timedelta(seconds=1),
            )
        )
        open_request = session.scalar(
            select(InfoRequest).where(
                InfoRequest.application_id == application_id,
                InfoRequest.responded_at.is_(None),
            )
        )
        expected_id, expected_items = str(open_request.id), open_request.items
    with client_for(pipeline_factory, "ooo_gap") as client:
        view = client.get(f"/api/v1/applications/{application_id}").json()[
            "info_request"
        ]
    assert view["id"] == expected_id
    assert view["items"] == expected_items


def test_overdraft_counter_uses_current_offer(pipeline_factory, persona_data):
    application_id, _ = completed(pipeline_factory, persona_data, "ooo_load")
    with pipeline_factory.begin() as session:
        application = session.get(Application, application_id)
        current = session.get(Offer, application.current_offer_id)
        current.product_code = "OVERDRAFT"
        current.monthly_payment = None
        session.add(
            Offer(
                application_id=application_id,
                version=2,
                kind="APPROVED",
                product_code="EXPRESS",
                amount=300000,
                term_months=12,
                rate=22,
                status="SUPERSEDED",
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        current_id = str(current.id)
    with client_for(pipeline_factory, "ooo_load") as client:
        view = client.get(f"/api/v1/applications/{application_id}").json()["offer"]
    assert view["id"] == current_id
    assert view["monthly_payment"] is None
    assert view["counter_reason"] == (
        "Лимит овердрафта ограничен 40% среднемесячных поступлений на счёт"
    )


def test_newest_open_request_is_selected(pipeline_factory, persona_data):
    application_id, _ = completed(pipeline_factory, persona_data, "ooo_gap")
    with pipeline_factory.begin() as session:
        latest = InfoRequest(
            application_id=application_id,
            source="UNDERWRITER",
            items=[
                {
                    "item_code": "UNDERWRITER_QUESTION",
                    "question": "Поясните назначение кредита",
                    "requires_value": False,
                }
            ],
            due_at=datetime.now(UTC) + timedelta(days=3),
            created_at=datetime.now(UTC) + timedelta(seconds=1),
        )
        session.add(latest)
        session.flush()
        latest_id, latest_due = str(latest.id), latest.due_at
    with client_for(pipeline_factory, "ooo_gap") as client:
        view = client.get(f"/api/v1/applications/{application_id}").json()[
            "info_request"
        ]
    assert view["id"] == latest_id
    assert datetime.fromisoformat(view["due_at"]) == latest_due
