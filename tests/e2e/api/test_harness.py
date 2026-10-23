"""Офлайн-проверки API-сценариев: контракт, ожидания и транспорт."""

import importlib
import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
DATA = json.loads((ROOT / "contracts/personas.json").read_text(encoding="utf-8"))
PERSONAS = DATA["personas"]
OPENAPI = json.loads((ROOT / "contracts/openapi.json").read_text(encoding="utf-8"))


def validate(name, body):
    Draft202012Validator(
        {"$ref": f"#/components/schemas/{name}", "components": OPENAPI["components"]}
    ).validate(body)


@pytest.mark.parametrize("persona", PERSONAS, ids=lambda p: p["code"])
def test_request_bodies_preserve_demo_and_match_openapi(persona):
    flows = importlib.import_module("flows")
    original = deepcopy(persona)
    app = persona["demo"]["app"]
    body = flows.create_body(persona, "company-id")
    assert body == {
        "company_id": "company-id",
        "product_code": app["product"],
        "amount": app["amount"],
        "term_months": app["term"],
        "purpose": app["purpose"],
        "declared_revenue_year": app["declared_revenue_year"],
        **({"purpose_text": app["purpose_text"]} if "purpose_text" in app else {}),
    }
    validate("ApplicationCreate", body)
    submitted = flows.submit_body(persona, "otp-id", "123456")
    assert submitted == {
        "otp_id": "otp-id",
        "code": "123456",
        "consents": persona["demo"]["consents"],
    }
    validate("SubmitRequest", submitted)
    if "info_response" in persona["demo"]:
        answer = flows.info_response_body(persona)
        assert answer == {"answers": persona["demo"]["info_response"]}
        validate("InfoResponseRequest", answer)
    if "recommendation" in persona["demo"]["expected"]:
        recommendation = persona["demo"]["expected"]["recommendation"]
        approval = flows.approve_body(recommendation)
        assert approval == {
            "outcome": "APPROVE",
            "amount": recommendation["offer"]["amount"],
            "term_months": recommendation["offer"]["term_months"],
            "comment": "Одобрено по рекомендации системы после проверки",
        }
        validate("UnderwriterDecisionRequest", approval)
    assert persona == original


@pytest.mark.parametrize("persona", PERSONAS, ids=lambda p: p["code"])
def test_expectations_come_from_golden_data(persona):
    flows = importlib.import_module("flows")
    golden = persona["demo"]["expected"]
    if persona["code"] == "ooo_gap":
        golden = golden["after_info"]
    client = flows.expected_client(persona)
    assert client["state"] == golden["state"]
    assert client["offer"] == golden.get("offer")
    assert client["client_reason"] == (
        {"code": golden["client_reason_code"]}
        if "client_reason_code" in golden
        else None
    )
    assert set(client) == {"state", "offer", "client_reason"}
    bank = flows.expected_bank(persona)
    if persona["code"] == "ooo_border":
        numbers = golden["recommendation"]
        assert bank["route_reason"] == golden["route_reason"]
        assert "outcome" not in bank
    else:
        numbers = golden
        assert bank["outcome"] == golden["outcome"]
    assert bank["grade"] == numbers["grade"]
    assert bank["score"] == numbers["score"]
    assert bank["points"] == numbers.get("points", {})


def test_client_routes_bearer_and_request_payloads(monkeypatch):
    api = importlib.import_module("client")
    monkeypatch.setenv("E2E_PASSWORD", "test-password")
    expected = iter(
        [
            ("POST", "/auth/login", {"login": "person", "password": "test-password"}),
            ("GET", "/me", None),
            ("POST", "/applications", {"company_id": "co"}),
            ("GET", "/applications/app", None),
            ("GET", "/applications?company_id=co", None),
            ("POST", "/applications/app/otp", {"purpose": "CONSENTS"}),
            ("POST", "/applications/app/submit", {"code": "123456"}),
            ("POST", "/applications/app/info-response", {"answers": []}),
            ("POST", "/applications/app/offer/accept", {"offer_version": 1}),
            (
                "POST",
                "/applications/app/otp",
                {"purpose": "GUARANTEE", "party_id": "party"},
            ),
            ("POST", "/applications/app/sign", {"party_id": "party"}),
            ("GET", "/underwriting/applications/app", None),
            ("POST", "/underwriting/app/decision", {"outcome": "APPROVE"}),
        ]
    )
    seen = []

    def handle(request):
        method, suffix, body = next(expected)
        assert request.method == method
        assert str(request.url) == "http://test/api/v1" + suffix
        assert (json.loads(request.content) if request.content else None) == body
        if suffix != "/auth/login":
            assert request.headers["Authorization"] == "Bearer token"
        seen.append(suffix)
        return httpx.Response(200, json={"access_token": "token"})

    with api.ApiClient(
        "http://test/api/v1", transport=httpx.MockTransport(handle)
    ) as c:
        assert c.login("person") == "token"
        c.me()
        c.create_application({"company_id": "co"})
        c.get_application("app")
        c.list_applications("co")
        c.otp("app", "CONSENTS")
        c.submit("app", {"code": "123456"})
        c.info_response("app", {"answers": []})
        c.accept_offer("app", 1)
        c.otp("app", "GUARANTEE", party_id="party")
        c.sign("app", {"party_id": "party"})
        c.bank_application("app")
        c.decide("app", {"outcome": "APPROVE"})
    assert len(seen) == 13
    with pytest.raises(StopIteration):
        next(expected)


