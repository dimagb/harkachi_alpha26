from dataclasses import replace

import pytest

from app.decision import DEFAULT_CONFIG, decide
from app.decision.scoring import score


@pytest.mark.parametrize(
    "deviation,points",
    [
        (299_999, 10),
        (300_000, 5),
        (600_000, 5),
        (600_001, 0),
    ],
)
def test_stability_boundaries(deviation, points, persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(
        inputs, turnover=(1_000_000 - deviation, 1_000_000 + deviation) * 6
    )
    assert score(inputs, DEFAULT_CONFIG)[0]["turnover_stability"] == points


@pytest.mark.parametrize(
    "last_three,points",
    [
        (950_000, 10),
        (949_999, 5),
        (800_000, 5),
        (799_999, 0),
    ],
)
def test_trend_boundaries(last_three, points, persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(inputs, turnover=(1_000_000,) * 9 + (last_three,) * 3)
    assert score(inputs, DEFAULT_CONFIG)[0]["turnover_trend"] == points


@pytest.mark.parametrize("zero_months,points", [(0, 10), (1, 5), (2, 0)])
def test_months_without_receipts(zero_months, points, persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(
        inputs, turnover=(0,) * zero_months + (1_000_000,) * (12 - zero_months)
    )
    assert score(inputs, DEFAULT_CONFIG)[0]["zero_months"] == points


@pytest.mark.parametrize(
    "payment,points",
    [
        (89_999, 15),
        (90_000, 10),
        (189_999, 10),
        (190_000, 4),
        (289_999, 4),
        (290_000, 0),
    ],
)
def test_ptr_boundaries(payment, points, persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(
        inputs,
        turnover=(1_000_000,) * 12,
        app=replace(
            inputs.app, product_code="OVERDRAFT", amount=100_000, term_months=12
        ),
        bureau=replace(inputs.bureau, monthly_payments_total=payment),
    )
    # 10% лимита — платёж нового овердрафта; PTR=30% даёт 0 по эталону.
    assert score(inputs, DEFAULT_CONFIG)[0]["payment_to_turnover"] == points


@pytest.mark.parametrize(
    "okved,points",
    [
        ("52.10", 5),
        ("47.71", 3),
        ("41.10", 0),
        ("99.99", 3),
    ],
)
def test_industry_and_default(okved, points, persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(inputs, company=replace(inputs.company, okved_main=okved))
    assert score(inputs, DEFAULT_CONFIG)[0]["industry_risk"] == points


@pytest.mark.parametrize("field", ["mass_director", "mass_address"])
def test_mass_registration(field, persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(inputs, company=replace(inputs.company, **{field: True}))
    assert score(inputs, DEFAULT_CONFIG)[0]["mass_registration"] == 0


@pytest.mark.parametrize(
    "field",
    [
        "tax_debt",
        "enforcement_sum",
        "arbitration_defendant_sum",
    ],
)
def test_payment_discipline(field, persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    inputs = replace(inputs, tax=replace(inputs.tax, **{field: 1}))
    assert score(inputs, DEFAULT_CONFIG)[0]["payment_discipline"] == 2


@pytest.mark.parametrize(
    "total,grade",
    [
        (75, "A"),
        (74, "B"),
        (60, "B"),
        (59, "C"),
        (45, "C"),
        (44, "D"),
    ],
)
def test_grade_boundaries(total, grade, persona_data, build_inputs):
    inputs = build_inputs(persona_data["personas"][0])
    # Возраст уже >36 мес.; настройка баллов изолирует границы оценок.
    factor = replace(
        DEFAULT_CONFIG.factors["business_age"], bands=(), default_points=total
    )
    cfg = replace(DEFAULT_CONFIG, factors={"business_age": factor})
    result = decide(inputs, cfg)
    assert result.score == total
    assert result.grade == grade
    if grade == "D":
        assert result.reason_code == "LOW_SCORE"
        assert result.policy is None
    elif grade == "C":
        assert result.route_reason == "GRADE_C"
