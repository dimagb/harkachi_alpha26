"""A-09a, OWASP API1/API2/API5: матрица «эндпоинт × кто» по contracts/api.md."""

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest
from client import ApiClient, assert_api_error, broken_token, raw, wait_state
from flows import create_body
from test_personas import find_persona

# kind: me — все роли; catalog — клиент и андеррайтер (B-11); client — клиент без
# объекта; company/app — объект клиента;
# bank/bank_app — андеррайтер; reserved — Б2, путь зарезервирован и не реализован.
ENDPOINTS = (
    ("me", "GET", "me", "me"),
    ("products", "GET", "products", "catalog"),
    ("calculator", "POST", "calculator", "client"),
    ("profile", "GET", "companies/{company}/profile", "company"),
    ("create", "POST", "applications", "company"),
    ("patch", "PATCH", "applications/{app}", "app"),
    ("list", "GET", "applications", "company"),
    ("get", "GET", "applications/{app}", "app"),
    ("request-signature", "POST", "applications/{app}/request-signature", "app"),
    ("otp", "POST", "applications/{app}/otp", "app"),
    ("submit", "POST", "applications/{app}/submit", "app"),
    ("info-response", "POST", "applications/{app}/info-response", "app"),
    ("offer-accept", "POST", "applications/{app}/offer/accept", "app"),
    ("offer-reject", "POST", "applications/{app}/offer/reject", "app"),
    ("sign", "POST", "applications/{app}/sign", "app"),
    ("withdraw", "POST", "applications/{app}/withdraw", "app"),
    ("objection", "POST", "applications/{app}/objection", "app"),
    ("queue", "GET", "underwriting/queue", "bank"),
    ("bank-card", "GET", "underwriting/applications/{app}", "bank_app"),
    ("decision", "POST", "underwriting/{app}/decision", "bank_app"),
    ("journal", "GET", "bank/applications", "bank"),
    ("time-shift", "POST", "demo/time-shift", "bank_app"),
    ("preview", "POST", "preview", "reserved"),
)
# api.md (ee33fae): без права подписи → 403 SIGN_NOT_ALLOWED.
SIGN_RIGHT_ACTIONS = frozenset(
    {"otp", "submit", "offer-accept", "offer-reject", "objection"}
)
DESTRUCTIVE = frozenset({"withdraw", "offer-reject"})
ACTORS = (
    "own",
    "other",
    "accountant",
    "underwriter",
    "anon",
    "tampered",
    "forged",
    "alg_none",
)
BROKEN = frozenset({"tampered", "forged", "alg_none"})
MATRIX = {}


@dataclass
class Target:
    login: str
    token: str
    company_id: str
    app_id: str


def login(code):
    with ApiClient() as api:
        token = api.login(code)
        me = api.me()
    company_id = me["companies"][0]["company"]["id"] if me["companies"] else None
    return token, company_id


def new_draft(persona, token, company_id):
    response = raw(token, "POST", "applications", json=create_body(persona, company_id))
    assert response.status_code == 200, response.text[:200]
    return response.json()["id"]


@pytest.fixture(scope="module")
def world(persona_data):
    targets = {}
    for code in ("ip_good", "ooo_gap"):
        token, company_id = login(code)
        persona = find_persona(persona_data, code)
        targets[code] = Target(
            code, token, company_id, new_draft(persona, token, company_id)
        )
    acc_token, load_company = login("ooo_load_accountant")
    load = find_persona(persona_data, "ooo_load")
    targets["ooo_load"] = Target(
        "ooo_load_accountant",
        acc_token,
        load_company,
        new_draft(load, acc_token, load_company),
    )
    uw_token, _ = login(persona_data["staff"][0]["login"])
    yield {"targets": targets, "underwriter": uw_token, "personas": persona_data}
    out = os.getenv("ACCESS_MATRIX_REPORT")
    if out:
        Path(out).write_text(
            json.dumps(MATRIX, ensure_ascii=False, indent=1), encoding="utf-8"
        )


