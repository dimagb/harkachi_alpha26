import importlib
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import BigInteger, Numeric, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

ROOT = Path(__file__).resolve().parents[2]
TABLES = {
    "user",
    "company",
    "company_member",
    "account_turnover",
    "risk_flag",
    "product",
    "decision_config",
    "reason_catalog",
    "application",
    "party",
    "consent",
    "info_request",
    "external_check",
    "decision",
    "offer",
    "signature",
    "disbursement",
    "objection",
    "application_event",
    "job",
    "otp",
}


def metadata():
    importlib.import_module("app.models")
    from app.db import Base

    return Base.metadata


def reason_codes():
    codes = (ROOT / "contracts/codes.md").read_text(encoding="utf-8")
    section = codes.split("## Коды причин", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"`([A-Z_]+)`", section))


def test_all_documented_tables_and_columns_are_mapped():
    tables = metadata().tables
    assert set(tables) == TABLES
    document = (ROOT / "docs/data-model.md").read_text(encoding="utf-8")
    for line in document.splitlines():
        match = re.match(r"\| `([a-z_]+)` \| (.*?) \|", line)
        if not match:
            continue
        table, fields = match.groups()
        columns = {
            re.sub(r"\*", "", field).strip().split(" ")[0]
            for field in re.sub(r"\([^)]*\)", "", fields).split(", ")
        }
        assert columns | {"id", "created_at", "updated_at"} <= set(
            tables[table].c.keys()
        )
    for table in tables.values():
        assert table.c.id.primary_key
        assert table.c.created_at.type.timezone
        assert table.c.updated_at.type.timezone
    for table, column in [
        ("application", "amount"),
        ("application", "declared_revenue_year"),
        ("offer", "amount"),
        ("offer", "monthly_payment"),
        ("disbursement", "amount"),
        ("account_turnover", "credit_turnover"),
    ]:
        assert isinstance(tables[table].c[column].type, BigInteger)
    for table, column in [("offer", "rate"), ("decision_config", "key_rate")]:
        rate = tables[table].c[column].type
        assert isinstance(rate, Numeric)
        assert (rate.precision, rate.scale) == (5, 2)


def test_password_hash_is_salted_and_verifiable():
    security = importlib.import_module("app.security")
    first = security.hash_password("пароль-123")
    second = security.hash_password("пароль-123")
    assert first != second
    assert "пароль-123" not in first
    assert security.verify_password("пароль-123", first)
    assert not security.verify_password("не тот пароль", first)
    assert not security.verify_password("пароль-123", "corrupted-hash")


def test_contracts_dir_defaults_to_repository(monkeypatch):
    from app.config import Settings

    monkeypatch.delenv("CONTRACTS_DIR", raising=False)
    assert Settings(_env_file=None).contracts_dir == ROOT / "contracts"
    monkeypatch.setenv("CONTRACTS_DIR", str(ROOT))
    assert Settings(_env_file=None).contracts_dir == ROOT