def test_wait_state_returns_first_non_processing_state(monkeypatch):
    api = importlib.import_module("client")
    states = iter(["SUBMITTED", "VALIDATION", "OFFER_ISSUED"])
    delays = []
    monkeypatch.setattr(api.time, "sleep", delays.append)
    with api.ApiClient(
        "http://test/api/v1",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"state": next(states), "timeline": []})
        ),
    ) as c:
        assert api.wait_state(c, "app")["state"] == "OFFER_ISSUED"
    assert delays == [1, 1]


def test_wait_state_timeout_reports_last_state_and_timeline(monkeypatch):
    api = importlib.import_module("client")
    monkeypatch.setenv("E2E_TIMEOUT", "2")
    now = [0]
    delays = []

    def advance(seconds):
        delays.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(api.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(api.time, "sleep", advance)
    with (
        api.ApiClient(
            "http://test/api/v1",
            transport=httpx.MockTransport(
                lambda r: httpx.Response(
                    200,
                    json={"state": "VALIDATION", "timeline": [{"title": "Проверка"}]},
                )
            ),
        ) as c,
        pytest.raises(AssertionError, match="VALIDATION.*timeline.*Проверка"),
    ):
        api.wait_state(c, "app")
    assert now[0] == 2
    assert delays == [1, 1]


def test_wait_state_supports_signing_states(monkeypatch):
    api = importlib.import_module("client")
    states = iter(["SIGNING", "SIGNED", "DISBURSED"])
    monkeypatch.setattr(api.time, "sleep", lambda seconds: None)
    with api.ApiClient(
        "http://test/api/v1",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"state": next(states), "timeline": []})
        ),
    ) as c:
        assert api.wait_state(c, "app", leave={"SIGNING", "SIGNED"})["state"] == (
            "DISBURSED"
        )


def test_http_error_names_step_and_api_error():
    api = importlib.import_module("client")
    with (
        api.ApiClient(
            "http://test/api/v1",
            transport=httpx.MockTransport(
                lambda r: httpx.Response(
                    501,
                    json={
                        "error": {
                            "code": "NOT_IMPLEMENTED",
                            "message": "Ещё не реализовано",
                            "details": {},
                        }
                    },
                )
            ),
        ) as c,
        pytest.raises(
            AssertionError,
            match="Шаг submit: HTTP 501 NOT_IMPLEMENTED — Ещё не реализовано",
        ),
    ):
        c.submit("app", {})


@pytest.mark.parametrize(
    "secret",
    [
        "score",
        "grade",
        "points",
        "factors",
        "rules_fired",
        "internal_reasons",
        "risk_flags",
        "risk_flag",
        "inputs_snapshot",
        "route_reason",
    ],
)
@pytest.mark.parametrize("as_list", [False, True])
def test_client_rejects_internal_keys_at_any_depth(secret, as_list):
    api = importlib.import_module("client")
    payload = {"nested": [{"details": {secret: None}}]}
    with (
        api.ApiClient(
            "http://test/api/v1",
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json=[payload] if as_list else payload)
            ),
        ) as c,
        pytest.raises(AssertionError, match=secret),
    ):
        c.list_applications("co") if as_list else c.get_application("app")


def test_client_rejects_internal_reason_in_text():
    api = importlib.import_module("client")
    with (
        api.ApiClient(
            "http://test/api/v1",
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"text": "Причина SF_ADDITIONAL"})
            ),
        ) as c,
        pytest.raises(AssertionError, match="SF_ADDITIONAL"),
    ):
        c.get_application("app")


@pytest.mark.parametrize("status", [None, 503])
def test_unavailable_ready_reports_stand_url(status):
    config = importlib.import_module("conftest")

    def handle(request):
        assert str(request.url) == "http://test/api/v1/ready"
        if status is None:
            raise httpx.ConnectError("Нет соединения", request=request)
        return httpx.Response(status)

    with pytest.raises(
        BaseException, match="Стенд недоступен: http://test/api/v1"
    ) as err:
        config.require_ready(
            "http://test/api/v1", transport=httpx.MockTransport(handle)
        )
    assert err.type.__name__ == "Skipped"


def test_available_ready_allows_live_collection():
    config = importlib.import_module("conftest")
    config.require_ready(
        "http://test/api/v1",
        transport=httpx.MockTransport(lambda r: httpx.Response(200)),
    )


@pytest.mark.parametrize("persona", PERSONAS, ids=lambda p: p["code"])
def test_live_comparisons_detect_wrong_offer_reason_or_score(persona):
    live = importlib.import_module("test_personas")
    flows = importlib.import_module("flows")
    expected = flows.expected_client(persona)
    actual = deepcopy(expected)
    live.assert_client(actual, expected)
    if actual["offer"] is not None:
        actual["offer"]["monthly_payment"] += 1
    elif actual["client_reason"] is not None:
        actual["client_reason"]["code"] = "wrong-reason"
    else:
        actual["state"] = "OFFER_ISSUED"
    with pytest.raises(AssertionError):
        live.assert_client(actual, expected)
    expected_bank = flows.expected_bank(persona)
    auto = {
        "kind": "AUTO",
        "grade": expected_bank["grade"],
        "score": expected_bank["score"],
        "factors": [
            {"code": code, "points": points}
            for code, points in expected_bank["points"].items()
        ],
        **{k: v for k, v in expected_bank.items() if k in {"outcome", "route_reason"}},
    }
    live.assert_bank({"decisions": [auto]}, expected_bank)
    auto["score"] = "wrong-score"
    with pytest.raises(AssertionError):
        live.assert_bank({"decisions": [auto]}, expected_bank)
