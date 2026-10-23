from pathlib import Path

import pytest

from app.decision import DEFAULT_CONFIG, decide


@pytest.mark.parametrize("index", range(6))
def test_protocol(index, persona_data, build_inputs):
    persona = persona_data["personas"][index]
    result = decide(build_inputs(persona, answered={"REVENUE_CONFIRM"}), DEFAULT_CONFIG)
    if result.score is not None:
        assert len(result.factors) == 12
        assert sum(factor.points for factor in result.factors) == result.score
        assert sum(factor.max_points for factor in result.factors) == 100
        assert {f.code: f.points for f in result.factors} == result.points
        assert all(factor.value for factor in result.factors)
    if persona["code"] == "ooo_load":
        assert result.policy.steps
        assert result.what_if[0] == "Одобрение при сумме ≤ 1 550 000 ₽ на 12 мес."
        assert result.policy.free_payment == 150_000
        assert result.policy.rate == 23
        assert result.policy.max_amount == 2_850_000
        assert {rule.effect for rule in result.rules_fired} >= {"POLICY"}
    if persona["code"] == "ip_bad":
        assert [(r.code, r.effect) for r in result.rules_fired] == [
            ("SF_OVERDUE", "STOP")
        ]
        assert result.what_if
    if persona["code"] == "ooo_aml":
        assert result.client_reason_code == "ADDITIONAL_CHECKS"
        assert result.reason_code == "SF_ADDITIONAL"
    if result.state == "OFFER_ISSUED" and result.outcome == "APPROVE":
        assert result.what_if == []


def test_factor_wording_matches_current_table(persona_data, build_inputs):
    model = Path(__file__).resolve().parents[3] / "docs" / "decision-model.md"
    text = model.read_text(encoding="utf-8")
    table = text.split("## 4.")[1].split("<details>")[0]
    rows = [
        line.split("|")[3:5]
        for line in table.splitlines()
        if line.startswith("|") and line.split("|")[2].strip().isdigit()
    ]
    expected = [(title.strip(), rule.strip()) for title, rule in rows]
    result = decide(build_inputs(persona_data["personas"][0]), DEFAULT_CONFIG)
    assert len(expected) == 12
    assert [(factor.title, factor.rule) for factor in result.factors] == expected


def test_validation_protocol(persona_data, build_inputs):
    result = decide(build_inputs(persona_data["personas"][2]), DEFAULT_CONFIG)
    assert result.outcome is None
    assert result.policy is None
    assert result.factors == []
    assert [(r.code, r.effect) for r in result.rules_fired] == [
        ("VAL_REVENUE_MISMATCH", "INFO")
    ]
    assert all(r.value and r.threshold for r in result.rules_fired)
