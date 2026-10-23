from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import PRODUCTS, REASONS, STATES, Record, choices


class Application(Record, Base):
    __tablename__ = "application"
    __table_args__ = (
        choices("state", *STATES),
        choices("product_code", *PRODUCTS),
        choices("purpose", "WORKING_CAPITAL", "CASH_GAP", "EQUIPMENT", "OTHER"),
        Index("ix_application_company_state", "company_id", "state"),
    )
    number: Mapped[int] = mapped_column(BigInteger, Identity(start=1001), unique=True)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("company.id"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("user.id"))
    product_code: Mapped[str] = mapped_column(ForeignKey("product.code"))
    amount: Mapped[int] = mapped_column(BigInteger)
    term_months: Mapped[int]
    purpose: Mapped[str] = mapped_column(String(30))
    purpose_text: Mapped[str | None] = mapped_column(Text)
    declared_revenue_year: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(
        String(30), default="DRAFT", server_default="DRAFT"
    )
    current_offer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("offer.id", name="fk_application_current_offer", use_alter=True)
    )
    previous_application_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("application.id")
    )
    awaiting_signature: Mapped[bool] = mapped_column(default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    __mapper_args__ = {"version_id_col": version}


class Party(Record, Base):
    __tablename__ = "party"
    __table_args__ = (
        choices("role", "BORROWER_SIGNATORY", "GUARANTOR"),
        choices("status", "PENDING", "SIGNED"),
    )
    application_id: Mapped[UUID] = mapped_column(ForeignKey("application.id"))
    role: Mapped[str] = mapped_column(String(30))
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("user.id"))
    full_name: Mapped[str] = mapped_column(Text)
    required_signature: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")


class Consent(Record, Base):
    __tablename__ = "consent"
    __table_args__ = (choices("type", "PDN", "BKI", "AUTO_DECISION"),)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("application.id"))
    party_id: Mapped[UUID] = mapped_column(ForeignKey("party.id"))
    type: Mapped[str] = mapped_column(String(20))
    granted: Mapped[bool]
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    doc_hash: Mapped[str | None] = mapped_column(Text)


class InfoRequest(Record, Base):
    __tablename__ = "info_request"
    __table_args__ = (choices("source", "SYSTEM", "UNDERWRITER"),)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("application.id"))
    source: Mapped[str] = mapped_column(String(20))
    items: Mapped[list[object]] = mapped_column(JSONB)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    response: Mapped[list[object] | None] = mapped_column(JSONB)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExternalCheck(Record, Base):
    __tablename__ = "external_check"
    __table_args__ = (
        choices("source", "BKI", "EGRUL", "FNS"),
        choices("status", "PENDING", "OK", "FAILED"),
    )
    application_id: Mapped[UUID] = mapped_column(ForeignKey("application.id"))
    source: Mapped[str] = mapped_column(String(20))
    request: Mapped[dict[str, object]] = mapped_column(JSONB)
    response: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30))
    attempts: Mapped[int] = mapped_column(default=0)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Decision(Record, Base):
    __tablename__ = "decision"
    __table_args__ = (
        choices("kind", "AUTO", "MANUAL"),
        choices("grade", "A", "B", "C", "D"),
        choices(
            "outcome",
            "APPROVE",
            "COUNTER",
            "DECLINE",
            "MANUAL",
            "REQUEST_INFO",
            "RETRY_ENRICHMENT",
        ),
        choices(
            "route_reason",
            "GRADE_C",
            "AMOUNT_ABOVE_AUTO",
            "NO_AUTO_CONSENT",
            "SOURCE_UNAVAILABLE",
            "OBJECTION",
            "INFO_RESPONSE",
        ),
        choices("client_reason_code", *(r for r in REASONS if r != "SF_ADDITIONAL")),
    )
    application_id: Mapped[UUID] = mapped_column(ForeignKey("application.id"))
    kind: Mapped[str] = mapped_column(String(20))
    outcome: Mapped[str] = mapped_column(String(30))
    route_reason: Mapped[str | None] = mapped_column(String(30))
    grade: Mapped[str | None] = mapped_column(String(1))
    score: Mapped[int | None]
    factors: Mapped[list[object]] = mapped_column(JSONB)
    rules_fired: Mapped[list[object]] = mapped_column(JSONB)
    internal_reasons: Mapped[list[object]] = mapped_column(JSONB)
    client_reason_code: Mapped[str | None] = mapped_column(
        ForeignKey("reason_catalog.code")
    )
    recommendation: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    policy: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    what_if: Mapped[list[object]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    config_version: Mapped[int] = mapped_column(ForeignKey("decision_config.version"))
    inputs_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB)
    made_by: Mapped[UUID | None] = mapped_column(ForeignKey("user.id"))
    comment: Mapped[str | None] = mapped_column(Text)


