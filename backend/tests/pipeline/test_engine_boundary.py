from datetime import date

from app import decision
from app.decision.models import AppParams


def test_validation_public_rule_closes_after_answer():
    app = AppParams("EXPRESS", 1_000_000, 24, "OTHER", None, 48_000_000)
    assert (
        decision.validation_rule(
            app, (1_500_000,) * 12, frozenset(), decision.DEFAULT_CONFIG
        )
        == "VAL_REVENUE_MISMATCH"
    )
    assert (
        decision.validation_rule(
            app,
            (1_500_000,) * 12,
            frozenset({"REVENUE_CONFIRM"}),
            decision.DEFAULT_CONFIG,
        )
        == "VAL_PURPOSE_UNCLEAR"
    )
    assert (
        decision.validation_rule(
            app,
            (1_500_000,) * 12,
            frozenset({"REVENUE_CONFIRM", "PURPOSE_DETAILS"}),
            decision.DEFAULT_CONFIG,
        )
        is None
    )


def test_eligible_date_uses_first_day_of_eligible_month():
    assert decision.eligible_date(date(2025, 8, 31), decision.DEFAULT_CONFIG) == date(
        2026, 2, 1
    )
