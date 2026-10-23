import copy
import json
import random
from collections import Counter
from datetime import date

from app.decision import DEFAULT_CONFIG, decide


def test_parity_2000(persona_data, reference, build_inputs, capsys):
    rng = random.Random(7)
    states, outcomes = Counter(), Counter()
    for index in range(2000):
        persona = copy.deepcopy(rng.choice(persona_data["personas"]))
        app = persona["demo"]["app"]
        product = rng.choice(tuple(reference.PRODUCTS))
        bounds = reference.PRODUCTS[product]
        app.update(
            product=product,
            amount=max(
                bounds["min"],
                min(bounds["max"], round(app["amount"] * rng.uniform(0.2, 3.0))),
            ),
            term=rng.randint(bounds["tmin"], bounds["tmax"]),
        )
        scale = rng.uniform(0.3, 3.0)
        persona["turnover"] = [round(value * scale) for value in persona["turnover"]]
        persona["bki"]["summary"].update(
            max_dpd_12m=rng.choice((0, 15, 45, 75)),
            current_overdue_total=rng.choice((0, 10_000)),
        )
        persona["fns"]["tax_debt"] = rng.choice((0, 30_000, 80_000))
        persona["risk"].update(
            aml_flag=rng.choice((False, True)), fraud_flag=rng.choice((False, True))
        )
        consents = {"auto_decision": rng.choice((False, True))}
        persona["reg_date"] = date(
            rng.randint(2017, 2026), rng.randint(1, 12), 1
        ).isoformat()
        answered = rng.choice(((), ("REVENUE_CONFIRM",)))
        expected = reference.decide(persona, app, consents, answered)
        actual = decide(build_inputs(persona, app, consents, answered), DEFAULT_CONFIG)
        assert actual.to_expected() == expected, (
            f"Первое расхождение, вариант {index}:\n"
            + json.dumps(
                {
                    "persona": persona,
                    "consents": consents,
                    "answered": answered,
                    "expected": expected,
                    "actual": actual.to_expected(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        states[expected["state"]] += 1
        result = expected.get("recommendation", expected)
        if "outcome" in result:
            outcomes[result["outcome"]] += 1
    assert sum(states.values()) == 2000
    assert set(states) == {
        "INFO_REQUESTED",
        "MANUAL_REVIEW",
        "OFFER_ISSUED",
        "DECLINED",
    }
    assert set(outcomes) == {"APPROVE", "COUNTER", "DECLINE"}
    with capsys.disabled():
        print(
            f"\nParity: 2000 вариантов, 0 расхождений; states={dict(states)}; "
            f"outcomes={dict(outcomes)}"
        )