def test_seed_data_and_idempotency(migrated_database):
    from app.models import (
        AccountTurnover,
        Company,
        CompanyMember,
        DecisionConfig,
        Product,
        ReasonCatalog,
        RiskFlag,
        User,
    )
    from app.security import verify_password

    engine, run = migrated_database
    models = [
        Company,
        User,
        CompanyMember,
        AccountTurnover,
        RiskFlag,
        Product,
        DecisionConfig,
        ReasonCatalog,
    ]
    with Session(engine) as session:
        before = [session.scalar(select(func.count()).select_from(m)) for m in models]
        assert before == [6, 8, 7, 72, 6, 3, 1, 15]
        member = session.scalar(
            select(CompanyMember).join(User).where(User.login == "ooo_load_accountant")
        )
        assert member.can_sign is False
        assert set(session.scalars(select(ReasonCatalog.code))) == reason_codes()
        assert (
            session.scalar(
                select(ReasonCatalog.client_visible).where(
                    ReasonCatalog.code == "SF_ADDITIONAL"
                )
            )
            is False
        )
        for user in session.scalars(select(User)):
            assert verify_password("b03-test-password", user.password_hash)
        hashes = dict(session.execute(select(User.login, User.password_hash)).all())
        config = session.scalar(select(DecisionConfig))
        assert config.version == 1 and config.active
        assert config.key_rate == Decimal("14.00")
        assert config.key_rate_date == date(2026, 10, 23)
        assert config.params == {
            "products": {
                "EXPRESS": {
                    "min": 300000,
                    "max": 5000000,
                    "tmin": 6,
                    "tmax": 36,
                    "k": 2,
                    "auto": 3000000,
                    "spread": {"A": 8, "B": 10, "C": 12},
                },
                "WORKING_CAPITAL": {
                    "min": 500000,
                    "max": 15000000,
                    "tmin": 3,
                    "tmax": 24,
                    "k": 3,
                    "auto": 5000000,
                    "spread": {"A": 7, "B": 9, "C": 11},
                },
                "OVERDRAFT": {
                    "min": 100000,
                    "max": 5000000,
                    "tmin": 12,
                    "tmax": 12,
                    "k": 0.4,
                    "auto": 5000000,
                    "spread": {"A": 10, "B": 12, "C": 14},
                },
            },
            "industry": {
                "52": "low",
                "62": "low",
                "69": "low",
                "56": "mid",
                "47": "mid",
                "43": "mid",
                "46": "mid",
                "33": "mid",
                "41": "high",
                "01": "high",
            },
            "okved_stop": ["92", "64.9"],
            "stop": {
                "max_dpd_12m": 60,
                "tax_debt": 50000,
                "enforcement_sum": 100000,
                "min_age_months": 6,
            },
            "validation": {"revenue_mismatch": 0.4},
            "grades": {"A": 75, "B": 60, "C": 45},
            "policy": {
                "free_payment_share": 0.3,
                "counter_round": 50000,
                "overdraft_payment_share": 0.1,
            },
        }
        for product in session.scalars(select(Product)):
            assert product.params == config.params["products"][product.code]
        codes = (ROOT / "contracts/codes.md").read_text("utf-8")
        section = codes.split("## Клиентские тексты причин", 1)[1].split("\n## ", 1)[0]
        for line in section.splitlines():
            if not line.startswith("| `"):
                continue
            code, client_text, action = [
                part.strip().replace("`", "") for part in line.split("|")[1:4]
            ]
            reason = session.scalar(
                select(ReasonCatalog).where(ReasonCatalog.code == code)
            )
            assert reason.client_text == client_text
            assert reason.client_action == (None if action == "—" else action)
            assert reason.client_visible == (code != "SF_ADDITIONAL")
        assert (
            session.scalar(
                select(ReasonCatalog.client_category).where(
                    ReasonCatalog.code == "UNDERWRITER_DECLINE"
                )
            )
            is None
        )
        personas = json.loads((ROOT / "contracts/personas.json").read_text("utf-8"))
        for persona in personas["personas"]:
            company = session.scalar(
                select(Company).where(Company.inn == persona["inn"])
            )
            turnover = session.execute(
                select(AccountTurnover.month, AccountTurnover.credit_turnover)
                .where(AccountTurnover.company_id == company.id)
                .order_by(AccountTurnover.month)
            ).all()
            assert [row[0] for row in turnover] == [
                "2025-10",
                "2025-11",
                "2025-12",
                "2026-01",
                "2026-02",
                "2026-03",
                "2026-04",
                "2026-05",
                "2026-06",
                "2026-07",
                "2026-08",
                "2026-09",
            ]
            assert [row[1] for row in turnover] == persona["turnover"]
            risk = session.scalar(
                select(RiskFlag).where(RiskFlag.company_id == company.id)
            )
            assert (risk.aml_flag, risk.fraud_flag, risk.note) == (
                persona["risk"]["aml_flag"],
                persona["risk"]["fraud_flag"],
                persona["risk"]["note"],
            )
    run("-m", "app.seed")
    with Session(engine) as session:
        assert [
            session.scalar(select(func.count()).select_from(m)) for m in models
        ] == before
        assert (
            dict(session.execute(select(User.login, User.password_hash)).all())
            == hashes
        )


