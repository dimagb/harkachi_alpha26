from dataclasses import replace

import pytest

from app.decision import DEFAULT_CONFIG, decide
from app.decision.policy import apply_policy


@pytest.mark.parametrize(
    "turnover,amount,expected,offered",
    [
        (1_000_000, 400_000, "APPROVE", 400_000),
        (1_123_456, 500_000, "COUNTER", 400_000),
        (200_000, 100_000, "DECLINE", None),
    ],
)
def test_overdraft(turnover, amount, expected, offered, persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(
        inputs,
        turnover=(turnover,) * 12,
        bureau=replace(inputs.bureau, monthly_payments_total=9_000_000),
        app=replace(
            inputs.app, product_code="OVERDRAFT", amount=amount, term_months=12
        ),
    )
    outcome, offer, calc, rules = apply_policy(inputs, DEFAULT_CONFIG, "A")
    assert outcome == expected
    assert (offer.amount if offer else None) == offered
    assert calc.requested_payment is None
    assert calc.ptr_requested is None
    assert calc.steps[2].startswith("Лимит овердрафта: меньшее из ")
    assert " и " in calc.steps[2]
    assert calc.steps[2].endswith("; нагрузка не проверяется.")
    assert "min(" not in " ".join(calc.steps)
    assert all(rule.code == "HIGH_LOAD" for rule in rules)
    if offer:
        assert offer.monthly_payment is None
        assert offer.term_months == 12


def test_reduced_credit_amount_explanation_is_in_russian(persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(
        inputs,
        turnover=(1_000_000,) * 12,
        bureau=replace(inputs.bureau, monthly_payments_total=0),
        app=replace(
            inputs.app, product_code="EXPRESS", amount=2_500_000, term_months=36
        ),
    )
    outcome, offer, calc, _ = apply_policy(inputs, DEFAULT_CONFIG, "A")
    assert outcome == "COUNTER"
    assert offer.amount == 2_000_000
    assert calc.steps[-2].startswith("Сумма на 36 мес.: меньшее из 2 000 000 ₽ и ")
    assert calc.steps[-2].endswith("с округлением вниз до 50 000 ₽ = 2 000 000 ₽.")
    assert "min(" not in " ".join(calc.steps)


def test_counter_extends_term_before_reducing_amount(persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(inputs, app=replace(inputs.app, amount=2_100_000, term_months=6))
    result = decide(inputs, DEFAULT_CONFIG)
    assert result.outcome == "COUNTER"
    assert result.offer.amount == 2_100_000
    assert result.offer.term_months == 7
    assert result.grade == "A"
    assert result.what_if[0].endswith("на 6 мес.")


def test_no_free_payment_and_below_minimum(persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    for existing in (360_000, 359_999):
        changed = replace(
            inputs, bureau=replace(inputs.bureau, monthly_payments_total=existing)
        )
        outcome, offer, calc, rules = apply_policy(changed, DEFAULT_CONFIG, "A")
        assert outcome == "DECLINE"
        assert offer is None
        assert calc.max_amount < DEFAULT_CONFIG.products["EXPRESS"].min_amount
        assert rules[-1].code == "HIGH_LOAD"


def test_default_configuration_matches_reference(reference):
    cfg = DEFAULT_CONFIG
    assert cfg.key_rate == reference.KEY_RATE
    assert dict(cfg.industry) == reference.INDUSTRY
    assert cfg.okved_stop == reference.OKVED_STOP
    assert {
        code: {
            "min": p.min_amount,
            "max": p.max_amount,
            "tmin": p.min_term,
            "tmax": p.max_term,
            "k": p.k,
            "auto": p.auto_limit,
            "spread": dict(p.spreads),
        }
        for code, p in cfg.products.items()
    } == reference.PRODUCTS


def test_what_if_is_maximum_for_requested_term(persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][1])
    result = decide(inputs, DEFAULT_CONFIG)
    for amount, expected in ((1_550_000, "APPROVE"), (1_600_000, "COUNTER")):
        changed = replace(inputs, app=replace(inputs.app, amount=amount))
        outcome, _, _, _ = apply_policy(changed, DEFAULT_CONFIG, result.grade)
        assert outcome == expected
