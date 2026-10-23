"""One-time codes bound to a user, application, purpose and signing party."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.applications import service
from app.auth.deps import member_company
from app.config import get_settings
from app.errors import ApiErrorException
from app.models import Application, Party, User
from app.models.process import Otp
from app.schemas.api import OtpRequest, OtpResponse

SIGN_MESSAGE = "Подписать может только сотрудник с правом подписи"
STATE_MESSAGE = "Действие недоступно в текущем состоянии заявки"
INVALID_MESSAGE = "Код недействителен или истёк — запросите новый"


def locked_application(
    session: Session, application_id: UUID, user: User
) -> Application:
    application = service.get(session, application_id, user)
    return session.scalars(
        select(Application)
        .where(Application.id == application.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()


def require_signatory(session: Session, application: Application, user: User) -> None:
    _, membership = member_company(application.company_id, user, session)
    if not membership.can_sign:
        raise ApiErrorException(403, "SIGN_NOT_ALLOWED", SIGN_MESSAGE)


def require_state(application: Application, *states: str) -> None:
    if application.state not in states:
        raise ApiErrorException(409, "INVALID_TRANSITION", STATE_MESSAGE)


def _uuid(value: UUID | str | None) -> UUID | None:
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _hash(otp_id: UUID, code: str) -> str:
    return hashlib.sha256((str(otp_id) + code).encode("utf-8")).hexdigest()


def issue(
    session: Session, application_id: UUID, body: OtpRequest, user: User
) -> OtpResponse:
    application = locked_application(session, application_id, user)
    party_id = None
    if body.purpose == "CONSENTS":
        require_signatory(session, application, user)
        require_state(application, "DRAFT")
    else:
        # TODO(lead): добавить 409 INVALID_TRANSITION для /otp в OpenAPI;
        # карточка B-06 разрешает в схемах только два ответа 404 у /applications.
        require_state(
            application,
            *(("OFFER_ISSUED", "SIGNING") if body.purpose == "OFFER" else ("SIGNING",)),
        )
        if body.party_id is None:
            raise ApiErrorException(
                422,
                "VALIDATION_ERROR",
                "Укажите участника подписи",
                {"fields": {"party_id": "Укажите участника подписи"}},
            )
        party = (
            session.get(Party, _uuid(body.party_id)) if _uuid(body.party_id) else None
        )
        role = "BORROWER_SIGNATORY" if body.purpose == "OFFER" else "GUARANTOR"
        if (
            party is None
            or party.application_id != application.id
            or party.user_id != user.id
            or party.role != role
        ):
            raise ApiErrorException(403, "SIGN_NOT_ALLOWED", SIGN_MESSAGE)
        party_id = party.id
    otp_id = uuid4()
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.now(UTC) + timedelta(minutes=5)
    session.add(
        Otp(
            id=otp_id,
            application_id=application.id,
            user_id=user.id,
            party_id=party_id,
            purpose=body.purpose,
            code_hash=_hash(otp_id, code),
            expires_at=expires_at,
        )
    )
    session.commit()
    return OtpResponse(
        otp_id=str(otp_id),
        demo_code=code if get_settings().demo_mode else "",
        expires_at=expires_at.isoformat(),
    )


def verify_otp(
    session: Session,
    otp_id: UUID | str,
    code: str,
    *,
    application: Application,
    user: User,
    purpose: str,
    party_id: UUID | str | None = None,
) -> datetime:
    """Consume a valid code in the caller's transaction.

    Call before any business writes: a wrong-code attempt is committed before
    raising so that request rollback cannot reset the five-attempt limit.
    """
    identity = _uuid(otp_id)
    otp = (
        session.scalar(
            select(Otp)
            .where(Otp.id == identity)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if identity
        else None
    )
    now = datetime.now(UTC)
    if (
        otp is None
        or otp.application_id != application.id
        or otp.user_id != user.id
        or otp.purpose != purpose
        or otp.party_id != _uuid(party_id)
        or (party_id is not None and _uuid(party_id) is None)
        or otp.used_at is not None
        or otp.expires_at <= now
        or otp.attempts >= 5
    ):
        raise ApiErrorException(422, "OTP_INVALID", INVALID_MESSAGE)
    if not hmac.compare_digest(otp.code_hash, _hash(otp.id, code)):
        otp.attempts += 1
        if otp.attempts >= 5:
            otp.used_at = now
        session.commit()
        raise ApiErrorException(422, "OTP_INVALID", "Неверный код")
    otp.used_at = now
    session.flush()
    return now
