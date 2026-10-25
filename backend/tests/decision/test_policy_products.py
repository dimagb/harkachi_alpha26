"""F11: assessment is shared; product policy changes credit conditions."""

from dataclasses import replace
from unittest.mock import Mock

import pytest

from app.decision import DEFAULT_CONFIG, decide
from app.decision.policy import apply_policy
from app.decision.scoring import score


@pytest.mark.parametrize(
    "grade,express_spread,working_spread,express_rate,working_rate",
    [("A", 8, 7, 22, 21), ("B", 10, 9, 24, 23), ("C", 12, 11, 26, 25)],
)
def test_same_grade_gets_product_spread_rate_and_turnover_limit(
    persona_data,
    build_inputs,
    grade,
    express_spread,
    working_spread,
    express_rate,
    working_rate,
):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(
        inputs,
        turnover=(1_000_000,) * 12,
        bureau=replace(inputs.bureau, monthly_payments_total=0),
        app=replace(inputs.app, amount=2_500_000, term_months=24),
    )
    for product, spread, rate, cap, outcome, amount, term in (
        ("EXPRESS", express_spread, express_rate, 2_000_000, "COUNTER", 2_000_000, 36),
        (
            "WORKING_CAPITAL",
            working_spread,
            working_rate,
            3_000_000,
            "APPROVE",
            2_500_000,
            24,
        ),
    ):
        changed = replace(inputs, app=replace(inputs.app, product_code=product))
        actual, offer, calc, _ = apply_policy(changed, DEFAULT_CONFIG, grade)
        assert actual == outcome
        assert calc.rate - DEFAULT_CONFIG.key_rate == spread
        assert calc.rate == rate
        assert calc.cap_by_turnover == cap
        assert offer.rate == rate
        assert offer.amount == amount
        assert offer.term_months == term


@pytest.mark.parametrize(
    "product,amount,state",
    [
        ("EXPRESS", 3_000_000, "OFFER_ISSUED"),
        ("EXPRESS", 3_000_001, "MANUAL_REVIEW"),
        ("WORKING_CAPITAL", 5_000_000, "OFFER_ISSUED"),
        ("WORKING_CAPITAL", 5_000_001, "MANUAL_REVIEW"),
    ],
)
def test_product_auto_limit_with_a_fixed_assessment(
    persona_data, build_inputs, monkeypatch, product, amount, state
):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(
        inputs,
        turnover=(3_000_000,) * 12,
        bureau=replace(inputs.bureau, monthly_payments_total=0),
        app=replace(
            inputs.app,
            amount=1_000_000,
            term_months=24,
            declared_revenue_year=36_000_000,
        ),
    )
    assessment = score(inputs, DEFAULT_CONFIG)
    assert assessment[1:3] == (98, "A")
    fixed_score = Mock(return_value=assessment)
    monkeypatch.setattr("app.decision.engine.score", fixed_score)
    changed = replace(
        inputs, app=replace(inputs.app, product_code=product, amount=amount)
    )
    result = decide(changed, DEFAULT_CONFIG)
    fixed_score.assert_called_once_with(changed, DEFAULT_CONFIG)
    assert result.score == assessment[1]
    assert result.grade == assessment[2]
    assert result.state == state


def test_identical_payment_and_inputs_give_identical_product_scores(
    persona_data, build_inputs
):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(
        inputs,
        turnover=(1_000_000,) * 12,
        bureau=replace(inputs.bureau, monthly_payments_total=0),
        app=replace(inputs.app, amount=1_200_000, term_months=12),
    )
    # Equal conservative rates make the actual annuity payments identical.
    products = {
        code: replace(product, spreads={**product.spreads, "C": 0})
        for code, product in DEFAULT_CONFIG.products.items()
    }
    config = replace(DEFAULT_CONFIG, key_rate=0, products=products)
    express = score(
        replace(inputs, app=replace(inputs.app, product_code="EXPRESS")), config
    )
    working = score(
        replace(inputs, app=replace(inputs.app, product_code="WORKING_CAPITAL")), config
    )
    assert express == working
    assert express[0]["payment_to_turnover"] == 10
    assert express[3] == 10.0
