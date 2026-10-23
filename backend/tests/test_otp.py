"""OTP issuance, binding and durable attempt limits through the real API."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_applications_api import application_context, authenticate, create_body
from test_auth import PERSONAS

from app.models import Application, Party, User


@pytest.fixture
def signing_client(migrated_database):
    with application_context(migrated_database[0]) as context:
        yield context


def draft(session, client, login="ip_good"):
    persona = next(p for p in PERSONAS if any(u["login"] == login for u in p["users"]))
    authenticate(client, login)
    response = client.post("/applications", json=create_body(session, persona))
    assert response.status_code == 200, response.text
    return response.json()


def issue(client, application_id, purpose="CONSENTS", **fields):
    response = client.post(
        f"/applications/{application_id}/otp", json={"purpose": purpose, **fields}
    )
    assert response.status_code == 200, response.text
    return response.json()


def submit_body(otp, **changes):
    return {
        "otp_id": otp["otp_id"],
        "code": otp["demo_code"],
        "consents": {"pdn": True, "bki": True, "auto_decision": True},
        **changes,
    }


@pytest.mark.parametrize("demo_mode", [True, False])
def test_demo_code_and_hash_only_storage(signing_client, monkeypatch, demo_mode):
    from app.config import get_settings

    session, client = signing_client
    monkeypatch.setattr(get_settings(), "demo_mode", demo_mode)
    data = draft(session, client)
    before = datetime.now(UTC)
    otp = issue(client, data["id"])
    from app.models.process import Otp

    stored = session.get(Otp, UUID(otp["otp_id"]))
    assert before + timedelta(minutes=5) <= stored.expires_at
    assert stored.expires_at <= datetime.now(UTC) + timedelta(minutes=5)
    assert datetime.fromisoformat(otp["expires_at"]) == stored.expires_at
    assert stored.attempts == 0 and stored.used_at is None
    assert "code" not in stored.__table__.columns
    assert len(stored.code_hash) == 64
    if demo_mode:
        assert len(otp["demo_code"]) == 6 and otp["demo_code"].isascii()
        assert otp["demo_code"].isdigit()
        expected = hashlib.sha256(
            (otp["otp_id"] + otp["demo_code"]).encode()
        ).hexdigest()
        assert stored.code_hash == expected
        assert stored.code_hash != otp["demo_code"]
    else:
        assert otp["demo_code"] == ""


@pytest.mark.parametrize(
    "invalid",
    [
        "expired",
        "used",
        "user",
        "purpose",
        "application",
        "party",
        "missing",
        "malformed",
    ],
)
def test_invalid_otp_binding(signing_client, invalid):
    session, client = signing_client
    data = draft(session, client)
    otp = issue(client, data["id"])
    from app.models.process import Otp

    stored = session.get(Otp, UUID(otp["otp_id"]))
    if invalid == "expired":
        stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    elif invalid == "used":
        stored.used_at = datetime.now(UTC)
    elif invalid == "user":
        stored.user_id = session.scalar(select(User.id).where(User.login == "ooo_load"))
    elif invalid == "purpose":
        stored.purpose = "OFFER"
    elif invalid == "application":
        other = draft(session, client)
        stored.application_id = UUID(other["id"])
    elif invalid == "party":
        party = Party(
            application_id=UUID(data["id"]),
            role="BORROWER_SIGNATORY",
            user_id=stored.user_id,
            full_name="Подписант",
        )
        session.add(party)
        session.flush()
        stored.party_id = party.id
    elif invalid == "missing":
        otp["otp_id"] = str(uuid4())
    else:
        otp["otp_id"] = "invalid"
    session.commit()
    response = client.post(f"/applications/{data['id']}/submit", json=submit_body(otp))
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "OTP_INVALID"
    assert (
        response.json()["error"]["message"]
        == "Код недействителен или истёк — запросите новый"
    )
    assert stored.attempts == 0


def test_five_wrong_attempts_burn_code(signing_client):
    session, client = signing_client
    data = draft(session, client)
    otp = issue(client, data["id"])
    from app.models.process import Otp

    wrong = "000000" if otp["demo_code"] != "000000" else "111111"
    for attempt in range(1, 6):
        response = client.post(
            f"/applications/{data['id']}/submit", json=submit_body(otp, code=wrong)
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["message"] == "Неверный код"
        session.expire_all()
        stored = session.get(Otp, UUID(otp["otp_id"]))
        assert stored.attempts == attempt
        assert (stored.used_at is not None) == (attempt == 5)
    response = client.post(f"/applications/{data['id']}/submit", json=submit_body(otp))
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "OTP_INVALID"


@pytest.mark.parametrize(
    "login,purpose,status,code",
    [
        ("ooo_load_accountant", "CONSENTS", 403, "SIGN_NOT_ALLOWED"),
        ("ip_good", "OFFER", 409, "INVALID_TRANSITION"),
        ("ip_good", "GUARANTEE", 409, "INVALID_TRANSITION"),
    ],
)
def test_issuance_permissions_and_states(signing_client, login, purpose, status, code):
    session, client = signing_client
    data = draft(session, client, login)
    response = client.post(f"/applications/{data['id']}/otp", json={"purpose": purpose})
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


@pytest.mark.parametrize(
    "purpose,state,role",
    [
        ("OFFER", "OFFER_ISSUED", "BORROWER_SIGNATORY"),
        ("OFFER", "SIGNING", "BORROWER_SIGNATORY"),
        ("GUARANTEE", "SIGNING", "GUARANTOR"),
    ],
)
def test_party_bound_issuance(signing_client, purpose, state, role):
    session, client = signing_client
    data = draft(session, client)
    application = session.get(Application, UUID(data["id"]))
    application.state = state
    user = session.scalar(select(User).where(User.login == "ip_good"))
    party = Party(
        application_id=application.id,
        role=role,
        user_id=user.id,
        full_name=user.full_name,
    )
    session.add(party)
    session.commit()
    response = client.post(f"/applications/{data['id']}/otp", json={"purpose": purpose})
    assert response.status_code == 422, response.text
    assert "party_id" in response.json()["error"]["details"]["fields"]
    otp = issue(client, data["id"], purpose, party_id=str(party.id))
    assert len(otp["demo_code"]) == 6
    from app.models.process import Otp

    assert session.get(Otp, UUID(otp["otp_id"])).party_id == party.id
    party.user_id = session.scalar(select(User.id).where(User.login == "ooo_load"))
    session.commit()
    response = client.post(
        f"/applications/{data['id']}/otp",
        json={"purpose": purpose, "party_id": str(party.id)},
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "SIGN_NOT_ALLOWED"


@pytest.mark.parametrize("action", ["otp", "submit", "request-signature"])
def test_foreign_application_is_hidden(signing_client, action):
    session, client = signing_client
    data = draft(session, client)
    authenticate(client, "ooo_load")
    body = (
        {"purpose": "CONSENTS"}
        if action == "otp"
        else submit_body({"otp_id": str(uuid4()), "demo_code": "123456"})
        if action == "submit"
        else None
    )
    response = client.post(f"/applications/{data['id']}/{action}", json=body)
    assert response.status_code == 404, response.text


def test_verifier_consumes_party_bound_code_once(signing_client):
    from app.errors import ApiErrorException
    from app.models.process import Otp
    from app.signing.otp import verify_otp

    session, client = signing_client
    data = draft(session, client)
    application = session.get(Application, UUID(data["id"]))
    application.state = "SIGNING"
    user = session.scalar(select(User).where(User.login == "ip_good"))
    party = Party(
        application_id=application.id,
        role="GUARANTOR",
        user_id=user.id,
        full_name=user.full_name,
    )
    session.add(party)
    session.commit()
    otp = issue(client, data["id"], "GUARANTEE", party_id=str(party.id))
    for party_id in (None, uuid4(), "invalid"):
        with pytest.raises(ApiErrorException) as error:
            verify_otp(
                session,
                otp["otp_id"],
                otp["demo_code"],
                application=application,
                user=user,
                purpose="GUARANTEE",
                party_id=party_id,
            )
        assert error.value.status == 422 and error.value.code == "OTP_INVALID"
    verified_at = verify_otp(
        session,
        otp["otp_id"],
        otp["demo_code"],
        application=application,
        user=user,
        purpose="GUARANTEE",
        party_id=party.id,
    )
    session.commit()
    assert session.get(Otp, UUID(otp["otp_id"])).used_at == verified_at
    with pytest.raises(ApiErrorException) as error:
        verify_otp(
            session,
            otp["otp_id"],
            otp["demo_code"],
            application=application,
            user=user,
            purpose="GUARANTEE",
            party_id=party.id,
        )
    assert error.value.status == 422 and error.value.code == "OTP_INVALID"


@pytest.mark.parametrize("invalid", ["role", "application", "missing", "malformed"])
def test_issuance_rejects_unusable_party(signing_client, invalid):
    session, client = signing_client
    data = draft(session, client)
    application = session.get(Application, UUID(data["id"]))
    application.state = "SIGNING"
    user = session.scalar(select(User).where(User.login == "ip_good"))
    party = Party(
        application_id=application.id,
        role="GUARANTOR",
        user_id=user.id,
        full_name=user.full_name,
    )
    session.add(party)
    session.commit()
    party_id = str(party.id)
    if invalid == "role":
        party.role = "BORROWER_SIGNATORY"
    elif invalid == "application":
        other = draft(session, client)
        party.application_id = UUID(other["id"])
    elif invalid == "missing":
        party_id = str(uuid4())
    else:
        party_id = "invalid"
    session.commit()
    response = client.post(
        f"/applications/{data['id']}/otp",
        json={"purpose": "GUARANTEE", "party_id": party_id},
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "SIGN_NOT_ALLOWED"
