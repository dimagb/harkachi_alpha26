import json
import os
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import Base
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
from app.models.base import PRODUCTS, REASONS


@pytest.fixture(scope="session")
def persona_data():
    return json.loads(
        (Path(__file__).resolve().parents[3] / "contracts/personas.json").read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture
def pipeline_factory(migrated_database, monkeypatch, persona_data):
    # Separate schema: real commits and concurrent connections, no shared app data.
    url = os.environ["TEST_DATABASE_URL"]
    schema = f"pipeline_{uuid4().hex}"
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    settings = get_settings()
    monkeypatch.setattr(settings, "pipeline_step_delay_sec", 0, raising=False)
    monkeypatch.setattr(settings, "source_retry_pause_sec", 0, raising=False)
    with factory.begin() as session:
        session.add_all(
            [
                Product(code=code, name=code, description="Демо", params={})
                for code in PRODUCTS
            ]
        )
        session.add_all(
            [
                ReasonCatalog(code=code, client_text="Причина", client_visible=True)
                for code in REASONS
            ]
        )
        session.add(
            DecisionConfig(
                version=1,
                key_rate=14,
                key_rate_date=date(2026, 10, 23),
                params={},
                active=True,
            )
        )
        for persona in persona_data["personas"]:
            company = Company(
                **{
                    key: date.fromisoformat(persona[key])
                    if key == "reg_date"
                    else persona[key]
                    for key in (
                        "inn",
                        "ogrn",
                        "kind",
                        "name",
                        "okved_main",
                        "reg_date",
                        "address",
                    )
                }
            )
            session.add(company)
            session.flush()
            session.add(RiskFlag(company_id=company.id, **persona["risk"]))
            for index, amount in enumerate(persona["turnover"]):
                session.add(
                    AccountTurnover(
                        company_id=company.id,
                        month=f"{2025 + (index + 9) // 12}-{(index + 9) % 12 + 1:02}",
                        credit_turnover=amount,
                    )
                )
            for record in persona["users"]:
                user = User(
                    login=record["login"],
                    password_hash="unused",
                    role=record["role"],
                    full_name=record["full_name"],
                )
                session.add(user)
                session.flush()
                session.add(
                    CompanyMember(
                        user_id=user.id,
                        company_id=company.id,
                        **{
                            key: record[key]
                            for key in (
                                "position",
                                "can_sign",
                                "is_founder",
                                "share_pct",
                            )
                        },
                    )
                )
    try:
        yield factory
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
