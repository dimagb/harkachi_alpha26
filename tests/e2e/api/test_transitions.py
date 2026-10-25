"""A-07b: устойчивые переходы через API и события каждой новой заявки."""

import json

import pytest
from client import ApiClient
from conftest import require_ready
from test_personas import find_persona, start_application


@pytest.fixture(scope="module", autouse=True)
def stand_ready():
    # TODO(lead): как в A-03, без стенда модуль пропускается; на стенде пропусков нет.
    with ApiClient() as api:
        require_ready(str(api.http.base_url))


def started(client, persona_data, code, state):
    application, _ = start_application(client, find_persona(persona_data, code))
    assert application["state"] == state
    return application


def assert_event(bank, app_id, source, target, *, reason=None):
    events = [
        event
        for event in bank.bank_application(app_id)["events"]
        if event["event_type"] == "STATE_CHANGED"
        and event["from_state"] == source
        and event["to_state"] == target
    ]
    assert len(events) == 1, f"Ожидалось одно событие {source} → {target}: {events}"
    if reason is not None:
        assert events[0]["reason_code"] == reason


def test_manual_decline_category_without_comment(client, bank, persona_data):
    application = started(client, persona_data, "ooo_border", "MANUAL_REVIEW")
    app_id = application["id"]
    comment = "Внутренний комментарий проверки A-07b"
    decision = bank.decide(
        app_id,
        {
            "outcome": "DECLINE",
            "client_reason_category": "Финансовое положение",
            "comment": comment,
        },
    )
    assert decision["state"] == "DECLINED"
    public = client.get_application(app_id)
    assert public["state"] == "DECLINED"
    assert public["client_reason"]["code"] == "UNDERWRITER_DECLINE"
    assert public["client_reason"]["category"] == "Финансовое положение"
    assert comment not in json.dumps(public, ensure_ascii=False)
    assert_event(bank, app_id, "MANUAL_REVIEW", "DECLINED")


def test_manual_info_response_route(client, bank, persona_data):
    application = started(client, persona_data, "ooo_border", "MANUAL_REVIEW")
    app_id = application["id"]
    requested = bank.decide(
        app_id,
        {
            "outcome": "REQUEST_INFO",
            "info_questions": ["Уточните обязательства компании"],
            "comment": "Нужно уточнить обязательства для решения по заявке",
        },
    )
    assert requested["state"] == "INFO_REQUESTED"
    public = client.get_application(app_id)
    assert public["state"] == "INFO_REQUESTED"
    assert public["info_request"]["items"][0]["question"] == (
        "Уточните обязательства компании"
    )
    response = client.info_response(
        app_id,
        {
            "answers": [
                {
                    "item_code": "UNDERWRITER_QUESTION",
                    "comment": "Все обязательства указаны, дополнительных нет",
                }
            ]
        },
    )
    assert response["state"] == "MANUAL_REVIEW"
    queue = bank.request("queue-after-info", "GET", "underwriting/queue")
    assert next(row for row in queue if row["id"] == app_id)["route_reason"] == (
        "INFO_RESPONSE"
    )
    assert_event(bank, app_id, "MANUAL_REVIEW", "INFO_REQUESTED")
    assert_event(bank, app_id, "INFO_REQUESTED", "MANUAL_REVIEW")


@pytest.mark.parametrize(
    "code,state,days,reason",
    [
        ("ooo_gap", "INFO_REQUESTED", 6, "EXPIRED_INFO"),
        ("ip_good", "OFFER_ISSUED", 31, "EXPIRED_OFFER"),
        ("ip_good", "SIGNING", 31, "EXPIRED_OFFER"),
    ],
)
def test_expiry(client, bank, persona_data, code, state, days, reason):
    initial = "OFFER_ISSUED" if state == "SIGNING" else state
    application = started(client, persona_data, code, initial)
    app_id = application["id"]
    if state == "SIGNING":
        accepted = client.accept_offer(app_id, application["offer"]["version"])
        assert accepted["state"] == "SIGNING"
        assert not any(party["signed"] for party in accepted["parties"])
    shifted = bank.time_shift(app_id, days)
    assert shifted == {
        "application_id": app_id,
        "expired_now": True,
        "state": "EXPIRED",
    }
    public = client.get_application(app_id)
    assert public["state"] == "EXPIRED"
    assert public["client_reason"]["code"] == reason
    assert_event(bank, app_id, state, "EXPIRED", reason=reason)


@pytest.mark.parametrize(
    "code,state",
    [
        ("ooo_gap", "INFO_REQUESTED"),
        ("ooo_border", "MANUAL_REVIEW"),
        ("ip_good", "OFFER_ISSUED"),
        ("ooo_load", "SIGNING"),
    ],
)
def test_withdraw(client, bank, persona_data, code, state):
    initial = "OFFER_ISSUED" if state == "SIGNING" else state
    application = started(client, persona_data, code, initial)
    app_id = application["id"]
    if state == "SIGNING":
        accepted = client.accept_offer(app_id, application["offer"]["version"])
        assert accepted["state"] == "SIGNING"
        assert not any(party["signed"] for party in accepted["parties"])
    withdrawn = client.withdraw(app_id)
    assert withdrawn["state"] == "WITHDRAWN"
    assert withdrawn["client_reason"]["code"] == "CLIENT_WITHDREW"
    assert client.get_application(app_id)["state"] == "WITHDRAWN"
    assert_event(bank, app_id, state, "WITHDRAWN")


def test_decline_offer(client, bank, persona_data):
    application = started(client, persona_data, "ip_good", "OFFER_ISSUED")
    app_id = application["id"]
    declined = client.decline_offer(app_id, application["offer"]["version"])
    assert declined["state"] == "WITHDRAWN"
    assert declined["offer"]["status"] == "REJECTED"
    assert client.get_application(app_id)["state"] == "WITHDRAWN"
    assert_event(bank, app_id, "OFFER_ISSUED", "WITHDRAWN")
