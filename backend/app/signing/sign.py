"""Party-bound electronic signatures and atomic disbursement scheduling."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.applications.state_machine import transition
from app.errors import ApiErrorException
from app.models import (
    Application,
    ApplicationEvent,
    Company,
    Job,
    Offer,
    Party,
    Signature,
    User,
)
from app.schemas.api import SignRequest
from app.signing.consents import sign_consents
from app.signing.otp import (
    SIGN_MESSAGE,
    _uuid,
    locked_application,
    require_state,
    verify_otp,
)


def sign(
    session: Session, application_id: UUID, body: SignRequest, user: User
) -> Application:
    application = locked_application(session, application_id, user)
    require_state(application, "SIGNING")
    identity = _uuid(body.party_id)
    party = session.get(Party, identity) if identity else None
    if (
        party is None
        or party.application_id != application.id
        or party.user_id != user.id
    ):
        raise ApiErrorException(403, "SIGN_NOT_ALLOWED", SIGN_MESSAGE)
    if party.status == "SIGNED":
        raise ApiErrorException(409, "INVALID_TRANSITION", "Документ уже подписан")
    offer = session.get(Offer, application.current_offer_id)
    now = datetime.now(UTC)
    if offer.status == "EXPIRED" or offer.expires_at <= now:
        raise ApiErrorException(409, "OFFER_EXPIRED", "Срок предложения истёк")
    purpose = "OFFER" if party.role == "BORROWER_SIGNATORY" else "GUARANTEE"
    verified_at = verify_otp(
        session,
        body.otp_id,
        body.code,
        application=application,
        user=user,
        purpose=purpose,
        party_id=party.id,
    )
    document = {
        "type": purpose,
        "application_id": str(application.id),
        "number": application.number,
        "amount": offer.amount,
        "term_months": offer.term_months,
        "rate": str(offer.rate),
        "monthly_payment": offer.monthly_payment,
        "role": party.role,
        "full_name": party.full_name,
        "signed_at": now.isoformat(),
    }
    doc_hash = hashlib.sha256(
        json.dumps(document, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    party.status = "SIGNED"
    session.add(
        Signature(
            application_id=application.id,
            party_id=party.id,
            object_type=purpose,
            object_id=offer.id if purpose == "OFFER" else party.id,
            doc_hash=doc_hash,
            otp_verified_at=verified_at,
        )
    )
    if party.role == "GUARANTOR":
        sign_consents(
            session,
            application,
            session.get(Company, application.company_id),
            party,
            user,
            False,
            verified_at,
            now,
        )
    session.add(
        ApplicationEvent(
            application_id=application.id,
            event_type="SIGNED",
            actor_type="CLIENT",
            actor_id=user.id,
            payload={"party_id": str(party.id), "role": party.role},
            created_at=now,
        )
    )
    session.flush()
    pending = session.scalar(
        select(Party.id)
        .where(
            Party.application_id == application.id,
            Party.required_signature.is_(True),
            Party.status != "SIGNED",
        )
        .limit(1)
    )
    if pending is None:
        transition(
            session, application, "SIGNED", actor_type="CLIENT", actor_id=user.id
        )
        session.add(
            Job(
                application_id=application.id,
                step="DISBURSEMENT",
                status="PENDING",
                attempts=0,
                run_after=now,
            )
        )
    else:
        application.version += 1
    session.commit()
    return application