def body_for(name, target, persona):
    if name == "calculator":
        return {"product_code": "EXPRESS", "amount": 1_000_000, "term_months": 12}
    if name == "create":
        return create_body(persona, target.company_id)
    if name == "patch":
        return {"amount": 1_400_000}
    if name == "otp":
        return {"purpose": "CONSENTS"}
    if name == "submit":
        consents = {"pdn": True, "bki": True, "auto_decision": True}
        return {"otp_id": str(uuid.uuid4()), "code": "000000", "consents": consents}
    if name == "info-response":
        answer = {"item_code": "REVENUE_CONFIRM", "value": 1, "comment": "Проверка"}
        return {"answers": [answer]}
    if name == "offer-accept":
        return {"offer_version": 1}
    if name == "sign":
        return {
            "otp_id": str(uuid.uuid4()),
            "code": "000000",
            "party_id": str(uuid.uuid4()),
        }
    if name == "objection":
        return {"text": "Прошу пересмотреть решение по заявке"}
    if name == "decision":
        return {
            "outcome": "DECLINE",
            "client_reason_category": "Долговая нагрузка",
            "comment": "Проверка доступа",
        }
    if name == "time-shift":
        return {"application_id": target.app_id, "days": 1}
    if name == "preview":
        return {
            "company_id": target.company_id,
            "product_code": "EXPRESS",
            "amount": 1_000_000,
            "term_months": 12,
        }
    return None


def call(name, method, template, token, target, persona, app_id=None):
    app_id = app_id or target.app_id
    path = template.format(company=target.company_id, app=app_id)
    kwargs = {}
    body = body_for(name, target, persona)
    if body is not None:
        kwargs["json"] = body
    if name == "list":
        kwargs["params"] = {"company_id": target.company_id}
    if name == "journal":
        kwargs["params"] = {"size": 1}
    if name == "patch":
        # Верная версия: иначе 409 CONFLICT_VERSION закроет проверку доступа.
        version = raw(target.token, "GET", f"applications/{app_id}").json()["version"]
        kwargs["headers"] = {"If-Match": str(version)}
    return raw(token, method, path, **kwargs)


def assert_access_passed(response):
    """Доступ пройден: дальше — бизнес-ответ (200, 409, 422, 403 правила)."""
    assert response.status_code not in (401, 404, 500), response.text[:200]
    if response.status_code == 403:
        assert response.json()["error"]["code"] != "FORBIDDEN", response.text[:200]
    if not response.is_success:
        assert_api_error(response, response.status_code)


@pytest.mark.parametrize("actor", ACTORS)
@pytest.mark.parametrize(
    ("name", "method", "template", "kind"), ENDPOINTS, ids=[e[0] for e in ENDPOINTS]
)
def test_access(world, name, method, template, kind, actor):
    targets = world["targets"]
    personas = world["personas"]
    ip_good = find_persona(personas, "ip_good")
    seen = []

    def record(response):
        seen.append(response.status_code)
        MATRIX.setdefault(name, {})[actor] = "/".join(map(str, seen))
        return response

    if kind == "reserved":
        target = targets["ip_good"]
        token = None if actor == "anon" else target.token
        response = record(call(name, method, template, token, target, ip_good))
        assert_api_error(response, 404, "NOT_FOUND")
        return

    if actor in {"anon", *BROKEN}:
        target = targets["ip_good"]
        token = None if actor == "anon" else broken_token(target.token, actor)
        response = record(call(name, method, template, token, target, ip_good))
        assert_api_error(response, 401, "UNAUTHORIZED")
        return

    if actor == "underwriter":
        target = targets["ip_good"]
        response = record(
            call(name, method, template, world["underwriter"], target, ip_good)
        )
        if kind in {"company", "app", "client"}:
            assert_api_error(response, 403, "FORBIDDEN")
        else:
            assert_access_passed(response)
        return

    if actor == "accountant":
        target = targets["ooo_load"]
        persona = find_persona(personas, "ooo_load")
        app_id = None
        if name in DESTRUCTIVE:
            app_id = new_draft(persona, target.token, target.company_id)
        response = record(
            call(name, method, template, target.token, target, persona, app_id)
        )
        if kind in {"bank", "bank_app"}:
            assert_api_error(response, 403, "FORBIDDEN")
        elif name in SIGN_RIGHT_ACTIONS:
            assert_api_error(response, 403, "SIGN_NOT_ALLOWED")
        else:
            assert_access_passed(response)
        return

    # Клиент: своя заявка и чужая, в обе стороны (ip_good ↔ ooo_gap).
    for owner, stranger in (("ip_good", "ooo_gap"), ("ooo_gap", "ip_good")):
        target = targets[owner]
        persona = find_persona(personas, owner)
        if actor == "own":
            app_id = None
            if name in DESTRUCTIVE:
                app_id = new_draft(persona, target.token, target.company_id)
            response = record(
                call(name, method, template, target.token, target, persona, app_id)
            )
            if kind in {"bank", "bank_app"}:
                assert_api_error(response, 403, "FORBIDDEN")
            else:
                assert_access_passed(response)
        else:
            token = targets[stranger].token
            response = record(call(name, method, template, token, target, persona))
            if kind in {"bank", "bank_app"}:
                assert_api_error(response, 403, "FORBIDDEN")
            elif kind in {"company", "app"}:
                assert_api_error(response, 404, "NOT_FOUND")
            else:
                assert_access_passed(response)


