"""Client offer actions, serialized by the application row lock."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.applications.state_machine import transition
from app.errors import ApiErrorException
from app.models import Application, ApplicationEvent, Offer, User
from app.schemas.api import AcceptOfferRequest
from app.signing.otp import locked_application, require_signatory, require_state


def accept(
    session: Session, application_id: UUID, body: AcceptOfferRequest, user: User
) -> Application:
    application = locked_application(session, application_id, user)
    require_signatory(session, application, user)
    require_state(application, "OFFER_ISSUED")
    offer = session.get(Offer, application.current_offer_id)
    if body.offer_version != offer.version:
        raise ApiErrorException(
            409, "CONFLICT_VERSION", "Условия изменились — проверьте их ещё раз"
        )
    now = datetime.now(UTC)
    if offer.status == "EXPIRED" or offer.expires_at <= now:
        raise ApiErrorException(409, "OFFER_EXPIRED", "Срок предложения истёк")
    offer.status = "ACCEPTED"
    transition(session, application, "SIGNING", actor_type="CLIENT", actor_id=user.id)
    session.add(
        ApplicationEvent(
            application_id=application.id,
            event_type="OFFER_ACCEPTED",
            actor_type="CLIENT",
            actor_id=user.id,
            payload={"offer_id": str(offer.id), "version": offer.version},
            created_at=now,
        )
    )
    application.version += 1
    session.commit()
    return application


def reject(session: Session, application_id: UUID, user: User) -> Application:
    application = locked_application(session, application_id, user)
    require_signatory(session, application, user)
    require_state(application, "OFFER_ISSUED")
    session.get(Offer, application.current_offer_id).status = "REJECTED"
    transition(
        session,
        application,
        "WITHDRAWN",
        actor_type="CLIENT",
        actor_id=user.id,
        reason_code="CLIENT_REJECTED_OFFER",
    )
    application.version += 1
    session.commit()
    return application


def withdraw(session: Session, application_id: UUID, user: User) -> Application:
    application = locked_application(session, application_id, user)
    require_state(
        application,
        "DRAFT",
        "SUBMITTED",
        "VALIDATION",
        "ENRICHMENT",
        "INFO_REQUESTED",
        "ASSESSMENT",
        "MANUAL_REVIEW",
        "OFFER_ISSUED",
        "SIGNING",
    )
    if application.state != "DRAFT":
        require_signatory(session, application, user)
    if application.current_offer_id is not None:
        offer = session.get(Offer, application.current_offer_id)
        if offer.status in {"ACTIVE", "ACCEPTED"}:
            offer.status = "REJECTED"
    transition(
        session,
        application,
        "WITHDRAWN",
        actor_type="CLIENT",
        actor_id=user.id,
        reason_code="CLIENT_WITHDREW",
    )
    application.version += 1
    session.commit()
    return application
