"""Проверки контракта A-02 на настоящих данных и эталонном движке."""

import hashlib
import importlib.util
import json
import statistics
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "data/generate_background.py"
BACKGROUND = ROOT / "data/background.json"
STATES = {
    "DRAFT",
    "SUBMITTED",
    "WITHDRAWN",
    "OFFER_ISSUED",
    "SIGNED",
    "DISBURSED",
    "EXPIRED",
    "DECLINED",
    "MANUAL_REVIEW",
    "INFO_REQUESTED",
}
COMMON = {"DRAFT", "SUBMITTED", "WITHDRAWN"}
OFFER = {"OFFER_ISSUED", "SIGNED", "DISBURSED", "EXPIRED"}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def reference():
    return load_module("decision_reference", ROOT / "contracts/decision_reference.py")


@pytest.fixture(scope="module")
def personas():
    return json.loads((ROOT / "contracts/personas.json").read_text(encoding="utf-8"))[
        "personas"
    ]


@pytest.fixture(scope="module")
def companies():
    return json.loads(BACKGROUND.read_text(encoding="utf-8"))["companies"]


def test_generator_available():
    assert GENERATOR.is_file(), "В A-02 ещё отсутствует генератор generate(path)"


def test_names_are_human_and_do_not_overlap_personas(companies, personas):
    names = {p["name"] for p in personas}
    people = {u["full_name"] for p in personas for u in p["users"]}
    assert len({p["name"] for p in companies}) == 40
    for company in companies:
        assert company["name"] not in names
        assert "Фоновая компания" not in company["name"]
        assert not any(c.isdigit() for c in company["name"])
        for user in company["users"]:
            assert user["full_name"] not in people
            assert len(user["full_name"].split()) == 3
            assert not any(c.isdigit() for c in user["full_name"])


def test_renaming_preserves_original_financial_data(tmp_path):
    def without_names(value):
        if isinstance(value, dict):
            return {
                k: without_names(v)
                for k, v in value.items()
                if k not in {"name", "full_name", "director", "founders"}
            }
        if isinstance(value, list):
            return [without_names(v) for v in value]
        return value

    output = tmp_path / "background.json"
    load_module("generate_background", GENERATOR).generate(output)
    payload = without_names(json.loads(output.read_text("utf-8")))
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    assert digest == "15850db47c1295f154b10a317eb5f84eef48cdb3a82aa6eddf51f76e5b14ea39"


def test_determinism_and_serialization(tmp_path):
    generator = load_module("generate_background", GENERATOR)
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    generator.generate(first)
    generator.generate(second)
    blobs = [p.read_bytes() for p in (first, second, BACKGROUND)]
    assert len({hashlib.sha256(blob).hexdigest() for blob in blobs}) == 1
    assert b"\r" not in blobs[0]
    payload = json.loads(blobs[0])
    assert set(payload) == {"_meta", "companies"}
    assert blobs[0] == (
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    ).encode("utf-8")
    assert len(blobs[0]) < 1_000_000


def test_company_and_application_counts(companies):
    assert len(companies) == 40
    assert {p["code"] for p in companies} == {f"bg_{i:03d}" for i in range(1, 41)}
    assert all(1 <= len(p["demo"]["apps"]) <= 2 for p in companies)
    assert sum(len(p["demo"]["apps"]) for p in companies) == 60


def test_persona_compatible_structure(companies, personas):
    template = personas[0]
    for p in companies:
        assert set(p) == set(template)
        assert "expected" not in p["demo"] and "app" not in p["demo"]
        assert p["users"][0]["login"] == p["code"]
        assert set(p["users"][0]) == set(template["users"][0])
        assert set(p["bki"]) == {"loans", "summary"}
        assert set(p["bki"]["summary"]) == set(template["bki"]["summary"])
        assert set(p["fns"]) == set(template["fns"])
        for item in p["demo"]["apps"]:
            assert set(item) == {"app", "consents", "target_state"}
            assert set(item["app"]) == set(template["demo"]["app"])
            assert set(item["consents"]) == set(template["demo"]["consents"])