class Offer(Record, Base):
    __tablename__ = "offer"
    __table_args__ = (
        choices("kind", "APPROVED", "COUNTER"),
        choices("product_code", *PRODUCTS),
        choices("status", "ACTIVE", "ACCEPTED", "REJECTED", "EXPIRED", "SUPERSEDED"),
        UniqueConstraint("application_id", "version"),
    )
    application_id: Mapped[UUID] = mapped_column(ForeignKey("application.id"))
    version: Mapped[int] = mapped_column(default=1)
    kind: Mapped[str] = mapped_column(String(20))
    product_code: Mapped[str] = mapped_column(ForeignKey("product.code"))
    amount: Mapped[int] = mapped_column(BigInteger)
    term_months: Mapped[int]
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    monthly_payment: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Signature(Record, Base):
    __tablename__ = "signature"
    __table_args__ = (choices("object_type", "CONSENT", "OFFER", "GUARANTEE"),)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("application.id"))
    party_id: Mapped[UUID] = mapped_column(ForeignKey("party.id"))
    object_type: Mapped[str] = mapped_column(String(20))
    object_id: Mapped[UUID]
    doc_hash: Mapped[str] = mapped_column(Text)
    otp_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Disbursement(Record, Base):
    __tablename__ = "disbursement"
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("application.id"), unique=True
    )
    amount: Mapped[int] = mapped_column(BigInteger)
    disbursed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    schedule: Mapped[list[object] | None] = mapped_column(JSONB)


class Objection(Record, Base):
    __tablename__ = "objection"
    __table_args__ = (choices("outcome", "UPHELD", "REJECTED"),)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("application.id"))
    text: Mapped[str] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(30))


class ApplicationEvent(Record, Base):
    __tablename__ = "application_event"
    __table_args__ = (
        choices("from_state", *STATES),
        choices("to_state", *STATES),
        choices(
            "event_type",
            "STATE_CHANGED",
            "SIGNATURE_REQUESTED",
            "CONSENT_SIGNED",
            "CHECK_REQUESTED",
            "CHECK_RECEIVED",
            "CHECK_FAILED",
            "DECISION_MADE",
            "OFFER_ISSUED",
            "OFFER_ACCEPTED",
            "SIGNED",
            "DISBURSED",
            "BKI_REPORT",
            "OBJECTION_FILED",
            "UNDERWRITER_OVERRIDE",
        ),
        choices("reason_code", *REASONS),
        choices("actor_type", "CLIENT", "UNDERWRITER", "GUARANTOR", "SYSTEM"),
        Index(
            "ix_application_event_application_created", "application_id", "created_at"
        ),
    )
    application_id: Mapped[UUID] = mapped_column(ForeignKey("application.id"))
    from_state: Mapped[str | None] = mapped_column(String(30))
    to_state: Mapped[str | None] = mapped_column(String(30))
    event_type: Mapped[str] = mapped_column(String(30))
    actor_type: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("user.id"))
    reason_code: Mapped[str | None] = mapped_column(ForeignKey("reason_catalog.code"))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)


class Job(Record, Base):
    __tablename__ = "job"
    __table_args__ = (
        Index("ix_job_status_run_after", "status", "run_after"),
        choices(
            "step",
            "VALIDATION",
            "ENRICHMENT",
            "ASSESSMENT",
            "DISBURSEMENT",
            "EXPIRY_CHECK",
            "BACKGROUND_LOAD",
        ),
        choices("status", "PENDING", "RUNNING", "DONE", "FAILED"),
    )
    application_id: Mapped[UUID] = mapped_column(ForeignKey("application.id"))
    step: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    attempts: Mapped[int] = mapped_column(default=0)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class Otp(Record, Base):
    __tablename__ = "otp"
    __table_args__ = (choices("purpose", "CONSENTS", "OFFER", "GUARANTEE"),)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("application.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))
    party_id: Mapped[UUID | None] = mapped_column(ForeignKey("party.id"))
    purpose: Mapped[str] = mapped_column(String(20))
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
