"""Atomic application submission, signed documents and signature requests."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import select
from test_applications_api import application_context, authenticate
from test_otp import draft, issue, submit_body

from app.models import (
    Application,
    ApplicationEvent,
    Company,
    Consent,
    Job,
    Party,
    Signature,
    User,
)


@pytest.fixture
def submit_client(migrated_database):
    with application_context(migrated_database[0]) as context:
        yield context


@pytest.mark.parametrize(
    "login,auto,types,party_roles",
    [
        ("ip_good", True, {"PDN", "BKI", "AUTO_DECISION"}, ["BORROWER_SIGNATORY"]),
        ("ip_good", False, {"PDN", "BKI", "AUTO_DECISION"}, ["BORROWER_SIGNATORY"]),
        ("ooo_load", True, {"PDN", "BKI"}, ["BORROWER_SIGNATORY", "GUARANTOR"]),
    ],
)
def test_submit_creates_signed_consents_and_job(
    submit_client, login, auto, types, party_roles
):
    session, client = submit_client
    data = draft(session, client, login)
    otp = issue(client, data["id"])
    body = submit_body(otp)
    body["consents"]["auto_decision"] = auto
    before = datetime.now(UTC)
    response = client.post(f"/applications/{data['id']}/submit", json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["state"] == "SUBMITTED"
    assert result["version"] == data["version"] + 1
    assert result["stage"]["index"] == 1
    assert result["timeline"][0]["status"] == "current"
    application = session.get(Application, UUID(data["id"]))
    assert before <= application.submitted_at <= datetime.now(UTC)
    assert application.awaiting_signature is False
    company = session.get(Company, application.company_id)
    user = session.scalar(select(User).where(User.login == login))
    parties = session.scalars(
        select(Party).where(Party.application_id == application.id)
    ).all()
    assert sorted(p.role for p in parties) == party_roles
    assert all(p.user_id == user.id and p.status == "PENDING" for p in parties)
    consents = session.scalars(
        select(Consent).where(Consent.application_id == application.id)
    ).all()
    assert {c.type for c in consents} == types
    signatures = session.scalars(
        select(Signature).where(Signature.application_id == application.id)
    ).all()
    assert len(signatures) == len(types)
    for consent in consents:
        assert consent.granted == (auto if consent.type == "AUTO_DECISION" else True)
        assert (
            next(p for p in parties if p.id == consent.party_id).role
            == "BORROWER_SIGNATORY"
        )
        document = {
            "type": consent.type,
            "application_id": str(application.id),
            "number": application.number,
            "company_inn": company.inn,
            "user_id": str(user.id),
            "granted": consent.granted,
            "signed_at": consent.signed_at.isoformat(),
        }
        expected = hashlib.sha256(
            json.dumps(document, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        assert consent.doc_hash == expected
        assert consent.expires_at == (
            None
            if consent.type == "AUTO_DECISION"
            else consent.signed_at.replace(year=consent.signed_at.year + 1)
        )
        signature = next(s for s in signatures if s.object_id == consent.id)
        assert signature.object_type == "CONSENT" and signature.doc_hash == expected
        assert signature.party_id == consent.party_id
        assert before <= signature.otp_verified_at <= consent.signed_at
    events = session.scalars(
        select(ApplicationEvent).where(
            ApplicationEvent.application_id == application.id
        )
    ).all()
    signed = [e for e in events if e.event_type == "CONSENT_SIGNED"]
    assert len(signed) == len(types)
    assert {e.payload["type"] for e in signed} == types
    assert all(
        e.reason_code is None
        and e.actor_id == user.id
        and e.actor_type == "CLIENT"
        and e.payload
        == {
            "type": e.payload["type"],
            "granted": auto if e.payload["type"] == "AUTO_DECISION" else True,
        }
        for e in signed
    )
    changed = [e for e in events if e.to_state == "SUBMITTED"]
    assert len(changed) == 1 and changed[0].event_type == "STATE_CHANGED"
    assert len(events) == len(types) + 2  # Includes the original DRAFT event.
    jobs = session.scalars(
        select(Job).where(Job.application_id == application.id)
    ).all()
    assert len(jobs) == 1
    assert (jobs[0].step, jobs[0].status, jobs[0].attempts) == (
        "VALIDATION",
        "PENDING",
        0,
    )
    assert before <= jobs[0].run_after <= datetime.now(UTC)
    from app.models.process import Otp

    assert session.get(Otp, UUID(otp["otp_id"])).used_at is not None
    repeat = client.post(f"/applications/{data['id']}/submit", json=body)
    assert (
        repeat.status_code == 409
        and repeat.json()["error"]["code"] == "INVALID_TRANSITION"
    )


def test_wrong_code_leaves_no_partial_submission(submit_client):
    session, client = submit_client
    data = draft(session, client)
    otp = issue(client, data["id"])
    wrong = "000000" if otp["demo_code"] != "000000" else "111111"
    response = client.post(
        f"/applications/{data['id']}/submit", json=submit_body(otp, code=wrong)
    )
    assert response.status_code == 422, response.text
    session.expire_all()
    assert session.get(Application, UUID(data["id"])).state == "DRAFT"
    for model in (Party, Consent, Signature, Job):
        assert not session.scalars(
            select(model).where(model.application_id == UUID(data["id"]))
        ).all()
    events = session.scalars(select(ApplicationEvent)).all()
    assert len(events) == 1 and events[0].to_state == "DRAFT"


def test_accountant_requests_once_director_sees_and_submits(submit_client):
    session, client = submit_client
    data = draft(session, client, "ooo_load_accountant")
    path = f"/applications/{data['id']}"
    response = client.post(
        path + "/submit",
        json=submit_body({"otp_id": data["id"], "demo_code": "123456"}),
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "SIGN_NOT_ALLOWED"
    first = client.post(path + "/request-signature")
    assert first.status_code == 200, first.text
    assert first.json()["awaiting_signature"] is True
    assert first.json()["version"] == data["version"] + 1
    second = client.post(path + "/request-signature")
    assert second.status_code == 200 and second.json() == first.json()
    events = session.scalars(
        select(ApplicationEvent).where(
            ApplicationEvent.event_type == "SIGNATURE_REQUESTED"
        )
    ).all()
    assert len(events) == 1 and events[0].actor_type == "CLIENT"
    authenticate(client, "ooo_load")
    listing = client.get("/applications", params={"company_id": data["company_id"]})
    assert listing.status_code == 200
    assert listing.json()[0]["awaiting_signature"] is True
    otp = issue(client, data["id"])
    response = client.post(path + "/submit", json=submit_body(otp))
    assert (
        response.status_code == 200 and response.json()["awaiting_signature"] is False
    )


def test_signatory_cannot_request_signature(submit_client):
    session, client = submit_client
    data = draft(session, client, "ooo_load")
    response = client.post(f"/applications/{data['id']}/request-signature")
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "SIGN_NOT_ALLOWED"


def test_request_signature_requires_draft(submit_client):
    session, client = submit_client
    data = draft(session, client, "ooo_load")
    otp = issue(client, data["id"])
    assert (
        client.post(
            f"/applications/{data['id']}/submit", json=submit_body(otp)
        ).status_code
        == 200
    )
    authenticate(client, "ooo_load_accountant")
    response = client.post(f"/applications/{data['id']}/request-signature")
    assert response.status_code == 409, response.text


def test_submission_failure_rolls_back_code_and_all_documents(
    submit_client, monkeypatch
):
    from app.models.process import Otp
    from app.schemas.api import SubmitRequest
    from app.signing import submit as submit_service

    session, client = submit_client
    data = draft(session, client)
    otp = issue(client, data["id"])

    def fail_transition(*args, **kwargs):
        raise RuntimeError("Остановка перед постановкой в очередь")

    monkeypatch.setattr(submit_service, "transition", fail_transition)
    with pytest.raises(RuntimeError, match="Остановка перед постановкой в очередь"):
        submit_service.submit(
            session,
            UUID(data["id"]),
            SubmitRequest(**submit_body(otp)),
            session.scalar(select(User).where(User.login == "ip_good")),
        )
    session.rollback()
    assert session.get(Otp, UUID(otp["otp_id"])).used_at is None
    assert session.get(Application, UUID(data["id"])).state == "DRAFT"
    for model in (Party, Consent, Signature, Job):
        assert not session.scalars(
            select(model).where(model.application_id == UUID(data["id"]))
        ).all()


def test_ooo_without_majority_founder_has_only_borrower(submit_client):
    from app.models import CompanyMember

    session, client = submit_client
    data = draft(session, client, "ooo_load")
    members = session.scalars(
        select(CompanyMember).where(
            CompanyMember.company_id == UUID(data["company_id"])
        )
    ).all()
    for member in members:
        member.share_pct = 50
    session.commit()
    otp = issue(client, data["id"])
    response = client.post(f"/applications/{data['id']}/submit", json=submit_body(otp))
    assert response.status_code == 200, response.text
    assert [party["role"] for party in response.json()["parties"]] == [
        "BORROWER_SIGNATORY"
    ]
