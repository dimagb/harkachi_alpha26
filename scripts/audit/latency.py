"""Замеры локального демостенда; создаёт четыре заявки ip_good.

Запуск из корня: uv run --no-project --python 3.12 --with httpx python
-X utf8 scripts/audit/latency.py
"""

import argparse
import json
import math
import os
import platform
import statistics
import sys
import time
from datetime import UTC, datetime

import httpx


def summarize(values):
    """Медиана, p95 методом nearest rank и максимум, в миллисекундах."""
    if not values:
        raise ValueError("Нужен хотя бы один замер")
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "p50_ms": round(statistics.median(ordered), 3),
        "p95_ms": round(ordered[math.ceil(0.95 * len(ordered)) - 1], 3),
        "max_ms": round(ordered[-1], 3),
    }


def request(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    if response.status_code != 200:
        raise RuntimeError(f"{method} {path}: ожидался 200")
    return response.json()


def login(client, user, password):
    data = request(
        client, "POST", "auth/login", json={"login": user, "password": password}
    )
    return {"Authorization": f"Bearer {data['access_token']}"}


def submit(client, headers, company_id):
    application = request(
        client,
        "POST",
        "applications",
        headers=headers,
        json={
            "company_id": company_id,
            "product_code": "EXPRESS",
            "amount": 1_000_000,
            "term_months": 12,
            "purpose": "WORKING_CAPITAL",
            "declared_revenue_year": 12_000_000,
        },
    )
    path = f"applications/{application['id']}"
    otp = request(
        client, "POST", f"{path}/otp", headers=headers, json={"purpose": "CONSENTS"}
    )
    started = time.perf_counter()
    request(
        client,
        "POST",
        f"{path}/submit",
        headers=headers,
        json={
            "otp_id": otp["otp_id"],
            "code": otp["demo_code"],
            "consents": {"pdn": True, "bki": True, "auto_decision": True},
        },
    )
    return application["id"], started


def await_decision(client, headers, application_id, started, timeout=120):
    path = f"applications/{application_id}"
    while time.perf_counter() - started < timeout:
        application = request(client, "GET", path, headers=headers)
        if application["state"] == "OFFER_ISSUED":
            return round(time.perf_counter() - started, 3)
        if application["state"] in {"DECLINED", "MANUAL_REVIEW", "INFO_REQUESTED"}:
            raise RuntimeError(f"ip_good: неожиданный исход {application['state']}")
        time.sleep(0.2)
    raise TimeoutError("Решение по ip_good не получено за 120 секунд")


def measure(client, method, path, headers, **kwargs):
    request(client, method, path, headers=headers, **kwargs)  # Прогрев вне выборки.
    samples = []
    for _ in range(50):
        started = time.perf_counter()
        request(client, method, path, headers=headers, **kwargs)
        samples.append((time.perf_counter() - started) * 1000)
    return summarize(samples)


def run(base_url, password):
    with httpx.Client(base_url=base_url, timeout=15, trust_env=False) as client:
        customer = login(client, "ip_good", password)
        bank = login(client, "underwriter", password)
        me = request(client, "GET", "me", headers=customer)
        company_id = me["companies"][0]["company"]["id"]
        decisions = []
        for _ in range(3):
            application_id, started = submit(client, customer, company_id)
            decisions.append(await_decision(client, customer, application_id, started))

        # Четвёртая заявка даёт фоновую работу конвейера в начале серии GET.
        background_id, background_started = submit(client, customer, company_id)
        calculator = {"product_code": "EXPRESS", "amount": 1_000_000, "term_months": 12}
        measurements = []
        endpoints = [
            ("GET", f"applications/{application_id}", customer, {}),
            ("GET", "applications", customer, {"params": {"company_id": company_id}}),
            ("GET", "underwriting/queue", bank, {}),
            ("GET", "bank/applications", bank, {}),
            ("GET", f"underwriting/applications/{application_id}", bank, {}),
            ("POST", "calculator", customer, {"json": calculator}),
        ]
        for method, path, headers, kwargs in endpoints:
            measurements.append(
                {
                    "method": method,
                    "path": path,
                    **measure(client, method, path, headers, **kwargs),
                }
            )
        background_seconds = await_decision(
            client, customer, background_id, background_started
        )
        return {
            "at_utc": datetime.now(UTC).isoformat(),
            "base_url": base_url,
            "python": platform.python_version(),
            "httpx": httpx.__version__,
            "conditions": (
                "ноутбук, Docker Desktop, 1 пользователь, "
                "пауза конвейера 2 с между шагами"
            ),
            "methodology": (
                "50 последовательных запросов на эндпоинт; один прогрев исключён; "
                "p50 — медиана, p95 — nearest rank; polling решения 0,2 с; "
                "фоновая заявка активна в начале серии, затем может завершиться"
            ),
            "decision_seconds": decisions,
            "decision_median_seconds": statistics.median(decisions),
            "background_application_id": background_id,
            "background_observed_seconds": background_seconds,
            "measurements": measurements,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8080/api/v1/")
    args = parser.parse_args()
    try:
        result = run(
            args.base_url.rstrip("/") + "/", os.getenv("DEMO_PASSWORD", "demo2026")
        )
    except (httpx.HTTPError, RuntimeError, TimeoutError, KeyError, IndexError) as error:
        print(f"Замеры прерваны: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
