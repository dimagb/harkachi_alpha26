"""Client views are checked against the published texts and action table."""

import re
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select
from test_applications_api import (
    application_client as application_client,
)
from test_applications_api import (
    authenticate,
    create_body,
    created,
)
from test_auth import PERSONAS
from test_state_machine import documented_transitions

from app.models import Application, ApplicationEvent, Party, User

DOCUMENT = (Path(__file__).resolve().parents[2] / "contracts/codes.md").read_text(
    encoding="utf-8"
)


def rows(section):
    text = DOCUMENT.split(section, 1)[1].split("\n## ", 1)[0]
    return [
        [cell.strip() for cell in line.split("|")[1:-1]]
        for line in text.splitlines()
        if line.startswith("|")
    ][2:]


VIEW_ROWS = rows("## Лента и действия по состояниям")
STAGE_ROWS = rows("## Этапы ленты")
ACTION_CODES = set(
    re.findall(
        r"`([A-Z_]+)`", DOCUMENT.split("## Действия клиента", 1)[1].split("\n## ", 1)[0]
    )
)


def move(session, application, target, *, reason_code=None):
    from app.applications.state_machine import transition

    queue = deque([(application.state, [])])
    seen = set()
    while queue:
        state, steps = queue.popleft()
        if state == target:
            for index, (_, destination, actor) in enumerate(steps):
                transition(
                    session,
                    application,
                    destination,
                    actor_type=actor,
                    actor_id=application.created_by if actor != "SYSTEM" else None,
                    reason_code=reason_code if index == len(steps) - 1 else None,
                )
                session.flush()
            return
        if state in seen:
            continue
        seen.add(state)
        for triple in sorted(documented_transitions()):
            if triple[0] == state:
                queue.append((triple[1], [*steps, triple]))
    raise AssertionError(f"Нет пути в {target}")


@pytest.mark.parametrize("row", VIEW_ROWS, ids=lambda row: row[0].strip("`"))
def test_all_states_match_documented_client_view(application_client, row):
    session, client = application_client
    data = created(session, client)
    application = session.get(Application, UUID(data["id"]))
    state, index, happens, todo, status, actions = row
    state = state.strip("`")
    move(session, application, state)
    if state == "SIGNING":
        session.add(
            Party(
                application_id=application.id,
                role="BORROWER_SIGNATORY",
                user_id=application.created_by,
                full_name="Заёмщик",
                status="PENDING",
            )
        )
    session.commit()
    response = client.get(f"/applications/{application.id}")
    assert response.status_code == 200, response.text
    view = response.json()
    if index.isdigit():
        index = int(index)
    else:
        event = session.scalar(
            select(ApplicationEvent)
            .where(
                ApplicationEvent.application_id == application.id,
                ApplicationEvent.to_state == state,
            )
            .order_by(ApplicationEvent.created_at.desc())
        )
        index = next(
            int(stage[0])
            for stage in STAGE_ROWS
            if event.from_state in stage[3].split(", ")
        )
    stage_row = STAGE_ROWS[index - 1]
    assert view["stage"] == {
        "index": index,
        "code": stage_row[1].strip("`"),
        "title": stage_row[2],
        "what_happens": happens,
        "what_to_do": None if todo == "—" else todo,
    }
    expected_actions = [
        code
        for code in re.findall(r"`([A-Z_]+)`", actions)
        if code in ACTION_CODES and code not in {"OBJECT", "REQUEST_SIGNATURE"}
    ]
    assert view["allowed_actions"] == expected_actions
    assert [item["status"] for item in view["timeline"]] == ["done"] * (index - 1) + [
        status.strip("`")
    ] + ["pending"] * (6 - index)
    assert [(item["stage_code"], item["title"]) for item in view["timeline"]] == [
        (stage[1].strip("`"), stage[2]) for stage in STAGE_ROWS
    ]
    assert all(item["at"] is None for item in view["timeline"][index:])


