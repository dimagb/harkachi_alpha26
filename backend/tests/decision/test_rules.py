import copy
from dataclasses import FrozenInstanceError, replace
from datetime import date, timedelta
from types import MappingProxyType

import pytest

from app.decision import DEFAULT_CONFIG, decide, eligible_date
from app.decision.config import ScoreBand
from app.decision.scoring import rub, score


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("status", "LIQUIDATED", "SF_INACTIVE"),
        ("bankruptcy", True, "SF_BANKRUPTCY"),
        ("reg_date", "2026-05-01", "SF_AGE"),
        ("current_overdue_total", 1, "SF_OVERDUE"),
        ("max_dpd_12m", 61, "SF_OVERDUE"),
        ("tax_debt", 50_001, "SF_TAX_DEBT"),
        ("enforcement_sum", 100_001, "SF_TAX_DEBT"),
        ("okved_main", "92.11", "SF_OKVED"),
        ("okved_main", "64.99", "SF_OKVED"),
        ("aml_flag", True, "SF_ADDITIONAL"),
        ("fraud_flag", True, "SF_ADDITIONAL"),
        ("reg_date", "2026-04-01", None),
        ("max_dpd_12m", 60, None),
        ("tax_debt", 50_000, None),
        ("enforcement_sum", 100_000, None),
    ],
)
def test_stop_boundaries(field, value, expected, persona_data, build_inputs, reference):
    persona = copy.deepcopy(persona_data["personas"][0])
    if field in persona:
        persona[field] = value
    elif field in persona["bki"]["summary"]:
        persona["bki"]["summary"][field] = value
    elif field in persona["fns"]:
        persona["fns"][field] = value
    else:
        persona["risk"][field] = value
    result = decide(build_inputs(persona), DEFAULT_CONFIG)
    stops = [rule for rule in result.rules_fired if rule.effect == "STOP"]
    assert (stops[0].code if stops else None) == expected
    assert all(rule.value and rule.threshold for rule in result.rules_fired)
    assert result.to_expected() == reference.decide(
        persona, persona["demo"]["app"], persona["demo"]["consents"]
    )


def test_stop_priority_and_complete_protocol(persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(
        inputs,
        company=replace(
            inputs.company, status="INACTIVE", reg_date=inputs.as_of, okved_main="92.10"
        ),
        bureau=replace(inputs.bureau, current_overdue_total=10_000),
        tax=replace(inputs.tax, bankruptcy=True, tax_debt=80_000),
        risk=replace(inputs.risk, aml_flag=True),
    )
    result = decide(inputs, DEFAULT_CONFIG)
    assert result.reason_code == "SF_INACTIVE"
    assert [rule.code for rule in result.rules_fired] == [
        "SF_INACTIVE",
        "SF_BANKRUPTCY",
        "SF_AGE",
        "SF_OVERDUE",
        "SF_TAX_DEBT",
        "SF_OKVED",
        "SF_ADDITIONAL",
    ]


def test_validation_order_and_answers(persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][2])
    inputs = replace(inputs, app=replace(inputs.app, purpose="OTHER"))
    assert decide(inputs, DEFAULT_CONFIG).validation_rule == "VAL_REVENUE_MISMATCH"
    inputs = replace(inputs, answered_items=frozenset({"REVENUE_CONFIRM"}))
    assert decide(inputs, DEFAULT_CONFIG).to_expected() == {
        "state": "INFO_REQUESTED",
        "validation_rule": "VAL_PURPOSE_UNCLEAR",
    }
    inputs = replace(
        inputs, answered_items=frozenset({"REVENUE_CONFIRM", "PURPOSE_DETAILS"})
    )
    assert decide(inputs, DEFAULT_CONFIG).state == "OFFER_ISSUED"


