"""Locked, transactional deadline expiry and cumulative demo time shifts."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.applications.state_machine import transition
from app.config import get_settings
from app.errors import ApiErrorException
from app.models import Application, Consent, InfoRequest, Offer
from app.schemas.api import TimeShiftResponse
from app.signing.otp import _uuid

logger = logging.getLogger(__name__)


def expire_application(session: Session, application: Application) -> bool:
    """The caller holds the application lock and owns the transaction."""
    now = datetime.now(UTC)
    if application.state == "INFO_REQUESTED":
        overdue = session.scalar(
            select(InfoRequest.id)
            .where(
                InfoRequest.application_id == application.id,
                InfoRequest.responded_at.is_(None),
                InfoRequest.due_at <= now,
            )
            .limit(1)
        )
        if overdue is None:
            return False
        reason = "EXPIRED_INFO"
    elif application.state in {"OFFER_ISSUED", "SIGNING"}:
        offer = (
            session.get(Offer, application.current_offer_id)
            if application.current_offer_id
            else None
        )
        if offer is None or offer.expires_at > now:
            return False
        offer.status = "EXPIRED"
        reason = "EXPIRED_OFFER"
    else:
        return False
    transition(
        session,
        application,
        "EXPIRED",
        actor_type="SYSTEM",
        actor_id=None,
        reason_code=reason,
    )
    application.version += 1
    return True


def expire_due(factory: sessionmaker[Session]) -> int:
    now = datetime.now(UTC)
    due_info = (
        select(InfoRequest.id)
        .where(
            InfoRequest.application_id == Application.id,
            InfoRequest.responded_at.is_(None),
            InfoRequest.due_at <= now,
        )
        .exists()
    )
    due_offer = (
        select(Offer.id)
        .where(
            Offer.id == Application.current_offer_id,
            Offer.expires_at <= now,
        )
        .exists()
    )
    with factory() as session:
        candidates = list(
            session.scalars(
                select(Application.id)
                .where(
                    or_(
                        and_(Application.state == "INFO_REQUESTED", due_info),
                        and_(
                            Application.state.in_(("OFFER_ISSUED", "SIGNING")),
                            due_offer,
                        ),
                    )
                )
                .order_by(Application.id)
            )
        )
    expired = 0
    skipped_locked = 0
    for identity in candidates:
        try:
            with factory.begin() as session:
                application = session.scalar(
                    select(Application)
                    .where(Application.id == identity)
                    .with_for_update(skip_locked=True, of=Application)
                )
                if application is None:
                    skipped_locked += 1
                    continue
                changed = expire_application(session, application)
            expired += int(changed)
        except Exception as error:
            logger.error(
                "Application %s expiry failed: %s", identity, type(error).__name__
            )
    logger.debug("Expiry skipped locked applications: %s", skipped_locked)
    return expired


def time_shift(session: Session, application_id: str, days: int) -> TimeShiftResponse:
    if not get_settings().demo_mode:
        raise ApiErrorException(404, "NOT_FOUND", "Действие не найдено")
    identity = _uuid(application_id)
    if identity is None:
        raise ApiErrorException(404, "NOT_FOUND", "Заявка не найдена")
    application = session.scalar(
        select(Application)
        .where(Application.id == identity)
        .with_for_update(of=Application)
        .execution_options(populate_existing=True)
    )
    if application is None:
        raise ApiErrorException(404, "NOT_FOUND", "Заявка не найдена")
    if application.state not in {"INFO_REQUESTED", "OFFER_ISSUED", "SIGNING"}:
        raise ApiErrorException(
            409, "INVALID_TRANSITION", "Действие недоступно в текущем состоянии заявки"
        )
    delta = timedelta(days=days)
    for request in session.scalars(
        select(InfoRequest).where(
            InfoRequest.application_id == identity, InfoRequest.responded_at.is_(None)
        )
    ):
        request.due_at -= delta
    if application.current_offer_id:
        offer = session.get(Offer, application.current_offer_id)
        if offer is not None:
            offer.expires_at -= delta
    for consent in session.scalars(
        select(Consent).where(
            Consent.application_id == identity, Consent.expires_at.is_not(None)
        )
    ):
        consent.expires_at -= delta
    expired_now = expire_application(session, application)
    response = TimeShiftResponse(
        application_id=str(application.id),
        expired_now=expired_now,
        state=application.state,
    )
    session.commit()
    return response
