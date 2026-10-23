import pytest

from app.decision import DEFAULT_CONFIG, decide


@pytest.mark.parametrize("index", range(6))
def test_golden_personas(index, persona_data, build_inputs):
    persona = persona_data["personas"][index]
    expected = persona["demo"]["expected"]
    result = decide(build_inputs(persona), DEFAULT_CONFIG)
    if persona["code"] == "ooo_gap":
        assert result.to_expected() == {
            "state": expected["first_state"],
            "validation_rule": expected["validation_rule"],
        }
        result = decide(
            build_inputs(persona, answered={"REVENUE_CONFIRM"}), DEFAULT_CONFIG
        )
        assert result.to_expected() == expected["after_info"]
    else:
        assert result.to_expected() == expected
