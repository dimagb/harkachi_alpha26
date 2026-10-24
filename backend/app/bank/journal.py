"""Bank journal projected with a total and page in one SQL statement."""

from sqlalchemy import case, func, select, true
from sqlalchemy.orm import Session

from app.models import Application, Company
from app.schemas.api import ApplicationState, BankListItem, Page
from app.underwriting.queue import entry_route, latest_auto, latest_entry


def list_applications(
    session: Session, state: ApplicationState | None, page: int, size: int
) -> Page[BankListItem]:
    filters = () if state is None else (Application.state == state,)
    offset = (page - 1) * size
    if offset > 2**63 - 1:
        total = session.scalar(
            select(func.count()).select_from(Application).where(*filters)
        )
        return Page[BankListItem](items=[], total=total, page=page, size=size)
    auto, entry = latest_auto(), latest_entry()
    manual = Application.state == "MANUAL_REVIEW"
    total = (
        select(func.count().label("total"))
        .select_from(Application)
        .where(*filters)
        .subquery()
    )
    entries = (
        select(
            Application.id,
            Application.number,
            Company.name.label("company_name"),
            Company.kind.label("company_kind"),
            Application.product_code,
            Application.amount,
            auto.c.grade,
            case(
                (
                    manual,
                    entry_route(entry, auto),
                ),
                else_=auto.c.route_reason,
            ).label("route_reason"),
            case(
                (manual, func.coalesce(entry.c.created_at, Application.updated_at)),
                else_=None,
            ).label("waiting_since"),
            Application.state,
            Application.updated_at,
        )
        .join(Company, Company.id == Application.company_id)
        .outerjoin(auto, auto.c.application_id == Application.id)
        .outerjoin(entry, entry.c.application_id == Application.id)
        .where(*filters)
        .order_by(Application.updated_at.desc(), Application.id)
        .offset(offset)
        .limit(size)
        .subquery()
    )
    rows = list(
        session.execute(
            select(total.c.total, *entries.c)
            .select_from(total.outerjoin(entries, true()))
            .order_by(entries.c.updated_at.desc(), entries.c.id)
        ).mappings()
    )
    items = []
    for row in rows:
        if row["id"] is None:
            continue
        values = {key: value for key, value in row.items() if key != "total"}
        values["id"] = str(row["id"])
        values["updated_at"] = row["updated_at"].isoformat()
        values["waiting_since"] = (
            row["waiting_since"].isoformat() if row["waiting_since"] else None
        )
        items.append(BankListItem(**values))
    return Page[BankListItem](items=items, total=rows[0]["total"], page=page, size=size)
