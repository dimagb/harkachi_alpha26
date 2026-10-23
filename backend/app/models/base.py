from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class Record:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def choices(column: str, *values: str) -> CheckConstraint:
    allowed = ", ".join(f"'{value}'" for value in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=f"ck_{column}")


STATES = (
    "DRAFT",
    "SUBMITTED",
    "VALIDATION",
    "INFO_REQUESTED",
    "ENRICHMENT",
    "ASSESSMENT",
    "MANUAL_REVIEW",
    "OFFER_ISSUED",
    "DECLINED",
    "SIGNING",
    "SIGNED",
    "DISBURSED",
    "WITHDRAWN",
    "EXPIRED",
)
PRODUCTS = ("EXPRESS", "WORKING_CAPITAL", "OVERDRAFT")
REASONS = (
    "SF_INACTIVE",
    "SF_BANKRUPTCY",
    "SF_AGE",
    "SF_OVERDUE",
    "SF_TAX_DEBT",
    "SF_OKVED",
    "SF_ADDITIONAL",
    "ADDITIONAL_CHECKS",
    "LOW_SCORE",
    "HIGH_LOAD",
    "UNDERWRITER_DECLINE",
    "CLIENT_REJECTED_OFFER",
    "CLIENT_WITHDREW",
    "EXPIRED_INFO",
    "EXPIRED_OFFER",
)
