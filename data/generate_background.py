"""Детерминированные фоновые компании и заявки; запускать из корня проекта."""

import importlib.util
import json
import math
import random
import statistics
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 10, 23)
SEED = 20261023
COMMON = ("DRAFT", "SUBMITTED", "WITHDRAWN")
OFFER = ("OFFER_ISSUED", "SIGNED", "DISBURSED", "EXPIRED")


def inn10(b):
    w = [2, 4, 10, 3, 5, 9, 4, 6, 8]
    return b + str(sum(int(c) * k for c, k in zip(b, w)) % 11 % 10)


def inn12(b):
    d = [int(c) for c in b]
    c1 = sum(x * k for x, k in zip(d, [7, 2, 4, 10, 3, 5, 9, 4, 6, 8])) % 11 % 10
    d.append(c1)
    c2 = sum(x * k for x, k in zip(d, [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8])) % 11 % 10
    return b + str(c1) + str(c2)


def rub(value):
    return int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def load_reference():
    spec = importlib.util.spec_from_file_location(
        "decision_reference", ROOT / "contracts/decision_reference.py"
    )
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    return reference


def turnover(rng):
    average = max(
        300_000, min(8_000_000, rub(rng.lognormvariate(math.log(1_500_000), 0.85)))
    )
    cv = rng.uniform(0.1, 0.7)
    sigma = math.sqrt(math.log1p(cv * cv))
    phase = rng.uniform(0, 2 * math.pi)
    weights = [
        (1 + 0.15 * math.sin(2 * math.pi * month / 12 + phase))
        * rng.lognormvariate(-sigma * sigma / 2, sigma)
        for month in range(12)
    ]
    mean_weight = statistics.mean(weights)
    values = [rub(Decimal(average) * Decimal(str(w / mean_weight))) for w in weights]
    values[-1] += 12 * average - sum(values)
    return values


