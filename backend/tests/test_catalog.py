import importlib.util
import re
from pathlib import Path

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from test_auth import api_client

from app.models import DecisionConfig, Product


@pytest.fixture
def catalog_context(migrated_database):
    engine, _ = migrated_database
    with Session(engine) as session, api_client(session) as client:
        token = client.post(
            "/auth/login", json={"login": "ip_good", "password": "b03-test-password"}
        ).json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        yield client, session
        session.rollback()


def test_products_match_contract(catalog_context):
    client, _ = catalog_context
    response = client.get("/products")
    assert response.status_code == 200
    products = response.json()
    assert [product["code"] for product in products] == [
        "EXPRESS",
        "WORKING_CAPITAL",
        "OVERDRAFT",
    ]
    express = products[0]
    assert {
        key: express[key]
        for key in (
            "min_amount",
            "max_amount",
            "rate_from",
            "key_rate",
            "key_rate_date",
        )
    } == {
        "min_amount": 300000,
        "max_amount": 5000000,
        "rate_from": 22.0,
        "key_rate": 14.0,
        "key_rate_date": "2026-10-23",
    }
    codes = (Path(__file__).resolve().parents[2] / "contracts/codes.md").read_text(
        encoding="utf-8"
    )
    table = codes.split("### Витрина продуктов", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in table.splitlines() if re.match(r"\| `\w+` \|", line)]
    assert len(rows) == 3
    for product, row in zip(products, rows, strict=True):
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert product["code"] == cells[0].strip("`")
        assert product["name"] == cells[1]
        assert product["description"] == cells[2]
        assert product["purposes"] == re.findall(r"`(\w+)`", cells[3])
        assert product["requires_guarantor_ooo"] is (cells[4] == "да")


@pytest.mark.parametrize(
    "code,amount,term,rate,payment",
    [
        ("EXPRESS", 1500000, 24, 22.0, 77817),
        ("WORKING_CAPITAL", 4000000, 12, 21.0, 372455),
        ("EXPRESS", 300000, 6, 22.0, 53257),
        ("WORKING_CAPITAL", 15000000, 24, 21.0, 770785),
        ("OVERDRAFT", 500000, 12, 24.0, None),
    ],
)
def test_exact_payments(catalog_context, code, amount, term, rate, payment):
    client, _ = catalog_context
    response = client.post(
        "/calculator",
        json={"product_code": code, "amount": amount, "term_months": term},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"rate_estimate": rate, "monthly_payment": payment}


def test_annuity_reference_grid(catalog_context):
    client, session = catalog_context
    path = Path(__file__).resolve().parents[2] / "contracts/decision_reference.py"
    spec = importlib.util.spec_from_file_location("decision_reference_b04", path)
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    for code in ("EXPRESS", "WORKING_CAPITAL"):
        params = session.scalar(select(Product).where(Product.code == code)).params
        for amount in (
            params["min"],
            (params["min"] + params["max"]) // 2,
            params["max"],
        ):
            for term in (
                params["tmin"],
                (params["tmin"] + params["tmax"]) // 2,
                params["tmax"],
            ):
                response = client.post(
                    "/calculator",
                    json={"product_code": code, "amount": amount, "term_months": term},
                )
                assert response.status_code == 200, response.text
                data = response.json()
                assert data["monthly_payment"] == reference.rub(
                    reference.annuity(amount, data["rate_estimate"], term)
                )


@pytest.mark.parametrize(
    "code,field,value,message",
    [
        ("EXPRESS", "amount", 299999, "Сумма от 300 000 до 5 000 000 ₽"),
        ("EXPRESS", "amount", 5000001, "Сумма от 300 000 до 5 000 000 ₽"),
        ("EXPRESS", "term_months", 5, "Срок от 6 до 36 мес."),
        ("EXPRESS", "term_months", 37, "Срок от 6 до 36 мес."),
        ("WORKING_CAPITAL", "term_months", 2, "Срок от 3 до 24 мес."),
        ("WORKING_CAPITAL", "term_months", 25, "Срок от 3 до 24 мес."),
    ],
)
def test_product_boundaries(catalog_context, code, field, value, message):
    client, _ = catalog_context
    body = {"product_code": code, "amount": 1500000, "term_months": 12, field: value}
    response = client.post("/calculator", json=body)
    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "VALIDATION_ERROR",
        "message": "Проверьте параметры кредита",
        "details": {"fields": {field: message}},
    }


@pytest.mark.parametrize("path", ["/products", "/calculator"])
def test_no_active_config(catalog_context, path):
    client, session = catalog_context
    session.execute(update(DecisionConfig).values(active=False))
    response = (
        client.get(path)
        if path == "/products"
        else client.post(
            path, json={"product_code": "EXPRESS", "amount": 1500000, "term_months": 24}
        )
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


def test_missing_product(catalog_context):
    client, session = catalog_context
    product = session.scalar(select(Product).where(Product.code == "EXPRESS"))
    session.delete(product)
    session.flush()
    response = client.post(
        "/calculator",
        json={"product_code": "EXPRESS", "amount": 1500000, "term_months": 24},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
