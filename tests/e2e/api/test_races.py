"""A-09a, OWASP API6: двойные запросы и перезапуск worker."""

import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest
from client import ApiClient, assert_api_error, raw
from flows import approve_body, create_body, submit_body
from test_personas import find_persona, start_application

ROOT = Path(__file__).resolve().parents[3]


def twice(token, method, path, **kwargs):
    """Два одинаковых запроса одновременно (барьер), каждый в своём соединении."""
    barrier = threading.Barrier(2)
    results = [None, None]

    def worker(index):
        barrier.wait()
        results[index] = raw(token, method, path, **kwargs)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def one_wins(results, loser_codes):
    """Ровно один успех; второй — ApiError с одним из ожидаемых кодов."""
    statuses = sorted(r.status_code for r in results)
    assert statuses[0] == 200 and statuses[1] != 200, (
        f"Ждали один успех, пришло {statuses}: "
        + " | ".join(r.text[:120] for r in results)
    )
    loser = next(r for r in results if r.status_code != 200)
    body = assert_api_error(loser, loser.status_code)
    assert (loser.status_code, body["error"]["code"]) in loser_codes, loser.text[:200]
    return next(r for r in results if r.status_code == 200).json()


def transitions(bank, app_id, from_state, to_state):
    events = bank.bank_application(app_id)["events"]
    return [
        e
        for e in events
        if e["event_type"] == "STATE_CHANGED"
        and e["from_state"] == from_state
        and e["to_state"] == to_state
    ]


CONFLICT = {(409, "INVALID_TRANSITION"), (409, "CONFLICT_VERSION")}
OTP_REUSED = CONFLICT | {(422, "OTP_INVALID")}


def draft(client, persona):
    token = client.login(persona["users"][0]["login"])
    company_id = client.me()["companies"][0]["company"]["id"]
    app_id = client.create_application(create_body(persona, company_id))["id"]
    return token, app_id


def test_double_submit(client, bank, persona_data):
    persona = find_persona(persona_data, "ip_good")
    token, app_id = draft(client, persona)
    otp = client.otp(app_id, "CONSENTS")
    body = submit_body(persona, otp["otp_id"], otp["demo_code"])
    one_wins(
        twice(token, "POST", f"applications/{app_id}/submit", json=body), OTP_REUSED
    )
    assert len(transitions(bank, app_id, "DRAFT", "SUBMITTED")) == 1


def test_double_withdraw(client, bank, persona_data):
    persona = find_persona(persona_data, "ip_good")
    token, app_id = draft(client, persona)
    won = one_wins(twice(token, "POST", f"applications/{app_id}/withdraw"), CONFLICT)
    assert won["state"] == "WITHDRAWN"
    assert client.get_application(app_id)["state"] == "WITHDRAWN"
    assert len(transitions(bank, app_id, "DRAFT", "WITHDRAWN")) == 1


def test_double_accept_then_double_sign(client, bank, persona_data):
    persona = find_persona(persona_data, "ip_good")
    application, _ = start_application(client, persona)
    app_id = application["id"]
    assert application["state"] == "OFFER_ISSUED"
    token = client.http.headers["Authorization"].removeprefix("Bearer ")

    body = {"offer_version": application["offer"]["version"]}
    won = one_wins(
        twice(token, "POST", f"applications/{app_id}/offer/accept", json=body),
        CONFLICT,
    )
    assert won["state"] == "SIGNING"
    assert len(transitions(bank, app_id, "OFFER_ISSUED", "SIGNING")) == 1

    party = next(p for p in won["parties"] if p["is_me"])
    otp = client.otp(app_id, "OFFER", party_id=party["id"])
    body = {"otp_id": otp["otp_id"], "code": otp["demo_code"], "party_id": party["id"]}
    one_wins(twice(token, "POST", f"applications/{app_id}/sign", json=body), OTP_REUSED)
    assert len(transitions(bank, app_id, "SIGNING", "SIGNED")) == 1
    assert client.get_application(app_id)["state"] in {"SIGNED", "DISBURSED"}


def test_double_underwriter_decision(client, bank, persona_data):
    persona = find_persona(persona_data, "ooo_border")
    application, _ = start_application(client, persona)
    app_id = application["id"]
    assert application["state"] == "MANUAL_REVIEW"
    token = bank.http.headers["Authorization"].removeprefix("Bearer ")
    body = approve_body(persona["demo"]["expected"]["recommendation"])
    won = one_wins(
        twice(token, "POST", f"underwriting/{app_id}/decision", json=body), CONFLICT
    )
    assert won["state"] == "OFFER_ISSUED"
    assert len(transitions(bank, app_id, "MANUAL_REVIEW", "OFFER_ISSUED")) == 1
    manual = [
        d for d in bank.bank_application(app_id)["decisions"] if d["kind"] != "AUTO"
    ]
    assert len(manual) == 1, "Решение андеррайтера записано дважды"


def docker_compose_available():
    if shutil.which("docker") is None:
        return False
    probe = subprocess.run(
        ["docker", "compose", "ps", "-q", "worker"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return probe.returncode == 0 and probe.stdout.strip() != ""


def test_worker_restart_keeps_application(client, persona_data):
    if not docker_compose_available():
        # Карточка A-09a п. 4: без docker на машине тест пропускается с причиной.
        pytest.skip("docker compose недоступен: перезапуск worker не проверить")
    persona = find_persona(persona_data, "ip_good")
    client.login(persona["users"][0]["login"])
    company_id = client.me()["companies"][0]["company"]["id"]
    app_id = client.create_application(create_body(persona, company_id))["id"]
    otp = client.otp(app_id, "CONSENTS")
    client.submit(app_id, submit_body(persona, otp["otp_id"], otp["demo_code"]))
    restart = subprocess.run(
        ["docker", "compose", "restart", "worker"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert restart.returncode == 0, restart.stderr[-500:]
    deadline = time.monotonic() + 120
    with ApiClient() as api:
        api.http.headers["Authorization"] = client.http.headers["Authorization"]
        while True:
            state = api.get_application(app_id, timeout=10)["state"]
            if state == "OFFER_ISSUED":
                break
            assert time.monotonic() < deadline, f"За 120 с не дождались: {state}"
            time.sleep(2)