def make_companies(rng, reference):
    indices = list(range(40))
    kinds = ["OOO"] * 24 + ["IP"] * 16
    rng.shuffle(kinds)
    credit = rng.sample(indices, 24)
    delinquent = rng.sample(credit, 6)
    short, long = set(delinquent[:4]), set(delinquent[4:6])
    current = rng.choice(delinquent[:4])
    taxes = rng.sample(indices, 3)
    enforcement = set(rng.sample(indices, 2))
    bankrupt, aml = rng.choice(indices), rng.choice(indices)
    stop = rng.sample(indices, 2)
    used_inns = {p["inn"] for p in reference.PERSONAS}
    companies = []
    for i, kind in enumerate(kinds):
        code = f"bg_{i + 1:03d}"
        while True:
            prefix = "77" + "".join(
                str(rng.randrange(10)) for _ in range(7 if kind == "OOO" else 8)
            )
            inn = inn10(prefix) if kind == "OOO" else inn12(prefix)
            if inn not in used_inns:
                used_inns.add(inn)
                break
        age = max(3, min(120, round(rng.lognormvariate(math.log(30), 0.65))))
        month_index = AS_OF.year * 12 + AS_OF.month - 1 - age
        registered = date(month_index // 12, month_index % 12 + 1, AS_OF.day)
        amounts = turnover(rng)
        average = Decimal(sum(amounts)) / 12
        payment = (
            rub(average * Decimal(str(rng.uniform(0.05, 0.35)))) if i in credit else 0
        )
        balance = payment * rng.randint(6, 36) if i in credit else 0
        dpd = (
            rng.randint(1, 30)
            if i in short
            else rng.randint(31, 90)
            if i in long
            else 0
        )
        overdue = rng.randint(1000, 30_000) if i == current else 0
        tax = (
            rng.randint(50_001, 100_000)
            if i == taxes[0]
            else rng.randint(1000, 50_000)
            if i in taxes
            else 0
        )
        okved = rng.choice(tuple(reference.INDUSTRY)) + ".10"
        if i in stop:
            okved = "92.10" if i == stop[0] else "64.91"
        director = f"Иванов Алексей Сергеевич {i + 1}"
        name = (
            f"ООО «Фоновая компания {i + 1:02d}»" if kind == "OOO" else f"ИП {director}"
        )
        ogrn_prefix = (
            "12677" if kind == "OOO" else "32677"
        ) + f"{i + 1:0{7 if kind == 'OOO' else 9}d}"
        ogrn = ogrn_prefix + str(int(ogrn_prefix) % (11 if kind == "OOO" else 13) % 10)
        companies.append(
            reference.company(
                code,
                kind,
                inn,
                ogrn,
                name,
                okved,
                registered.isoformat(),
                f"г. Москва, ул. Примерная, д. {i + 1}",
                director,
                amounts,
                reference.bki(
                    payment, balance, overdue, dpd, min(age, rng.randint(12, 72))
                ),
                reference.fns(
                    tax=tax,
                    enf=rng.randint(1000, 100_000) if i in enforcement else 0,
                    bank=i == bankrupt,
                ),
                [
                    reference.user(
                        code,
                        director,
                        "Директор" if kind == "OOO" else "Предприниматель",
                    )
                ],
                {"apps": []},
                aml=i == aml,
            )
        )
    return companies


def make_application(rng, reference, company, wanted=None):
    product = rng.choice(tuple(reference.PRODUCTS))
    limits = reference.PRODUCTS[product]
    app = {
        "product": product,
        "amount": rng.randrange(limits["min"] // 50_000, limits["max"] // 50_000 + 1)
        * 50_000,
        "term": rng.randint(limits["tmin"], limits["tmax"]),
        "purpose": "WORKING_CAPITAL",
        "declared_revenue_year": sum(company["turnover"]),
    }
    consents = {"pdn": True, "bki": True, "auto_decision": True}
    if wanted == "INFO_REQUESTED":
        app["declared_revenue_year"] *= 2
    elif wanted == "MANUAL_REVIEW" and company["kind"] == "IP":
        consents["auto_decision"] = False
    return app, consents


def add_applications(rng, reference, companies):
    double = set(rng.sample(range(40), 20))
    slots = [i for i in range(40) for _ in range(2 if i in double else 1)]
    rng.shuffle(slots)
    # Сначала резервируем по три заявки для состояний с ограниченным маршрутом.
    wanted_states = ("DECLINED", "MANUAL_REVIEW", "INFO_REQUESTED") + OFFER + COMMON
    for wanted in wanted_states:
        for _ in range(3):
            selected = None
            for slot, index in enumerate(slots):
                company = companies[index]
                for _ in range(30):
                    app, consents = make_application(rng, reference, company, wanted)
                    state = reference.decide(company, app, consents)["state"]
                    allowed = COMMON + (OFFER if state == "OFFER_ISSUED" else (state,))
                    if wanted in allowed:
                        selected = slot, app, consents
                        break
                if selected is not None:
                    break
            if selected is None:
                raise RuntimeError(
                    f"Не удалось подобрать достижимое состояние {wanted}"
                )
            slot, app, consents = selected
            index = slots.pop(slot)
            companies[index]["demo"]["apps"].append(
                {
                    "app": app,
                    "consents": consents,
                    "target_state": wanted,
                }
            )
    for index in slots:
        company = companies[index]
        app, consents = make_application(rng, reference, company)
        state = reference.decide(company, app, consents)["state"]
        allowed = COMMON + (OFFER if state == "OFFER_ISSUED" else (state,))
        company["demo"]["apps"].append(
            {
                "app": app,
                "consents": consents,
                "target_state": rng.choice(allowed),
            }
        )


def generate(path):
    rng = random.Random(20261023)
    reference = load_reference()
    companies = make_companies(rng, reference)
    add_applications(rng, reference, companies)
    data = {
        "_meta": {
            "as_of": AS_OF.isoformat(),
            "seed": SEED,
            "turnover_months": "2025-10…2026-09 (YYYY-MM)",
            "note": "Синтетические данные; исходы рассчитываются конвейером, demo.expected отсутствует.",
        },
        "companies": companies,
    }
    path = Path(path)
    path.write_bytes(
        (json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode(
            "utf-8"
        )
    )


if __name__ == "__main__":
    generate(ROOT / "data/background.json")
