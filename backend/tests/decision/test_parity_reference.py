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


def test_parity_2000_without_stops(persona_data, reference, build_inputs, capsys):
    rng = random.Random(17)
    reasons, outcomes, routes, validations = Counter(), Counter(), Counter(), Counter()
    for index in range(2000):
        persona = copy.deepcopy(rng.choice(persona_data["personas"]))
        product = rng.choice(tuple(reference.PRODUCTS))
        bounds = reference.PRODUCTS[product]
        persona.update(
            kind=rng.choice(("IP", "OOO")),
            status="ACTIVE",
            reg_date=date(rng.randint(2017, 2025), rng.randint(1, 12), 1).isoformat(),
            okved_main=rng.choice(("52.10", "56.10", "41.10")),
        )
        scale, trend = rng.uniform(0.1, 3.0), rng.choice((0.5, 0.8, 1.0, 1.3))
        persona["turnover"] = [
            round(value * scale * (trend if month >= 9 else 1))
            for month, value in enumerate(persona["turnover"])
        ]
        for month in rng.sample(range(12), rng.choice((0, 1, 2))):
            persona["turnover"][month] = 0
        avg = sum(persona["turnover"]) / 12
        persona["bki"]["summary"].update(
            monthly_payments_total=round(avg * rng.uniform(0, 0.6)),
            total_balance=round(avg * rng.uniform(0, 12)),
            current_overdue_total=0,
            max_dpd_12m=0,
            credit_history_months=rng.choice((0, 12, 36)),
            inquiries_30d=rng.choice((0, 2, 5)),
        )
        persona["fns"].update(
            bankruptcy=False,
            mass_director=False,
            mass_address=False,
            tax_debt=0,
            enforcement_sum=0,
            arbitration_defendant_sum=0,
        )
        persona["risk"].update(aml_flag=False, fraud_flag=False)
        app = persona["demo"]["app"]
        app.update(
            product=product,
            amount=rng.randint(bounds["min"], bounds["max"]),
            term=rng.randint(bounds["tmin"], bounds["tmax"]),
            purpose=rng.choice(("WORKING_CAPITAL", "EQUIPMENT", "OTHER")),
            purpose_text=rng.choice((None, "Закупка материалов")),
            declared_revenue_year=sum(persona["turnover"]),
        )
        consents = {"auto_decision": rng.choice((False, True))}
        answered = rng.choice(((), ("PURPOSE_DETAILS",)))
        assert reference.stop_factor(persona) is None
        expected = reference.decide(persona, app, consents, answered)
        actual = decide(build_inputs(persona, app, consents, answered), DEFAULT_CONFIG)
        assert actual.to_expected() == expected, (
            f"Первое расхождение без стоп-факторов, вариант {index}:\n"
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
        result = expected.get("recommendation", expected)
        reasons[result.get("reason_code")] += 1
        outcomes[result.get("outcome")] += 1
        routes[expected.get("route_reason")] += 1
        validations[expected.get("validation_rule")] += 1
    assert sum(outcomes.values()) == 2000
    assert reasons["LOW_SCORE"] > 0
    assert reasons["HIGH_LOAD"] > 0
    assert outcomes["COUNTER"] > 0
    assert {route for route in routes if route is not None} == {
        "NO_AUTO_CONSENT",
        "GRADE_C",
        "AMOUNT_ABOVE_AUTO",
    }
    assert validations["VAL_PURPOSE_UNCLEAR"] > 0
    with capsys.disabled():
        print(
            f"\nParity без стоп-факторов: 2000 вариантов, 0 расхождений; "
            f"reasons={dict(reasons)}; outcomes={dict(outcomes)}; "
            f"routes={dict(routes)}; validations={dict(validations)}"
        )
