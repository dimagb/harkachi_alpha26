import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

from app.decision.models import (
    AppParams,
    BureauSummary,
    CompanyFacts,
    DecisionInputs,
    RiskFlags,
    TaxCheck,
)

CONTRACTS = Path(__file__).resolve().parents[3] / "contracts"


@pytest.fixture(scope="session")
def persona_data():
    return json.loads((CONTRACTS / "personas.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def reference():
    spec = importlib.util.spec_from_file_location(
        "decision_reference", CONTRACTS / "decision_reference.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def build_inputs(persona_data):
    def build(persona, app=None, consents=None, answered=(), as_of=None):
        app = persona["demo"]["app"] if app is None else app
        consents = persona["demo"]["consents"] if consents is None else consents
        fns = persona["fns"]
        return DecisionInputs(
            company=CompanyFacts(
                kind=persona["kind"],
                status=persona["status"],
                reg_date=date.fromisoformat(persona["reg_date"]),
                okved_main=persona["okved_main"],
                mass_director=fns["mass_director"],
                mass_address=fns["mass_address"],
            ),
            bureau=BureauSummary(**persona["bki"]["summary"]),
            tax=TaxCheck(
                **{
                    key: fns[key]
                    for key in (
                        "tax_debt",
                        "enforcement_sum",
                        "arbitration_defendant_sum",
                        "bankruptcy",
                    )
                }
            ),
            risk=RiskFlags(
                **{key: persona["risk"][key] for key in ("aml_flag", "fraud_flag")}
            ),
            app=AppParams(
                product_code=app["product"],
                amount=app["amount"],
                term_months=app["term"],
                purpose=app["purpose"],
                purpose_text=app.get("purpose_text"),
                declared_revenue_year=app["declared_revenue_year"],
            ),
            turnover=tuple(persona["turnover"]),
            auto_decision_consent=consents.get("auto_decision", False),
            answered_items=frozenset(answered),
            as_of=as_of or date.fromisoformat(persona_data["_meta"]["as_of"]),
        )

    return build
