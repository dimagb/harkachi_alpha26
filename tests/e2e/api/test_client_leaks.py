"""A-09a, OWASP API3/API8: клиент не видит внутренних полей банка."""

import json
import re
import time
import uuid
from pathlib import Path

import pytest
from client import ApiClient, assert_api_error, assert_client_safe, raw
from flows import approve_body, create_body, submit_body
from jsonschema import Draft202012Validator
from test_personas import find_persona

ROOT = Path(__file__).resolve().parents[3]
OPENAPI = json.loads((ROOT / "contracts/openapi.json").read_text(encoding="utf-8"))
PROCESSING = {"SUBMITTED", "VALIDATION", "ENRICHMENT", "ASSESSMENT"}


def response_schema(method, path):
    """Схема ответа 200 из снимка OpenAPI по шаблону пути."""
    for template, methods in OPENAPI["paths"].items():
        pattern = re.sub(r"\{[^}]+\}", "[^/]+", template.removeprefix("/api/v1/"))
        if re.fullmatch(pattern, path) and method.lower() in methods:
            content = methods[method.lower()]["responses"]["200"]["content"]
            return content["application/json"]["schema"]
    raise AssertionError(f"Нет пути в OpenAPI: {method} {path}")


class ClientView:
    """Все ответы клиенту: схема без лишних полей + assert_client_safe."""

    def __init__(self, login):
        with ApiClient() as api:
            self.token = api.login(login)
            self.me = api.me()
        self.texts = []

    def __call__(self, method, path, **kwargs):
        response = raw(self.token, method, path, **kwargs)
        assert response.is_success, f"{method} {path}: {response.text[:200]}"
        data = response.json()
        Draft202012Validator(
            {**response_schema(method, path), "components": OPENAPI["components"]}
        ).validate(data)
        assert_client_safe(data, response.text)
        self.texts.append(response.text)
        return data


def run_client_path(view, persona):
    """Полный клиентский путь до решения; каждый ответ проходит проверку."""
    company_id = view.me["companies"][0]["company"]["id"]
    app = persona["demo"]["app"]
    view("GET", "me")
    view("GET", "products")
    view(
        "POST",
        "calculator",
        json={
            "product_code": app["product"],
            "amount": app["amount"],
            "term_months": app["term"],
        },
    )
    view("GET", f"companies/{company_id}/profile")
    created = view("POST", "applications", json=create_body(persona, company_id))
    app_id = created["id"]
    view(
        "PATCH",
        f"applications/{app_id}",
        json={"amount": app["amount"]},
        headers={"If-Match": str(created["version"])},
    )
    otp = view("POST", f"applications/{app_id}/otp", json={"purpose": "CONSENTS"})
    view(
        "POST",
        f"applications/{app_id}/submit",
        json=submit_body(persona, otp["otp_id"], otp["demo_code"]),
    )
    deadline = time.monotonic() + 60
    while True:
        application = view("GET", f"applications/{app_id}")
        if application["state"] not in PROCESSING:
            break
        assert time.monotonic() < deadline, application["state"]
        time.sleep(0.5)
    view("GET", "applications", params={"company_id": company_id})
    return application


@pytest.mark.parametrize("code", ["ooo_aml", "ip_bad"])
def test_declined_client_sees_no_internals(code, persona_data):
    persona = find_persona(persona_data, code)
    view = ClientView(code)
    application = run_client_path(view, persona)
    assert application["state"] == "DECLINED"
    assert application["client_reason"] is not None
    if code == "ip_bad":
        objected = view(
            "POST",
            f"applications/{application['id']}/objection",
            json={"text": "Прошу пересмотреть решение: задолженность погашена"},
        )
        assert objected["state"] == "MANUAL_REVIEW"
        view("GET", f"applications/{application['id']}")


def test_underwriter_comment_hidden_from_client(bank, persona_data):
    persona = find_persona(persona_data, "ooo_border")
    view = ClientView("ooo_border")
    application = run_client_path(view, persona)
    assert application["state"] == "MANUAL_REVIEW"
    app_id = application["id"]
    marker = f"Внутренний комментарий {uuid.uuid4().hex[:12]}"
    body = approve_body(persona["demo"]["expected"]["recommendation"])
    bank.decide(app_id, {**body, "comment": marker})
    assert marker in json.dumps(bank.bank_application(app_id), ensure_ascii=False)

    application = view("GET", f"applications/{app_id}")
    assert application["state"] == "OFFER_ISSUED"
    company_id = view.me["companies"][0]["company"]["id"]
    view("GET", "applications", params={"company_id": company_id})
    view(
        "POST",
        f"applications/{app_id}/offer/accept",
        json={"offer_version": application["offer"]["version"]},
    )
    for text in view.texts:
        assert marker not in text, "Комментарий андеррайтера виден клиенту"


@pytest.mark.parametrize("auth", [True, False], ids=["with_token", "anon"])
def test_unknown_path_and_wrong_method_are_api_errors(auth):
    token = None
    if auth:
        with ApiClient() as api:
            token = api.login("ip_good")
    assert_api_error(raw(token, "GET", "no-such-path"), 404, "NOT_FOUND")
    assert_api_error(raw(token, "GET", f"no/such/{uuid.uuid4()}"), 404, "NOT_FOUND")
    # api-types.ts: «405 → NOT_FOUND».
    assert_api_error(raw(token, "DELETE", "me"), 405, "NOT_FOUND")
    assert_api_error(raw(token, "PUT", "products"), 405, "NOT_FOUND")


def test_malformed_json_is_clean_validation_error():
    response = raw(
        None,
        "POST",
        "auth/login",
        content=b'{"login": ',
        headers={"Content-Type": "application/json"},
    )
    assert_api_error(response, 422, "VALIDATION_ERROR")