def test_inn_checksums_and_uniqueness(companies, personas):
    inns = [p["inn"] for p in companies]
    assert len(set(inns)) == 40
    assert set(inns).isdisjoint(p["inn"] for p in personas)
    for p in companies:
        digits = list(map(int, p["inn"]))
        assert len(digits) == (10 if p["kind"] == "OOO" else 12)
        if len(digits) == 10:
            assert (
                digits[9]
                == sum(d * w for d, w in zip(digits, [2, 4, 10, 3, 5, 9, 4, 6, 8]))
                % 11
                % 10
            )
        else:
            assert (
                digits[10]
                == sum(d * w for d, w in zip(digits, [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]))
                % 11
                % 10
            )
            assert (
                digits[11]
                == sum(
                    d * w for d, w in zip(digits, [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8])
                )
                % 11
                % 10
            )


def test_company_mix_and_ages(companies):
    kinds = Counter(p["kind"] for p in companies)
    assert kinds == {"OOO": 24, "IP": 16}
    ages = []
    for p in companies:
        registered = date.fromisoformat(p["reg_date"])
        age = (2026 - registered.year) * 12 + 10 - registered.month
        assert 3 <= age <= 120
        ages.append(age)
    assert 20 <= statistics.median(ages) <= 40
    assert len(set(ages)) >= 15


def test_turnover_and_credit_distributions(companies):
    assert sum(bool(p["bki"]["loans"]) for p in companies) == 24
    for p in companies:
        turnover = p["turnover"]
        assert len(turnover) == 12
        assert all(type(v) is int and v > 0 for v in turnover)
        avg = statistics.mean(turnover)
        assert 300_000 <= avg <= 8_000_000
        b = p["bki"]
        assert b["summary"]["monthly_payments_total"] == sum(
            loan["monthly_payment"] for loan in b["loans"]
        )
        assert b["summary"]["total_balance"] == sum(
            loan["balance"] for loan in b["loans"]
        )
        if b["loans"]:
            assert 0.05 <= b["summary"]["monthly_payments_total"] / avg <= 0.35
    summaries = [p["bki"]["summary"] for p in companies]
    assert sum(1 <= b["max_dpd_12m"] <= 30 for b in summaries) == 4
    assert sum(31 <= b["max_dpd_12m"] <= 90 for b in summaries) == 2
    assert sum(b["current_overdue_total"] > 0 for b in summaries) == 1
    assert all(
        b["max_dpd_12m"] >= 1 for b in summaries if b["current_overdue_total"] > 0
    )


def test_rare_risks_and_industries(companies, reference):
    fns = [p["fns"] for p in companies]
    assert sum(f["tax_debt"] > 0 for f in fns) == 3
    assert sum(f["tax_debt"] > 50_000 for f in fns) == 1
    assert sum(f["enforcement_sum"] > 0 for f in fns) == 2
    assert sum(f["bankruptcy"] for f in fns) == 1
    assert sum(p["risk"]["aml_flag"] for p in companies) == 1
    stopped = [p for p in companies if p["okved_main"].startswith(("92", "64.9"))]
    assert len(stopped) == 2
    assert {p["okved_main"][:2] for p in stopped} == {"92", "64"}
    assert all(
        p in stopped or p["okved_main"][:2] in reference.INDUSTRY for p in companies
    )


def test_application_product_limits(companies, reference):
    products = set()
    for p in companies:
        for item in p["demo"]["apps"]:
            app = item["app"]
            products.add(app["product"])
            product = reference.PRODUCTS[app["product"]]
            assert type(app["amount"]) is int
            assert type(app["declared_revenue_year"]) is int
            assert product["min"] <= app["amount"] <= product["max"]
            assert product["tmin"] <= app["term"] <= product["tmax"]
            assert item["consents"]["pdn"] is True
            assert item["consents"]["bki"] is True
    assert products == set(reference.PRODUCTS)


def test_target_states_are_reachable_and_balanced(companies, reference):
    counts = Counter()
    for p in companies:
        for item in p["demo"]["apps"]:
            state = reference.decide(p, item["app"], item["consents"])["state"]
            allowed = COMMON | (OFFER if state == "OFFER_ISSUED" else {state})
            assert item["target_state"] in allowed, (p["code"], state, item)
            counts[item["target_state"]] += 1
    assert set(counts) == STATES
    assert min(counts.values()) >= 3
