"""One objection per IP application within thirty days of an automatic refusal."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.applications.state_machine import transition
from app.errors import ApiErrorException
from app.models import Application, ApplicationEvent, Company, Decision, Objection, User
from app.schemas.api import ObjectionRequest
from app.signing.otp import locked_application, require_signatory


def eligible(session: Session, application: Application) -> bool:
    """Membership and signing permission are the caller's responsibility."""
    if application.state != "DECLINED":
        return False
    company = session.get(Company, application.company_id)
    if company.kind != "IP":
        return False
    decision = session.scalar(
        select(Decision)
        .where(Decision.application_id == application.id)
        .order_by(Decision.created_at.desc(), Decision.id.desc())
        .limit(1)
    )
    if (
        decision is None
        or decision.kind != "AUTO"
        or decision.outcome != "DECLINE"
        or datetime.now(UTC) - decision.created_at > timedelta(days=30)
    ):
        return False
    return (
        session.scalar(
            select(Objection.id)
            .where(Objection.application_id == application.id)
            .limit(1)
        )
        is None
    )


def file(
    session: Session, application_id: UUID, body: ObjectionRequest, user: User
) -> Application:
    application = locked_application(session, application_id, user)
    require_signatory(session, application, user)
    if not eligible(session, application):
        raise ApiErrorException(
            403, "OBJECTION_NOT_ALLOWED", "Пересмотр сейчас недоступен"
        )
    objection = Objection(application_id=application.id, text=body.text)
    session.add(objection)
    session.flush()
    session.add(
        ApplicationEvent(
            application_id=application.id,
            event_type="OBJECTION_FILED",
            actor_type="CLIENT",
            actor_id=user.id,
            payload={"objection_id": str(objection.id)},
            created_at=datetime.now(UTC),
        )
    )
    transition(
        session,
        application,
        "MANUAL_REVIEW",
        actor_type="CLIENT",
        actor_id=user.id,
        payload={"route_reason": "OBJECTION"},
    )
    application.version += 1
    session.commit()
    return application


def resolve(session: Session, application: Application, outcome: str) -> None:
    objection = session.scalar(
        select(Objection).where(
            Objection.application_id == application.id, Objection.resolved_at.is_(None)
        )
    )
    if objection is not None:
        objection.outcome = "REJECTED" if outcome == "DECLINE" else "UPHELD"
        objection.resolved_at = datetime.now(UTC)
