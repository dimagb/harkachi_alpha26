"""Bank queue projected in one SQL query, independently of queue size."""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.models import Application, ApplicationEvent, Company, Decision
from app.schemas.api import QueueItem


def latest_auto():
    return (
        select(Decision)
        .where(Decision.kind == "AUTO")
        .ext(distinct_on(Decision.application_id))
        .order_by(
            Decision.application_id, Decision.created_at.desc(), Decision.id.desc()
        )
        .subquery()
    )


def latest_entry():
    return (
        select(ApplicationEvent)
        .where(
            ApplicationEvent.event_type == "STATE_CHANGED",
            ApplicationEvent.to_state == "MANUAL_REVIEW",
        )
        .ext(distinct_on(ApplicationEvent.application_id))
        .order_by(
            ApplicationEvent.application_id,
            ApplicationEvent.created_at.desc(),
            ApplicationEvent.id.desc(),
        )
        .subquery()
    )


def get_queue(session: Session) -> list[QueueItem]:
    auto, entry = latest_auto(), latest_entry()
    waiting = func.coalesce(entry.c.created_at, Application.updated_at)
    rows = session.execute(
        select(
            Application.id,
            Application.number,
            Company.name.label("company_name"),
            Company.kind.label("company_kind"),
            Application.product_code,
            Application.amount,
            auto.c.grade,
            func.coalesce(
                entry.c.payload["route_reason"].astext, auto.c.route_reason
            ).label("route_reason"),
            waiting.label("waiting_since"),
        )
        .join(Company, Company.id == Application.company_id)
        .outerjoin(auto, auto.c.application_id == Application.id)
        .outerjoin(entry, entry.c.application_id == Application.id)
        .where(Application.state == "MANUAL_REVIEW")
        .order_by(waiting, Application.id)
    ).mappings()
    return [
        QueueItem(
            **{
                **row,
                "id": str(row["id"]),
                "waiting_since": row["waiting_since"].isoformat(),
            }
        )
        for row in rows
    ]


def current_route(session: Session, application: Application, auto: Decision | None):
    entry = session.scalar(
        select(ApplicationEvent)
        .where(
            ApplicationEvent.application_id == application.id,
            ApplicationEvent.event_type == "STATE_CHANGED",
            ApplicationEvent.to_state == "MANUAL_REVIEW",
        )
        .order_by(ApplicationEvent.created_at.desc(), ApplicationEvent.id.desc())
        .limit(1)
    )
    route = (entry.payload or {}).get("route_reason") if entry else None
    return route or (auto.route_reason if auto else None)
