from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import PRODUCTS, REASONS, Record, choices


class User(Record, Base):
    __tablename__ = "user"
    __table_args__ = (choices("role", "CLIENT", "UNDERWRITER", "GUARANTOR"),)
    login: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30))
    full_name: Mapped[str] = mapped_column(Text)


class Company(Record, Base):
    __tablename__ = "company"
    __table_args__ = (choices("kind", "IP", "OOO"),)
    inn: Mapped[str] = mapped_column(String(12), unique=True)
    ogrn: Mapped[str] = mapped_column(String(15))
    kind: Mapped[str] = mapped_column(String(3))
    name: Mapped[str] = mapped_column(Text)
    okved_main: Mapped[str] = mapped_column(String(20))
    reg_date: Mapped[date]
    address: Mapped[str] = mapped_column(Text)


class CompanyMember(Record, Base):
    __tablename__ = "company_member"
    __table_args__ = (UniqueConstraint("user_id", "company_id"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("company.id"))
    position: Mapped[str] = mapped_column(Text)
    can_sign: Mapped[bool] = mapped_column(default=False)
    is_founder: Mapped[bool] = mapped_column(default=False)
    share_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)


class AccountTurnover(Record, Base):
    __tablename__ = "account_turnover"
    __table_args__ = (UniqueConstraint("company_id", "month"),)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("company.id"))
    month: Mapped[str] = mapped_column(String(7))
    credit_turnover: Mapped[int] = mapped_column(BigInteger)


class RiskFlag(Record, Base):
    __tablename__ = "risk_flag"
    company_id: Mapped[UUID] = mapped_column(ForeignKey("company.id"), unique=True)
    aml_flag: Mapped[bool] = mapped_column(default=False)
    fraud_flag: Mapped[bool] = mapped_column(default=False)
    note: Mapped[str | None] = mapped_column(Text)


class Product(Record, Base):
    __tablename__ = "product"
    __table_args__ = (choices("code", *PRODUCTS),)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    params: Mapped[dict[str, object]] = mapped_column(JSONB)


class DecisionConfig(Record, Base):
    __tablename__ = "decision_config"
    version: Mapped[int] = mapped_column(unique=True)
    key_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    key_rate_date: Mapped[date]
    params: Mapped[dict[str, object]] = mapped_column(JSONB)
    active: Mapped[bool] = mapped_column(default=False)


class ReasonCatalog(Record, Base):
    __tablename__ = "reason_catalog"
    __table_args__ = (choices("code", *REASONS),)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    client_category: Mapped[str | None] = mapped_column(Text)
    client_text: Mapped[str] = mapped_column(Text)
    client_action: Mapped[str | None] = mapped_column(Text)
    client_visible: Mapped[bool]
    bki_reason_code: Mapped[str | None] = mapped_column(Text)