@pytest.mark.parametrize("state", ["DRAFT", "OFFER_ISSUED"])
def test_signatory_and_accountant_actions(application_client, state):
    session, client = application_client
    persona = next(persona for persona in PERSONAS if persona["code"] == "ooo_load")
    authenticate(client, "ooo_load")
    response = client.post("/applications", json=create_body(session, persona))
    assert response.status_code == 200, response.text
    data = response.json()
    application = session.get(Application, UUID(data["id"]))
    move(session, application, state)
    session.commit()
    path = f"/applications/{application.id}"
    signer = client.get(path).json()
    assert signer["allowed_actions"] == (
        ["EDIT_DRAFT", "SUBMIT", "WITHDRAW"]
        if state == "DRAFT"
        else ["ACCEPT_OFFER", "REJECT_OFFER", "WITHDRAW"]
    )
    authenticate(client, "ooo_load_accountant")
    view = client.get(path).json()
    assert view["timeline"][view["stage"]["index"] - 1]["status"] == "current"
    assert view["stage"]["what_to_do"] == "Ждём решения подписанта компании"
    assert view["allowed_actions"] == (
        ["EDIT_DRAFT", "REQUEST_SIGNATURE", "WITHDRAW"] if state == "DRAFT" else []
    )
    if state == "DRAFT":
        application.awaiting_signature = True
        session.commit()
        assert client.get(path).json()["allowed_actions"] == ["EDIT_DRAFT", "WITHDRAW"]


@pytest.mark.parametrize(
    "party_status,own", [("PENDING", True), ("SIGNED", True), ("PENDING", False)]
)
def test_signing_only_for_own_pending_party(application_client, party_status, own):
    session, client = application_client
    data = created(session, client)
    application = session.get(Application, UUID(data["id"]))
    move(session, application, "SIGNING")
    other = session.scalar(select(User).where(User.login == "ooo_load"))
    party = Party(
        application_id=application.id,
        role="GUARANTOR",
        user_id=application.created_by if own else other.id,
        full_name="Участник",
        status=party_status,
    )
    session.add(party)
    session.commit()
    view = client.get(f"/applications/{application.id}").json()
    can_sign = own and party_status == "PENDING"
    assert view["allowed_actions"] == (
        ["SIGN", "WITHDRAW"] if can_sign else ["WITHDRAW"]
    )
    assert view["timeline"][4]["status"] == (
        "action_required" if can_sign else "current"
    )
    assert view["stage"]["what_to_do"] == (
        "Подпишите договор кодом подтверждения"
        if can_sign
        else "Ждём подписи остальных участников"
    )
    assert view["parties"] == [
        {
            "id": str(party.id),
            "role": "GUARANTOR",
            "full_name": "Участник",
            "signed": party_status == "SIGNED",
            "is_me": own,
        }
    ]


def test_rejected_offer_text(application_client):
    session, client = application_client
    data = created(session, client)
    application = session.get(Application, UUID(data["id"]))
    move(session, application, "OFFER_ISSUED")
    move(session, application, "WITHDRAWN", reason_code="CLIENT_REJECTED_OFFER")
    session.commit()
    view = client.get(f"/applications/{application.id}").json()
    assert view["stage"]["what_happens"] == "Вы отказались от предложения"
    assert view["stage"]["index"] == 4


def test_stage_timestamps_use_first_entry_and_cancellation_time(application_client):
    session, client = application_client
    data = created(session, client)
    application = session.get(Application, UUID(data["id"]))
    move(session, application, "INFO_REQUESTED")
    move(session, application, "VALIDATION")
    move(session, application, "ENRICHMENT")
    events = session.scalars(
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id == application.id)
        .order_by(ApplicationEvent.created_at)
    ).all()
    start = datetime(2026, 10, 23, tzinfo=UTC)
    for index, event in enumerate(events):
        event.created_at = start + timedelta(minutes=index)
    session.commit()
    view = client.get(f"/applications/{application.id}").json()
    assert view["timeline"][0]["at"] == start.isoformat()
    assert view["timeline"][1]["at"] == (start + timedelta(minutes=2)).isoformat()
    move(session, application, "WITHDRAWN", reason_code="CLIENT_WITHDREW")
    cancellation = session.scalar(
        select(ApplicationEvent).where(
            ApplicationEvent.application_id == application.id,
            ApplicationEvent.to_state == "WITHDRAWN",
        )
    )
    cancellation.created_at = start + timedelta(hours=1)
    session.commit()
    view = client.get(f"/applications/{application.id}").json()
    assert view["stage"]["index"] == 2
    assert [item["status"] for item in view["timeline"]] == [
        "done",
        "cancelled",
        "pending",
        "pending",
        "pending",
        "pending",
    ]
    assert view["timeline"][0]["at"] == start.isoformat()
    assert view["timeline"][1]["at"] == (start + timedelta(hours=1)).isoformat()
