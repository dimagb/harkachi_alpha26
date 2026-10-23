"""Atomic submission and idempotent requests to a company's signatory."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.applications.state_machine import transition
from app.auth.deps import member_company
from app.errors import ApiErrorException
from app.models import (
    Application,
    ApplicationEvent,
    Company,
    CompanyMember,
    Job,
    Party,
    User,
)
from app.schemas.api import SubmitRequest
from app.signing.consents import sign_consents
from app.signing.otp import (
    SIGN_MESSAGE,
    locked_application,
    require_signatory,
    require_state,
    verify_otp,
)


def submit(
    session: Session, application_id: UUID, body: SubmitRequest, user: User
) -> Application:
    application = locked_application(session, application_id, user)
    require_signatory(session, application, user)
    require_state(application, "DRAFT")
    verified_at = verify_otp(
        session,
        body.otp_id,
        body.code,
        application=application,
        user=user,
        purpose="CONSENTS",
    )
    now = datetime.now(UTC)
    company = session.get(Company, application.company_id)
    borrower = Party(
        application_id=application.id,
        role="BORROWER_SIGNATORY",
        user_id=user.id,
        full_name=user.full_name,
    )
    session.add(borrower)
    if company.kind == "OOO":
        founder = session.scalar(
            select(User)
            .join(CompanyMember, CompanyMember.user_id == User.id)
            .where(
                CompanyMember.company_id == company.id,
                CompanyMember.is_founder.is_(True),
                CompanyMember.share_pct > 50,
            )
            .order_by(User.id)
        )
        if founder is not None:
            session.add(
                Party(
                    application_id=application.id,
                    role="GUARANTOR",
                    user_id=founder.id,
                    full_name=founder.full_name,
                )
            )
    session.flush()
    sign_consents(
        session,
        application,
        company,
        borrower,
        user,
        body.consents.auto_decision,
        verified_at,
        now,
    )
    transition(session, application, "SUBMITTED", actor_type="CLIENT", actor_id=user.id)
    application.submitted_at = now
    application.awaiting_signature = False
    session.add(
        Job(
            application_id=application.id,
            step="VALIDATION",
            status="PENDING",
            attempts=0,
            run_after=now,
        )
    )
    session.commit()
    return application


def request_signature(
    session: Session, application_id: UUID, user: User
) -> Application:
    application = locked_application(session, application_id, user)
    _, membership = member_company(application.company_id, user, session)
    if membership.can_sign:
        raise ApiErrorException(403, "SIGN_NOT_ALLOWED", SIGN_MESSAGE)
    require_state(application, "DRAFT")
    if not application.awaiting_signature:
        application.awaiting_signature = True
        session.add(
            ApplicationEvent(
                application_id=application.id,
                event_type="SIGNATURE_REQUESTED",
                actor_type="CLIENT",
                actor_id=user.id,
                payload={},
                created_at=datetime.now(UTC),
            )
        )
    session.commit()
    return application