def test_role_swap_in_token_rejected(world):
    """Роль в JWT подменена без подписи → 401, не доступ андеррайтера."""
    token = broken_token(world["targets"]["ip_good"].token, "role_swap")
    for path in ("underwriting/queue", "bank/applications", "me"):
        assert_api_error(raw(token, "GET", path), 401, "UNAUTHORIZED")


def test_accountant_cannot_sign_or_accept(client, persona_data):
    """Бухгалтер ooo_load без права подписи: submit, otp, offer/*, sign → 403."""
    persona = find_persona(persona_data, "ooo_load")
    acc_token, company_id = login("ooo_load_accountant")
    app_id = new_draft(persona, acc_token, company_id)
    consents = {"pdn": True, "bki": True, "auto_decision": False}
    submit = {"otp_id": str(uuid.uuid4()), "code": "000000", "consents": consents}
    response = raw(acc_token, "POST", f"applications/{app_id}/submit", json=submit)
    assert_api_error(response, 403, "SIGN_NOT_ALLOWED")

    client.login("ooo_load")
    otp = client.otp(app_id, "CONSENTS")
    client.submit(
        app_id,
        {"otp_id": otp["otp_id"], "code": otp["demo_code"], "consents": consents},
    )
    application = wait_state(client, app_id)
    assert application["state"] == "OFFER_ISSUED"
    accept = {"offer_version": application["offer"]["version"]}
    response = raw(
        acc_token, "POST", f"applications/{app_id}/offer/accept", json=accept
    )
    assert_api_error(response, 403, "SIGN_NOT_ALLOWED")
    response = raw(acc_token, "POST", f"applications/{app_id}/offer/reject")
    assert_api_error(response, 403, "SIGN_NOT_ALLOWED")
    party_id = application["parties"][0]["id"] if application["parties"] else None
    otp_body = {"purpose": "OFFER", **({"party_id": party_id} if party_id else {})}
    response = raw(acc_token, "POST", f"applications/{app_id}/otp", json=otp_body)
    assert_api_error(response, 403, "SIGN_NOT_ALLOWED")
    assert client.get_application(app_id)["state"] == "OFFER_ISSUED"

    application = client.accept_offer(app_id, application["offer"]["version"])
    assert application["state"] == "SIGNING"
    for party in application["parties"]:
        purpose = {"BORROWER_SIGNATORY": "OFFER", "GUARANTOR": "GUARANTEE"}[
            party["role"]
        ]
        otp = client.otp(app_id, purpose, party_id=party["id"])
        sign = {
            "otp_id": otp["otp_id"],
            "code": otp["demo_code"],
            "party_id": party["id"],
        }
        response = raw(acc_token, "POST", f"applications/{app_id}/sign", json=sign)
        assert_api_error(response, 403, "SIGN_NOT_ALLOWED")
    assert client.get_application(app_id)["state"] == "SIGNING"


NOT_UUID_PATHS = (
    ("GET", "applications/abc", "ip_good"),
    ("POST", "applications/abc/withdraw", "ip_good"),
    ("GET", "underwriting/applications/abc", "underwriter"),
    ("POST", "underwriting/abc/decision", "underwriter"),
    ("GET", "companies/abc/profile", "ip_good"),
)


def _not_uuid_call(world, method, path, who):
    token = (
        world["underwriter"] if who == "underwriter" else world["targets"][who].token
    )
    kwargs = {}
    if path.endswith("decision"):
        kwargs["json"] = body_for("decision", None, None)
    return raw(token, method, path, **kwargs)


@pytest.mark.parametrize(("method", "path", "who"), NOT_UUID_PATHS)
def test_not_uuid_id_is_clean_client_error(world, method, path, who):
    """id не UUID → 404 или 422 VALIDATION_ERROR, не 500 (решение тимлида 24.10)."""
    response = _not_uuid_call(world, method, path, who)
    assert response.status_code in (404, 422), response.text[:200]
    code = {404: "NOT_FOUND", 422: "VALIDATION_ERROR"}[response.status_code]
    assert_api_error(response, response.status_code, code)