@pytest.mark.parametrize("delta,needs_info", [(0, False), (1, True)])
def test_revenue_boundary(delta, needs_info, persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(
        inputs, app=replace(inputs.app, declared_revenue_year=20_160_000 + delta)
    )
    result = decide(inputs, DEFAULT_CONFIG)
    assert (result.state == "INFO_REQUESTED") == needs_info


def test_no_consent_overrides_stop_and_score(persona_data, build_inputs):
    for index in (3, 4):
        inputs = build_inputs(persona_data["personas"][index])
        inputs = replace(
            inputs,
            company=replace(inputs.company, kind="IP"),
            auto_decision_consent=False,
        )
        result = decide(inputs, DEFAULT_CONFIG)
        assert result.state == "MANUAL_REVIEW"
        assert result.route_reason == "NO_AUTO_CONSENT"
        assert result.recommendation["outcome"] == result.outcome
        assert result.to_expected()["recommendation"] == result.recommendation
        assert result.rules_fired[-1].code == "NO_AUTO_CONSENT"


def test_grade_c_precedes_amount_route(persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][4])
    product = replace(DEFAULT_CONFIG.products["EXPRESS"], auto_limit=500_000)
    cfg = replace(
        DEFAULT_CONFIG, products={**DEFAULT_CONFIG.products, "EXPRESS": product}
    )
    result = decide(inputs, cfg)
    assert result.grade == "C"
    assert result.route_reason == "GRADE_C"
    assert result.rules_fired[-1].code == "GRADE_C"
    assert len(result.what_if) >= 2
    deficiencies = sorted(
        result.factors, key=lambda f: f.max_points - f.points, reverse=True
    )[:2]
    assert result.what_if[-2:] == [
        f"Оценка выше при: {factor.title}" for factor in deficiencies
    ]


@pytest.mark.parametrize(
    "amount,route", [(3_000_000, None), (3_000_001, "AMOUNT_ABOVE_AUTO")]
)
def test_amount_route_uses_requested_amount(amount, route, persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(inputs, app=replace(inputs.app, amount=amount))
    result = decide(inputs, DEFAULT_CONFIG)
    assert result.route_reason == route
    assert result.outcome == "COUNTER"
    assert result.offer.amount < 3_000_000


def test_decline_does_not_route_by_amount(persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][3])
    inputs = replace(inputs, app=replace(inputs.app, amount=4_000_000))
    result = decide(inputs, DEFAULT_CONFIG)
    assert result.state == "DECLINED"
    assert result.route_reason is None


