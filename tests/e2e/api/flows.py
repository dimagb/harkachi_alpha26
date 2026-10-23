"""Тела запросов и golden-ожидания; без HTTP и расчёта модели решения."""

from copy import deepcopy


def create_body(persona, company_id):
    app = persona["demo"]["app"]
    body = {"company_id": company_id, **deepcopy(app)}
    body["product_code"] = body.pop("product")
    body["term_months"] = body.pop("term")
    return body


def submit_body(persona, otp_id, code):
    return {
        "otp_id": otp_id,
        "code": code,
        "consents": deepcopy(persona["demo"]["consents"]),
    }


def info_response_body(persona):
    return {"answers": deepcopy(persona["demo"]["info_response"])}


def approve_body(recommendation):
    return {
        "outcome": "APPROVE",
        "amount": recommendation["offer"]["amount"],
        "term_months": recommendation["offer"]["term_months"],
        "comment": "Одобрено по рекомендации системы после проверки",
    }


def expected_client(persona):
    expected = persona["demo"]["expected"]
    expected = expected.get("after_info", expected)
    return {
        "state": expected["state"],
        "offer": deepcopy(expected.get("offer")),
        "client_reason": (
            {"code": expected["client_reason_code"]}
            if "client_reason_code" in expected
            else None
        ),
    }


def expected_bank(persona):
    expected = persona["demo"]["expected"]
    expected = expected.get("after_info", expected)
    numbers = expected.get("recommendation", expected)
    result = {
        "grade": numbers["grade"],
        "score": numbers["score"],
        "points": deepcopy(numbers.get("points", {})),
    }
    key = "route_reason" if "route_reason" in expected else "outcome"
    result[key] = expected[key]
    return result
