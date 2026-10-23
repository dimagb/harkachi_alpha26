"""HTTP-клиент сценариев с диагностикой шага и контролем утечек."""

import json
import os
import time

import httpx

DEFAULT_BASE_URL = "http://localhost:8080/api/v1"
PROCESSING = frozenset({"SUBMITTED", "VALIDATION", "ENRICHMENT", "ASSESSMENT"})
INTERNAL_KEYS = frozenset(
    {
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
    }
)


def assert_client_safe(data, raw_text):
    assert "SF_ADDITIONAL" not in raw_text, "Утечка клиенту: SF_ADDITIONAL"
    if isinstance(data, dict):
        forbidden = INTERNAL_KEYS.intersection(data)
        assert not forbidden, f"Утечка клиенту: {sorted(forbidden)}"
        for value in data.values():
            assert_client_safe(value, "")
    elif isinstance(data, list):
        for value in data:
            assert_client_safe(value, "")


class ApiClient:
    def __init__(self, base_url=None, *, transport=None):
        self.http = httpx.Client(
            base_url=(base_url or os.getenv("E2E_BASE_URL", DEFAULT_BASE_URL)).rstrip(
                "/"
            )
            + "/",
            transport=transport,
            timeout=5,
            trust_env=False,
        )

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.http.close()

    def request(self, step, method, path, *, client_view=False, **kwargs):
        try:
            response = self.http.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise AssertionError(f"Шаг {step}: HTTP недоступен — {exc}") from exc
        if not response.is_success:
            try:
                error = response.json()["error"]
                code, message = error["code"], error["message"]
            except (ValueError, KeyError, TypeError):
                code, message = "", response.text
            raise AssertionError(
                f"Шаг {step}: HTTP {response.status_code} {code} — {message}"
            )
        data = response.json()
        if client_view:
            assert_client_safe(data, response.text)
        return data

    def login(self, login):
        data = self.request(
            "login",
            "POST",
            "auth/login",
            json={"login": login, "password": os.getenv("E2E_PASSWORD", "demo2026")},
        )
        token = data["access_token"]
        self.http.headers["Authorization"] = f"Bearer {token}"
        return token

    def me(self):
        return self.request("me", "GET", "me")

    def create_application(self, body):
        return self.request(
            "create", "POST", "applications", json=body, client_view=True
        )

    def get_application(self, app_id, **kwargs):
        return self.request(
            "get", "GET", f"applications/{app_id}", client_view=True, **kwargs
        )

    def list_applications(self, company_id):
        return self.request(
            "list",
            "GET",
            "applications",
            params={"company_id": company_id},
            client_view=True,
        )

    def otp(self, app_id, purpose, *, party_id=None):
        body = {"purpose": purpose}
        if party_id is not None:
            body["party_id"] = party_id
        return self.request("otp", "POST", f"applications/{app_id}/otp", json=body)

    def submit(self, app_id, body):
        return self.request(
            "submit",
            "POST",
            f"applications/{app_id}/submit",
            json=body,
            client_view=True,
        )

    def info_response(self, app_id, body):
        return self.request(
            "info-response",
            "POST",
            f"applications/{app_id}/info-response",
            json=body,
            client_view=True,
        )

    def accept_offer(self, app_id, offer_version):
        return self.request(
            "accept",
            "POST",
            f"applications/{app_id}/offer/accept",
            json={"offer_version": offer_version},
            client_view=True,
        )

    def sign(self, app_id, body):
        return self.request(
            "sign", "POST", f"applications/{app_id}/sign", json=body, client_view=True
        )

    def bank_application(self, app_id):
        return self.request("bank", "GET", f"underwriting/applications/{app_id}")

    def decide(self, app_id, body):
        return self.request(
            "decision", "POST", f"underwriting/{app_id}/decision", json=body
        )


def wait_state(client, app_id, *, leave=PROCESSING):
    deadline = time.monotonic() + float(os.getenv("E2E_TIMEOUT", "60"))
    while True:
        remaining = deadline - time.monotonic()
        application = client.get_application(app_id, timeout=max(0.001, remaining))
        if application["state"] not in leave:
            return application
        remaining = deadline - time.monotonic()
        assert remaining > 0, (
            f"Шаг wait: state={application['state']}; "
            f"timeline={json.dumps(application['timeline'], ensure_ascii=False)}"
        )
        time.sleep(min(1, remaining))
