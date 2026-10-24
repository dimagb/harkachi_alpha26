from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.applications.serializers import to_client
from app.applications.state_machine import transition
from app.models import (
    Application,
    ApplicationEvent,
    Consent,
    InfoRequest,
    Objection,
    Offer,
    User,
)


@pytest.mark.parametrize(
    "code,signing,reason,stage",
    [
        ("ip_good", False, "EXPIRED_OFFER", 4),
        ("ip_good", True, "EXPIRED_OFFER", 5),
        ("ooo_gap", False, "EXPIRED_INFO", 2),
    ],
)
def test_due_application_expires_once(
    pipeline_factory, run_persona, code, signing, reason, stage
):
    from app.expiry.service import expire_due

    identity = run_persona(code)
    with pipeline_factory.begin() as session:
        application = session.get(Application, identity)
        if signing:
            transition(
                session,
                application,
                "SIGNING",
                actor_type="CLIENT",
                actor_id=application.created_by,
            )
        if reason == "EXPIRED_OFFER":
            session.get(Offer, application.current_offer_id).expires_at = datetime.now(
                UTC
            ) - timedelta(seconds=1)
        else:
            request = session.scalar(
                select(InfoRequest).where(InfoRequest.application_id == identity)
            )
            request.due_at = datetime.now(UTC) - timedelta(seconds=1)
        session.add(
            Objection(
                application_id=identity, text="Проверка скрытия нерешённого возражения"
            )
        )
        session.flush()
        version = application.version
        events = session.scalar(select(func.count()).select_from(ApplicationEvent))
    assert expire_due(pipeline_factory) == 1
    assert expire_due(pipeline_factory) == 0
    with pipeline_factory() as session:
        application = session.get(Application, identity)
        assert application.state == "EXPIRED"
        assert application.version == version + 1
        assert (
            session.scalar(select(func.count()).select_from(ApplicationEvent))
            == events + 1
        )
        event = session.scalar(
            select(ApplicationEvent).where(ApplicationEvent.to_state == "EXPIRED")
        )
        assert event.reason_code == reason
        assert event.actor_type == "SYSTEM" and event.actor_id is None
        if reason == "EXPIRED_OFFER":
            assert session.get(Offer, application.current_offer_id).status == "EXPIRED"
        view = to_client(
            session, application, session.get(User, application.created_by)
        )
        assert view.client_reason.code == reason
        assert view.client_reason.category is None
        assert view.stage.index == stage
        assert view.timeline[stage - 1].status == "cancelled"
        assert view.allowed_actions == ["NEW_APPLICATION"]
        assert view.objection is None


def test_future_deadlines_are_unchanged(pipeline_factory, run_persona):
    from app.expiry.service import expire_due

    ids = [run_persona("ip_good"), run_persona("ooo_gap")]
    with pipeline_factory() as session:
        versions = [session.get(Application, identity).version for identity in ids]
    assert expire_due(pipeline_factory) == 0
    with pipeline_factory() as session:
        assert [
            session.get(Application, identity).version for identity in ids
        ] == versions
        assert [session.get(Application, identity).state for identity in ids] == [
            "OFFER_ISSUED",
            "INFO_REQUESTED",
        ]


def test_time_shift_accumulates_and_shifts_all_deadlines(
    bank_context, pipeline_factory, run_persona
):
    client, _ = bank_context
    identity = run_persona("ip_good")
    with pipeline_factory() as session:
        application = session.get(Application, identity)
        offer_deadline = session.get(Offer, application.current_offer_id).expires_at
        consents = {
            c.id: c.expires_at
            for c in session.scalars(
                select(Consent).where(Consent.application_id == identity)
            )
        }
        events = session.scalar(select(func.count()).select_from(ApplicationEvent))
    response = client.post(
        "/api/v1/demo/time-shift", json={"application_id": str(identity), "days": 29}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "application_id": str(identity),
        "expired_now": False,
        "state": "OFFER_ISSUED",
    }
    with pipeline_factory() as session:
        application = session.get(Application, identity)
        assert session.get(
            Offer, application.current_offer_id
        ).expires_at == offer_deadline - timedelta(days=29)
        assert (
            session.scalar(select(func.count()).select_from(ApplicationEvent)) == events
        )
        for consent in session.scalars(
            select(Consent).where(Consent.application_id == identity)
        ):
            assert consent.expires_at == (
                consents[consent.id] - timedelta(days=29)
                if consents[consent.id]
                else None
            )
    response = client.post(
        "/api/v1/demo/time-shift", json={"application_id": str(identity), "days": 2}
    )
    assert response.json() == {
        "application_id": str(identity),
        "expired_now": True,
        "state": "EXPIRED",
    }
    repeated = client.post(
        "/api/v1/demo/time-shift", json={"application_id": str(identity), "days": 1}
    )
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "INVALID_TRANSITION"


def test_info_time_shift(bank_context, pipeline_factory, run_persona):
    client, _ = bank_context
    identity = run_persona("ooo_gap")
    response = client.post(
        "/api/v1/demo/time-shift", json={"application_id": str(identity), "days": 6}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "application_id": str(identity),
        "expired_now": True,
        "state": "EXPIRED",
    }


@pytest.mark.parametrize("identity", ["abc", str(uuid4())])
def test_shift_missing_application(bank_context, identity):
    client, _ = bank_context
    response = client.post(
        "/api/v1/demo/time-shift", json={"application_id": identity, "days": 1}
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_accountant_draft_then_signature_request(bank_context, pipeline_factory):
    from app.applications.service import create
    from app.models import CompanyMember
    from app.schemas.api import ApplicationCreate
    from app.signing.submit import request_signature

    with pipeline_factory() as session:
        user = session.scalar(select(User).where(User.login == "ooo_load_accountant"))
        member = session.scalar(
            select(CompanyMember).where(CompanyMember.user_id == user.id)
        )
        application = create(
            session,
            ApplicationCreate(
                company_id=str(member.company_id),
                product_code="EXPRESS",
                amount=500_000,
                term_months=12,
                purpose="WORKING_CAPITAL",
                purpose_text=None,
                declared_revenue_year=10_000_000,
            ),
            user,
        )
        response = bank_context[0].post(
            "/api/v1/demo/time-shift",
            json={"application_id": str(application.id), "days": 1},
        )
        assert response.status_code == 409, response.text
        journal = bank_context[0].get("/api/v1/bank/applications").json()["items"][0]
        assert journal["grade"] is None
        assert journal["route_reason"] is None
        assert journal["waiting_since"] is None
        view = to_client(session, application, user)
        assert view.timeline[0].status == "action_required"
        assert (
            view.stage.what_to_do == "Отправьте заявку на подпись руководителю "
            "или сотруднику с правом подписи"
        )
        application = request_signature(session, application.id, user)
        view = to_client(session, application, user)
        assert view.timeline[0].status == "current"
        assert view.stage.what_to_do == "Ждём решения подписанта компании"