def test_as_of_is_input_and_no_input_mutation(persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(
        inputs, company=replace(inputs.company, reg_date=date(2026, 4, 23))
    )
    original = copy.deepcopy(inputs)
    assert decide(inputs, DEFAULT_CONFIG).reason_code is None
    earlier = replace(inputs, as_of=date(2026, 9, 23))
    result = decide(earlier, DEFAULT_CONFIG)
    assert result.reason_code == "SF_AGE"
    assert result.what_if == ["Подайте заявку с 01.10.2026"]
    assert inputs == original
    assert decide(inputs, DEFAULT_CONFIG) == decide(inputs, DEFAULT_CONFIG)


@pytest.mark.parametrize(
    "reg_date,first_eligible,expected_text",
    [
        (date(2026, 4, 15), date(2026, 10, 1), "Подайте заявку с 01.10.2026"),
        (date(2026, 3, 31), date(2026, 9, 1), "Подайте заявку с 01.09.2026"),
        (date(2025, 10, 31), date(2026, 4, 1), "Подайте заявку с 01.04.2026"),
    ],
)
def test_business_age_first_eligible_day(
    reg_date, first_eligible, expected_text, persona_data, build_inputs
):
    assert eligible_date(reg_date, DEFAULT_CONFIG) == first_eligible
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(
        inputs,
        company=replace(inputs.company, reg_date=reg_date),
        as_of=first_eligible - timedelta(days=1),
    )
    before = decide(inputs, DEFAULT_CONFIG)
    assert before.reason_code == "SF_AGE"
    assert before.what_if == [expected_text]
    eligible = decide(replace(inputs, as_of=first_eligible), DEFAULT_CONFIG)
    assert "SF_AGE" not in {rule.code for rule in eligible.rules_fired}
    assert eligible.state == "OFFER_ISSUED"


def test_frozen_models_and_config(persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    result = decide(inputs, DEFAULT_CONFIG)
    for obj in (
        inputs,
        inputs.company,
        inputs.bureau,
        inputs.tax,
        inputs.risk,
        inputs.app,
        result,
        result.offer,
        result.policy,
        DEFAULT_CONFIG,
    ):
        field_name = next(iter(obj.__dataclass_fields__))
        with pytest.raises(FrozenInstanceError):
            setattr(obj, field_name, None)
    with pytest.raises(TypeError):
        DEFAULT_CONFIG.products["EXPRESS"] = None
    with pytest.raises(TypeError):
        DEFAULT_CONFIG.products["EXPRESS"].spreads["A"] = 0
    with pytest.raises(TypeError):
        DEFAULT_CONFIG.factors["business_age"] = None
    with pytest.raises(ValueError, match="12"):
        replace(inputs, turnover=(1,) * 11)


def test_custom_configuration_is_used(persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    base = decide(inputs, DEFAULT_CONFIG)
    higher_rate = decide(inputs, replace(DEFAULT_CONFIG, key_rate=15.0))
    assert higher_rate.offer.rate == base.offer.rate + 1
    assert higher_rate.offer.monthly_payment > base.offer.monthly_payment
    cfg = replace(DEFAULT_CONFIG, stop_min_age=100)
    assert decide(inputs, cfg).reason_code == "SF_AGE"
    factors = {**DEFAULT_CONFIG.factors}
    factors["business_age"] = replace(
        factors["business_age"], bands=(ScoreBand("ge", 0, 0),)
    )
    result = decide(inputs, replace(DEFAULT_CONFIG, factors=MappingProxyType(factors)))
    assert result.points["business_age"] == 0
    assert result.score == base.score - 10
    assert decide(inputs, DEFAULT_CONFIG) == base


@pytest.mark.parametrize("value,expected", [(1.49, 1), (1.5, 2), (2.5, 3)])
def test_half_up_rounding(value, expected):
    assert rub(value) == expected


@pytest.mark.parametrize("age,points", [(11, 0), (12, 5), (36, 5), (37, 10)])
def test_business_age_score(age, points, persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    month_index = inputs.as_of.year * 12 + inputs.as_of.month - 1 - age
    inputs = replace(
        inputs,
        company=replace(
            inputs.company, reg_date=date(month_index // 12, month_index % 12 + 1, 1)
        ),
    )
    assert score(inputs, DEFAULT_CONFIG)[0]["business_age"] == points


@pytest.mark.parametrize(
    "field,value,factor,points",
    [
        ("max_dpd_12m", 0, "delinquency_12m", 10),
        ("max_dpd_12m", 1, "delinquency_12m", 5),
        ("max_dpd_12m", 30, "delinquency_12m", 5),
        ("max_dpd_12m", 31, "delinquency_12m", 0),
        ("credit_history_months", 0, "credit_history_length", 2),
        ("credit_history_months", 1, "credit_history_length", 3),
        ("credit_history_months", 23, "credit_history_length", 3),
        ("credit_history_months", 24, "credit_history_length", 5),
        ("inquiries_30d", 1, "bureau_inquiries_30d", 5),
        ("inquiries_30d", 2, "bureau_inquiries_30d", 2),
        ("inquiries_30d", 3, "bureau_inquiries_30d", 2),
        ("inquiries_30d", 4, "bureau_inquiries_30d", 0),
        ("total_balance", 3_599_999, "debt_to_turnover", 10),
        ("total_balance", 3_600_000, "debt_to_turnover", 5),
        ("total_balance", 7_200_000, "debt_to_turnover", 5),
        ("total_balance", 7_200_001, "debt_to_turnover", 0),
    ],
)
def test_bureau_score_boundaries(
    field, value, factor, points, persona_data, build_inputs
):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(inputs, bureau=replace(inputs.bureau, **{field: value}))
    assert score(inputs, DEFAULT_CONFIG)[0][factor] == points
