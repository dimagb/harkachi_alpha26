"""Signing binds an OTP to a party and queues exactly one disbursement."""

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.applications.state_machine import transition
from app.auth.deps import current_user
from app.db import get_session
from app.main import app
from app.models import (
    Application,
    ApplicationEvent,
    Company,
    CompanyMember,
    Consent,
    Disbursement,
    Job,
    Offer,
    Party,
    Signature,
    User,
)


@pytest.fixture
def signing(migrated_database, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("PIPELINE_STEP_DELAY_SEC", "0")
    from app.config import get_settings

    get_settings.cache_clear()
    engine, _ = migrated_database
    connection = engine.connect()
    transaction = connection.begin()
    factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = factory()
    user = User(
        login=str(uuid4()), password_hash="", role="CLIENT", full_name="Иван Иванов"
    )
    company = Company(
        inn="7707083893",
        ogrn="1027700132195",
        kind="IP",
        name="Тест",
        okved_main="47.11",
        reg_date=date(2020, 1, 1),
        address="Москва",
    )
    session.add_all([user, company])
    session.flush()
    member = CompanyMember(
        user_id=user.id,
        company_id=company.id,
        position="Директор",
        can_sign=True,
        is_founder=True,
        share_pct=100,
    )
    application = Application(
        company_id=company.id,
        created_by=user.id,
        product_code="WORKING_CAPITAL",
        amount=1_500_000,
        term_months=24,
        purpose="WORKING_CAPITAL",
        declared_revenue_year=12_000_000,
        state="OFFER_ISSUED",
    )
    session.add_all([member, application])
    session.flush()
    offer = Offer(
        application_id=application.id,
        kind="APPROVED",
        product_code=application.product_code,
        amount=1_500_000,
        term_months=24,
        rate=Decimal("22.00"),
        monthly_payment=77_817,
        status="ACCEPTED",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    borrower = Party(
        application_id=application.id,
        role="BORROWER_SIGNATORY",
        user_id=user.id,
        full_name=user.full_name,
    )
    session.add_all([offer, borrower])
    session.flush()
    application.current_offer_id = offer.id
    transition(session, application, "SIGNING", actor_type="CLIENT", actor_id=user.id)
    session.commit()
    app.dependency_overrides[current_user] = lambda: user
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        yield (
            client,
            session,
            factory,
            user,
            company,
            member,
            application,
            offer,
            borrower,
        )
    app.dependency_overrides.pop(current_user, None)
    app.dependency_overrides.pop(get_session, None)
    session.close()
    transaction.rollback()
    connection.close()
    get_settings.cache_clear()


def otp(client, application, party, purpose="OFFER"):
    response = client.post(
        f"/api/v1/applications/{application.id}/otp",
        json={"purpose": purpose, "party_id": str(party.id)},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    return {
        "otp_id": data["otp_id"],
        "code": data["demo_code"],
        "party_id": str(party.id),
    }


def sign(client, application, body):
    return client.post(f"/api/v1/applications/{application.id}/sign", json=body)


def test_ip_signs_and_worker_disburses_once(signing):
    client, session, factory, user, _, _, application, offer, borrower = signing
    body = otp(client, application, borrower)
    version = application.version
    response = sign(client, application, body)
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "SIGNED"
    session.refresh(application)
    assert application.version == version + 1
    jobs = session.scalars(
        select(Job).where(Job.application_id == application.id)
    ).all()
    assert len(jobs) == 1
    assert (jobs[0].step, jobs[0].status) == ("DISBURSEMENT", "PENDING")
    signature = session.scalar(
        select(Signature).where(Signature.party_id == borrower.id)
    )
    assert signature.object_type == "OFFER"
    assert signature.object_id == offer.id
    event = session.scalar(
        select(ApplicationEvent).where(
            ApplicationEvent.application_id == application.id,
            ApplicationEvent.event_type == "SIGNED",
        )
    )
    assert event.actor_type == "CLIENT"
    assert event.actor_id == user.id
    assert event.payload == {"party_id": str(borrower.id), "role": "BORROWER_SIGNATORY"}
    document = {
        "type": "OFFER",
        "application_id": str(application.id),
        "number": application.number,
        "amount": offer.amount,
        "term_months": 24,
        "rate": "22.00",
        "monthly_payment": 77_817,
        "role": borrower.role,
        "full_name": user.full_name,
        "signed_at": event.created_at.isoformat(),
    }
    assert (
        signature.doc_hash
        == hashlib.sha256(
            json.dumps(document, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    )
    from app.pipeline.steps import process_step

    process_step(factory, application.id, "DISBURSEMENT", None, date.today)
    session.expire_all()
    assert application.state == "DISBURSED"
    disbursement = session.scalar(
        select(Disbursement).where(Disbursement.application_id == application.id)
    )
    assert disbursement.amount == 1_500_000
    assert len(disbursement.schedule) == 24
    events = session.scalars(
        select(ApplicationEvent).where(
            ApplicationEvent.application_id == application.id,
            ApplicationEvent.event_type.in_(["DISBURSED", "BKI_REPORT"]),
        )
    ).all()
    assert {e.event_type for e in events} == {"DISBURSED", "BKI_REPORT"}
    assert all(e.actor_type == "SYSTEM" and e.actor_id is None for e in events)
    report = next(e.payload for e in events if e.event_type == "BKI_REPORT")
    assert report == {
        "report": "NEW_LOAN",
        "amount": 1_500_000,
        "term_months": 24,
        "rate": "22.00",
        "monthly_payment": 77_817,
        "disbursed_on": disbursement.disbursed_at.astimezone(
            __import__("zoneinfo").ZoneInfo("Europe/Moscow")
        )
        .date()
        .isoformat(),
    }
    response = client.get(f"/api/v1/applications/{application.id}")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["allowed_actions"] == ["NEW_APPLICATION"]
    assert data["offer"]["amount"] == 1_500_000
    assert data["timeline"][-1]["status"] == "done"
    process_step(factory, application.id, "DISBURSEMENT", None, date.today)
    assert (
        len(
            session.scalars(
                select(Disbursement).where(
                    Disbursement.application_id == application.id
                )
            ).all()
        )
        == 1
    )
    assert (
        len(
            session.scalars(
                select(ApplicationEvent).where(
                    ApplicationEvent.application_id == application.id,
                    ApplicationEvent.event_type.in_(["DISBURSED", "BKI_REPORT"]),
                )
            ).all()
        )
        == 2
    )


def test_director_signs_both_roles_and_guarantor_consents(signing):
    client, session, _, user, company, member, application, _, borrower = signing
    company.kind = "OOO"
    guarantor = Party(
        application_id=application.id,
        role="GUARANTOR",
        user_id=user.id,
        full_name=user.full_name,
    )
    session.add(guarantor)
    session.commit()
    response = sign(client, application, otp(client, application, borrower))
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "SIGNING"
    assert "SIGN" in response.json()["allowed_actions"]
    member.can_sign = False
    session.commit()
    response = sign(
        client, application, otp(client, application, guarantor, "GUARANTEE")
    )
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "SIGNED"
    consents = session.scalars(
        select(Consent).where(Consent.party_id == guarantor.id)
    ).all()
    assert {c.type for c in consents} == {"PDN", "BKI"}
    assert all(c.granted for c in consents)
    signatures = session.scalars(
        select(Signature).where(Signature.party_id == guarantor.id)
    ).all()
    assert {s.object_id for s in signatures if s.object_type == "CONSENT"} == {
        c.id for c in consents
    }
    assert any(
        s.object_type == "GUARANTEE" and s.object_id == guarantor.id for s in signatures
    )


@pytest.mark.parametrize(
    "case,status,code",
    [
        ("malformed_party", 403, "SIGN_NOT_ALLOWED"),
        ("missing_party", 403, "SIGN_NOT_ALLOWED"),
        ("foreign_user", 403, "SIGN_NOT_ALLOWED"),
        ("foreign_application", 403, "SIGN_NOT_ALLOWED"),
        ("wrong_otp", 422, "OTP_INVALID"),
        ("wrong_party_otp", 422, "OTP_INVALID"),
        ("signed_party", 409, "INVALID_TRANSITION"),
        ("expired_offer", 409, "OFFER_EXPIRED"),
        ("wrong_state", 409, "INVALID_TRANSITION"),
    ],
)
def test_sign_rejects_invalid_requests_without_side_effects(
    signing, case, status, code
):
    client, session, _, user, _, _, application, offer, borrower = signing
    body = otp(client, application, borrower)
    if case == "malformed_party":
        body["party_id"] = "not-a-uuid"
    elif case == "missing_party":
        body["party_id"] = str(uuid4())
    elif case == "foreign_user":
        borrower.user_id = None
    elif case == "foreign_application":
        other = Application(
            company_id=application.company_id,
            created_by=user.id,
            product_code=application.product_code,
            amount=100_000,
            term_months=12,
            purpose=application.purpose,
            declared_revenue_year=12_000_000,
        )
        session.add(other)
        session.flush()
        borrower.application_id = other.id
    elif case == "wrong_otp":
        body["code"] = "000000" if body["code"] != "000000" else "111111"
    elif case == "wrong_party_otp":
        guarantor = Party(
            application_id=application.id,
            role="GUARANTOR",
            user_id=user.id,
            full_name=user.full_name,
        )
        session.add(guarantor)
        session.flush()
        body["party_id"] = str(guarantor.id)
    elif case == "signed_party":
        borrower.status = "SIGNED"
    elif case == "expired_offer":
        offer.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    elif case == "wrong_state":
        application.state = "OFFER_ISSUED"
    session.commit()
    response = sign(client, application, body)
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert (
        session.scalar(
            select(Signature).where(Signature.application_id == application.id)
        )
        is None
    )
    assert (
        session.scalar(select(Job).where(Job.application_id == application.id)) is None
    )
    if case == "wrong_otp":
        from uuid import UUID

        from app.models.process import Otp

        session.expire_all()
        assert session.get(Otp, UUID(body["otp_id"])).attempts == 1


def test_duplicate_sign_does_not_create_second_signature(signing):
    client, session, _, _, _, _, application, _, borrower = signing
    body = otp(client, application, borrower)
    assert sign(client, application, body).status_code == 200
    assert sign(client, application, body).status_code == 409
    assert (
        len(
            session.scalars(
                select(Signature).where(Signature.party_id == borrower.id)
            ).all()
        )
        == 1
    )
