"""Сценарии S-01…S-06, S-08, S-09, S-17, S-18 на настоящем HTTP."""

import pytest
from client import wait_state
from flows import (
    approve_body,
    create_body,
    expected_bank,
    expected_client,
    info_response_body,
    submit_body,
)

PERSONA_CODES = ("ip_good", "ooo_load", "ooo_gap", "ip_bad", "ooo_border", "ooo_aml")


def find_persona(persona_data, code):
    return next(p for p in persona_data["personas"] if p["code"] == code)


def assert_client(application, expected):
    assert application["state"] == expected["state"]
    for key in ("offer", "client_reason"):
        if expected[key] is None:
            assert application[key] is None
        else:
            assert application[key] is not None
            assert {k: application[key][k] for k in expected[key]} == expected[key]


def assert_bank(application, expected):
    # Контракт: decisions упорядочены от новых к старым.
    auto = next(d for d in application["decisions"] if d["kind"] == "AUTO")
    for key in expected.keys() - {"points"}:
        assert auto[key] == expected[key], f"Банк: неверное поле {key}"
    assert len(auto["factors"]) == len(expected["points"])
    assert {f["code"]: f["points"] for f in auto["factors"]} == expected["points"]
    return auto


def assert_list(client, company_id, app_id, state):
    applications = client.list_applications(company_id)
    application = next(a for a in applications if a["id"] == app_id)
    assert application["state"] == state


def start_application(client, persona):
    signatory = next(u for u in persona["users"] if u["can_sign"])
    client.login(signatory["login"])
    me = client.me()
    membership = next(
        m for m in me["companies"] if m["company"]["inn"] == persona["inn"]
    )
    assert membership["can_sign"] is True
    company_id = membership["company"]["id"]
    application = client.create_application(create_body(persona, company_id))
    assert application["state"] == "DRAFT"
    app_id = application["id"]
    otp = client.otp(app_id, "CONSENTS")
    client.submit(app_id, submit_body(persona, otp["otp_id"], otp["demo_code"]))
    application = wait_state(client, app_id)
    assert_list(client, company_id, app_id, application["state"])
    return application, company_id


@pytest.mark.parametrize("code", PERSONA_CODES)
def test_persona(code, client, bank, persona_data):
    persona = find_persona(persona_data, code)
    golden = persona["demo"]["expected"]
    application, company_id = start_application(client, persona)
    app_id = application["id"]
    if code == "ooo_gap":
        assert application["state"] == golden["first_state"] == "INFO_REQUESTED"
        assert "REVENUE_CONFIRM" in {
            item["item_code"] for item in application["info_request"]["items"]
        }
        client.info_response(app_id, info_response_body(persona))
        application = wait_state(client, app_id)
    assert_client(application, expected_client(persona))
    auto = assert_bank(bank.bank_application(app_id), expected_bank(persona))
    if code == "ooo_aml":
        assert {"code": "SF_ADDITIONAL", "effect": "STOP"} in [
            {"code": rule["code"], "effect": rule["effect"]}
            for rule in auto["rules_fired"]
        ]
    if code == "ooo_border":
        recommendation = golden["recommendation"]
        assert auto["outcome"] == "MANUAL"
        assert auto["recommendation"] == {
            "outcome": recommendation["outcome"],
            **{
                k: recommendation["offer"][k] for k in ("amount", "term_months", "rate")
            },
        }
        bank.decide(app_id, approve_body(recommendation))
        application = wait_state(client, app_id, leave={"MANUAL_REVIEW"})
        assert_client(
            application,
            {
                "state": "OFFER_ISSUED",
                "offer": recommendation["offer"],
                "client_reason": None,
            },
        )
    assert_list(client, company_id, app_id, application["state"])


def full_path(client, bank, persona, expected_roles):
    application, company_id = start_application(client, persona)
    app_id = application["id"]
    assert_client(application, expected_client(persona))
    auto = assert_bank(bank.bank_application(app_id), expected_bank(persona))
    expected_kind = {"APPROVE": "APPROVED", "COUNTER": "COUNTER"}[auto["outcome"]]
    assert application["offer"]["kind"] == expected_kind
    application = client.accept_offer(app_id, application["offer"]["version"])
    assert application["state"] == "SIGNING"
    parties = [p for p in application["parties"] if p["is_me"] and not p["signed"]]
    assert sorted(p["role"] for p in parties) == sorted(expected_roles)
    for index, party in enumerate(parties):
        purpose = {"BORROWER_SIGNATORY": "OFFER", "GUARANTOR": "GUARANTEE"}[
            party["role"]
        ]
        otp = client.otp(app_id, purpose, party_id=party["id"])
        application = client.sign(
            app_id,
            {
                "otp_id": otp["otp_id"],
                "code": otp["demo_code"],
                "party_id": party["id"],
            },
        )
        assert next(p for p in application["parties"] if p["id"] == party["id"])[
            "signed"
        ]
        if index < len(parties) - 1:
            assert application["state"] == "SIGNING"
    application = wait_state(client, app_id, leave={"SIGNING", "SIGNED"})
    assert application["state"] == "DISBURSED"
    assert all(p["signed"] for p in application["parties"] if p["is_me"])
    assert_list(client, company_id, app_id, "DISBURSED")


def test_full_path_ip_good(client, bank, persona_data):
    full_path(
        client, bank, find_persona(persona_data, "ip_good"), ["BORROWER_SIGNATORY"]
    )


def test_counter_signed_ooo_load(client, bank, persona_data):
    full_path(
        client,
        bank,
        find_persona(persona_data, "ooo_load"),
        ["BORROWER_SIGNATORY", "GUARANTOR"],
    )