def test_migration_matches_models_and_indexes(migrated_database):
    engine, _ = migrated_database
    with engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) == TABLES | {
            "alembic_version"
        }
        assert (
            compare_metadata(MigrationContext.configure(connection), metadata()) == []
        )
        for table, columns in [
            ("application", ["company_id", "state"]),
            ("application_event", ["application_id", "created_at"]),
            ("job", ["status", "run_after"]),
        ]:
            assert columns in [
                i["column_names"] for i in inspect(connection).get_indexes(table)
            ]
        for table in metadata().tables.values():
            expected = {
                constraint.name: set(re.findall(r"'([^']+)'", str(constraint.sqltext)))
                for constraint in table.constraints
                if hasattr(constraint, "sqltext")
            }
            actual = {
                constraint["name"]: set(re.findall(r"'([^']+)'", constraint["sqltext"]))
                for constraint in inspect(connection).get_check_constraints(table.name)
            }
            assert actual == expected


def test_service_enumerations_are_constrained():
    from sqlalchemy import CheckConstraint

    tables = metadata().tables
    for table, column, values in [
        (
            "job",
            "step",
            {
                "VALIDATION",
                "ENRICHMENT",
                "ASSESSMENT",
                "DISBURSEMENT",
                "EXPIRY_CHECK",
                "BACKGROUND_LOAD",
            },
        ),
        ("job", "status", {"PENDING", "RUNNING", "DONE", "FAILED"}),
        ("external_check", "status", {"PENDING", "OK", "FAILED"}),
        (
            "application_event",
            "actor_type",
            {"CLIENT", "UNDERWRITER", "GUARANTOR", "SYSTEM"},
        ),
        ("objection", "outcome", {"UPHELD", "REJECTED"}),
        ("decision", "grade", {"A", "B", "C", "D"}),
    ]:
        constraints = {
            c.name: c
            for c in tables[table].constraints
            if isinstance(c, CheckConstraint)
        }
        assert f"ck_{column}" in constraints
        assert (
            set(re.findall(r"'([^']+)'", str(constraints[f"ck_{column}"].sqltext)))
            == values
        )


def test_number_and_optimistic_locking(migrated_database):
    from app.models import Application, Company, User

    engine, _ = migrated_database
    with Session(engine) as session:
        application = Application(
            company_id=session.scalar(select(Company.id).limit(1)),
            created_by=session.scalar(
                select(User.id).where(User.role == "CLIENT").limit(1)
            ),
            product_code="EXPRESS",
            amount=500000,
            term_months=12,
            purpose="WORKING_CAPITAL",
            declared_revenue_year=6000000,
        )
        session.add(application)
        session.commit()
        assert application.number == 1001
        assert application.version == 1 and application.state == "DRAFT"
        identifier = application.id
    with Session(engine) as first, Session(engine) as second:
        current = first.get(Application, identifier)
        stale = second.get(Application, identifier)
        current.amount = 600000
        first.commit()
        assert current.version == 2
        stale.amount = 700000
        with pytest.raises(StaleDataError):
            second.commit()


def test_database_rejects_invalid_enums_and_foreign_keys(migrated_database):
    from app.models import Application, User

    engine, _ = migrated_database
    with Session(engine) as session:
        user = session.scalar(select(User).limit(1))
        user.role = "NOT_A_ROLE"
        with pytest.raises(IntegrityError):
            session.commit()
    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "UPDATE company_member SET company_id = "
                    "'00000000-0000-0000-0000-000000000000'"
                )
            )
    assert Application.__mapper__.version_id_col is Application.__table__.c.version
