"""The sole writer of application state; callers own the transaction."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.errors import ApiErrorException
from app.models import Application, ApplicationEvent

TRANSITIONS = frozenset(
    {
        ("DRAFT", "SUBMITTED", "CLIENT"),
        ("SUBMITTED", "VALIDATION", "SYSTEM"),
        ("VALIDATION", "INFO_REQUESTED", "SYSTEM"),
        ("VALIDATION", "ENRICHMENT", "SYSTEM"),
        ("INFO_REQUESTED", "VALIDATION", "CLIENT"),
        ("INFO_REQUESTED", "MANUAL_REVIEW", "CLIENT"),
        ("ENRICHMENT", "ASSESSMENT", "SYSTEM"),
        ("ENRICHMENT", "MANUAL_REVIEW", "SYSTEM"),
        ("ASSESSMENT", "OFFER_ISSUED", "SYSTEM"),
        ("ASSESSMENT", "DECLINED", "SYSTEM"),
        ("ASSESSMENT", "MANUAL_REVIEW", "SYSTEM"),
        ("MANUAL_REVIEW", "OFFER_ISSUED", "UNDERWRITER"),
        ("MANUAL_REVIEW", "DECLINED", "UNDERWRITER"),
        ("MANUAL_REVIEW", "INFO_REQUESTED", "UNDERWRITER"),
        ("MANUAL_REVIEW", "ENRICHMENT", "UNDERWRITER"),
        ("DECLINED", "MANUAL_REVIEW", "CLIENT"),
        ("OFFER_ISSUED", "SIGNING", "CLIENT"),
        ("SIGNING", "SIGNED", "CLIENT"),
        ("SIGNING", "SIGNED", "GUARANTOR"),
        ("SIGNED", "DISBURSED", "SYSTEM"),
    }
    | {
        (source, "WITHDRAWN", "CLIENT")
        for source in (
            "DRAFT",
            "SUBMITTED",
            "VALIDATION",
            "INFO_REQUESTED",
            "ENRICHMENT",
            "ASSESSMENT",
            "MANUAL_REVIEW",
            "OFFER_ISSUED",
            "SIGNING",
        )
    }
    | {
        (source, "EXPIRED", "SYSTEM")
        for source in ("INFO_REQUESTED", "OFFER_ISSUED", "SIGNING")
    }
)


def transition(
    session: Session,
    application: Application,
    to_state: str,
    *,
    actor_type: str,
    actor_id: UUID | None,
    reason_code: str | None = None,
    payload: dict[str, object] | None = None,
) -> None:
    from_state = application.state
    if (from_state, to_state, actor_type) not in TRANSITIONS:
        raise ApiErrorException(
            409, "INVALID_TRANSITION", "Действие недоступно в текущем состоянии заявки"
        )
    application.state = to_state
    session.add(
        ApplicationEvent(
            application_id=application.id,
            event_type="STATE_CHANGED",
            from_state=from_state,
            to_state=to_state,
            actor_type=actor_type,
            actor_id=actor_id,
            reason_code=reason_code,
            payload={} if payload is None else payload,
            created_at=datetime.now(UTC),
        )
    )
