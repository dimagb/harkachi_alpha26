"""F14: rejected consent submissions never reach external sources."""

from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.auth.deps import current_user, get_session
from app.main import app
from app.models import Application, Company, Consent, ExternalCheck, Job, User
from app.pipeline.steps import Providers
from app.schemas.api import OtpRequest
from app.signing import otp
from tests.pipeline.test_pipeline import drain, providers_for, submit_persona


def counting_providers(data):
    providers = providers_for(data)
    return Providers(
        registry=Mock(wraps=providers.registry),
        bureau=Mock(wraps=providers.bureau),
        tax=Mock(wraps=providers.tax),
    )


@pytest.mark.parametrize(
    "consents",
    [
        {"pdn": True, "bki": False, "auto_decision": True},
        {"pdn": False, "bki": True, "auto_decision": True},
        {"pdn": False, "bki": False, "auto_decision": True},
        {"pdn": True, "auto_decision": True},
        {"bki": True, "auto_decision": True},
        {"auto_decision": True},
    ],
    ids=["no-bki", "no-pdn", "neither", "missing-bki", "missing-pdn", "missing-both"],
)
def test_submit_without_required_consents_never_calls_sources(
    pipeline_factory, persona_data, monkeypatch, consents
):
    persona = persona_data["personas"][0]
    params = persona["demo"]["app"]
    providers = counting_providers(persona_data)
    with pipeline_factory() as session:
        company = session.scalar(select(Company).where(Company.inn == persona["inn"]))
        user = session.scalar(select(User).where(User.login == persona["code"]))
        application = Application(
            company_id=company.id,
            created_by=user.id,
            product_code=params["product"],
            amount=params["amount"],
            term_months=params["term"],
            purpose=params["purpose"],
            declared_revenue_year=params["declared_revenue_year"],
            state="DRAFT",
        )
        session.add(application)
        session.commit()
        application_id = application.id
        challenge = otp.issue(
            session, application_id, OtpRequest(purpose="CONSENTS"), user
        )

        def test_session():
            yield session

        monkeypatch.setitem(app.dependency_overrides, get_session, test_session)
        monkeypatch.setitem(app.dependency_overrides, current_user, lambda: user)
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/applications/{application_id}/submit",
                json={
                    "otp_id": str(challenge.otp_id),
                    "code": challenge.demo_code,
                    "consents": consents,
                },
            )
        assert response.status_code == 422

    drain(pipeline_factory, providers, persona_data)
    for provider in (providers.registry, providers.bureau, providers.tax):
        provider.get.assert_not_called()
    with pipeline_factory() as session:
        assert session.get(Application, application_id).state == "DRAFT"
        for model in (Job, ExternalCheck, Consent):
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.application_id == application_id)
                )
                == 0
            )


def test_signed_consents_reach_bureau_with_the_granted_consent_id(
    pipeline_factory, persona_data
):
    persona = persona_data["personas"][0]
    providers = counting_providers(persona_data)
    application_id = submit_persona(pipeline_factory, persona)
    drain(pipeline_factory, providers, persona_data)

    providers.registry.get.assert_called_once_with(persona["inn"])
    providers.tax.get.assert_called_once_with(persona["inn"])
    providers.bureau.get.assert_called_once()
    inn, consent_id = providers.bureau.get.call_args.args
    assert inn == persona["inn"]
    with pipeline_factory() as session:
        consent = session.get(Consent, UUID(consent_id))
        assert consent.application_id == application_id
        assert consent.type == "BKI"
        assert consent.granted is True
        check = session.scalar(
            select(ExternalCheck).where(
                ExternalCheck.application_id == application_id,
                ExternalCheck.source == "BKI",
            )
        )
        assert check.request == {
            "inn": persona["inn"],
            "kind": "FULL",
            "consent_id": consent_id,
        }
        assert check.status == "OK"
        assert session.get(Application, application_id).state == "OFFER_ISSUED"
