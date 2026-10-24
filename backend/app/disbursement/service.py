"""Idempotent loan disbursement and integer-ruble repayment schedules."""

import calendar
import time
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.applications.state_machine import transition
from app.config import get_settings
from app.decision.scoring import annuity, rub
from app.models import Application, Disbursement, Offer
from app.pipeline.persist import event

MOSCOW = timezone(timedelta(hours=3))


def schedule(
    amount: int, rate: Decimal | int | float, term: int, issued_on: date
) -> list[dict[str, int | str]]:
    decimal_rate = Decimal(str(rate))
    payment = rub(annuity(amount, decimal_rate, term))
    rate_units = int((decimal_rate * 100).to_integral_value(rounding=ROUND_HALF_UP))
    balance = amount
    rows = []
    for number in range(1, term + 1):
        interest = (balance * rate_units + 60_000) // 120_000
        principal = balance if number == term else min(balance, payment - interest)
        balance -= principal
        year, month_index = divmod(
            issued_on.year * 12 + issued_on.month - 1 + number, 12
        )
        month = month_index + 1
        payment_date = date(
            year, month, min(issued_on.day, calendar.monthrange(year, month)[1])
        )
        rows.append(
            {
                "number": number,
                "date": payment_date.isoformat(),
                "payment": interest + principal,
                "interest": interest,
                "principal": principal,
                "balance": balance,
            }
        )
    return rows


def disburse(factory: sessionmaker[Session], application_id: UUID) -> None:
    time.sleep(get_settings().pipeline_step_delay_sec)
    with factory.begin() as session:
        application = session.scalars(
            select(Application)
            .where(Application.id == application_id)
            .with_for_update()
        ).one()
        if application.state != "SIGNED":
            return
        offer = session.get(Offer, application.current_offer_id)
        if offer.status != "ACCEPTED":
            return
        now = datetime.now(UTC)
        issued_on = now.astimezone(MOSCOW).date()
        session.add(
            Disbursement(
                application_id=application.id,
                amount=offer.amount,
                disbursed_at=now,
                schedule=None
                if offer.product_code == "OVERDRAFT"
                else schedule(offer.amount, offer.rate, offer.term_months, issued_on),
            )
        )
        transition(
            session, application, "DISBURSED", actor_type="SYSTEM", actor_id=None
        )
        event(session, application, "DISBURSED", {"amount": offer.amount})
        event(
            session,
            application,
            "BKI_REPORT",
            {
                "report": "NEW_LOAN",
                "amount": offer.amount,
                "term_months": offer.term_months,
                "rate": str(offer.rate),
                "monthly_payment": offer.monthly_payment,
                "disbursed_on": issued_on.isoformat(),
            },
        )
