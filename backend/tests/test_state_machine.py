"""The transition table is independent of the implementation under test."""

import ast
import re
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.errors import ApiErrorException
from app.models import Application, ApplicationEvent, Company, User

ROOT = Path(__file__).resolve().parents[2]
STATES = (
    "DRAFT SUBMITTED VALIDATION INFO_REQUESTED ENRICHMENT ASSESSMENT "
    "MANUAL_REVIEW OFFER_ISSUED SIGNING SIGNED DISBURSED DECLINED WITHDRAWN EXPIRED"
).split()
ACTORS = ["CLIENT", "SYSTEM", "UNDERWRITER", "GUARANTOR"]


def documented_transitions():
    document = (ROOT / "docs/state-machine.md").read_text(encoding="utf-8")
    table = document.split("## Таблица переходов\n", 1)[1].split("\n## ", 1)[0]
    actors = {
        "система": ["SYSTEM"],
        "планировщик": ["SYSTEM"],
        "клиент": ["CLIENT"],
        "подписант": ["CLIENT"],
        "клиент-ИП": ["CLIENT"],
        "андеррайтер": ["UNDERWRITER"],
        "подписант (+ поручитель)": ["CLIENT", "GUARANTOR"],
    }

    def expand(cell):
        values = STATES[:9] if cell == "* до SIGNED" else re.split(r"\s*[/,]\s*", cell)
        assert values and all(value in STATES for value in values), cell
        return values

    triples = set()
    for line in table.splitlines():
        if not line.startswith("|"):
            continue
        source, target, trigger, actor, condition = [
            part.strip() for part in line.split("|")[1:-1]
        ]
        if source in {"Из", "---"}:
            continue
        assert actor in actors, actor
        triples.update(product(expand(source), expand(target), actors[actor]))
    assert triples
    return triples


@pytest.fixture
def process_session(migrated_database):
    engine, _ = migrated_database
    with Session(engine) as session:
        sequence = session.scalar(
            text("SELECT pg_get_serial_sequence('application', 'number')")
        )
        last_value, is_called = session.execute(
            text(f"SELECT last_value, is_called FROM {sequence}")
        ).one()
        yield session
        session.rollback()
        # Identity sequences are nontransactional; restore the isolated fixture.
        session.execute(
            text("SELECT setval(CAST(:sequence AS regclass), :value, :called)"),
            {"sequence": sequence, "value": last_value, "called": is_called},
        )
        session.commit()


@pytest.fixture
def draft(process_session):
    company = process_session.scalar(select(Company))
    user = process_session.scalar(select(User).where(User.login == "ip_good"))
    application = Application(
        company_id=company.id,
        created_by=user.id,
        product_code="EXPRESS",
        amount=1500000,
        term_months=24,
        purpose="WORKING_CAPITAL",
        declared_revenue_year=12000000,
    )
    process_session.add(application)
    process_session.flush()
    return application


def test_transition_constants_match_document():
    from app.applications.state_machine import TRANSITIONS

    assert TRANSITIONS == documented_transitions()


@pytest.mark.parametrize("source,target,actor", list(product(STATES, STATES, ACTORS)))
def test_every_state_pair_and_actor(process_session, draft, source, target, actor):
    from app.applications.state_machine import transition

    draft.state = source
    process_session.flush()
    before = process_session.scalar(select(func.count()).select_from(ApplicationEvent))
    if (source, target, actor) in documented_transitions():
        transition(
            process_session, draft, target, actor_type=actor, actor_id=draft.created_by
        )
        process_session.flush()
        assert draft.state == target
        event = process_session.scalar(
            select(ApplicationEvent).where(ApplicationEvent.application_id == draft.id)
        )
        assert (event.event_type, event.from_state, event.to_state) == (
            "STATE_CHANGED",
            source,
            target,
        )
        assert (event.actor_type, event.actor_id, event.payload, event.reason_code) == (
            actor,
            draft.created_by,
            {},
            None,
        )
        assert (
            process_session.scalar(select(func.count()).select_from(ApplicationEvent))
            == before + 1
        )
    else:
        with pytest.raises(ApiErrorException) as caught:
            transition(process_session, draft, target, actor_type=actor, actor_id=None)
        assert caught.value.status == 409
        assert caught.value.code == "INVALID_TRANSITION"
        assert caught.value.message == "Действие недоступно в текущем состоянии заявки"
        assert draft.state == source
        process_session.flush()
        assert (
            process_session.scalar(select(func.count()).select_from(ApplicationEvent))
            == before
        )


def test_event_preserves_reason_payload_and_caller_transaction(process_session, draft):
    from app.applications.state_machine import transition

    transition(
        process_session,
        draft,
        "WITHDRAWN",
        actor_type="CLIENT",
        actor_id=draft.created_by,
        reason_code="CLIENT_WITHDREW",
        payload={"note": "тест"},
    )
    process_session.flush()
    event = process_session.scalar(
        select(ApplicationEvent).where(ApplicationEvent.application_id == draft.id)
    )
    assert event.reason_code == "CLIENT_WITHDREW"
    assert event.payload == {"note": "тест"}
    process_session.rollback()
    assert process_session.get(Application, draft.id) is None


def test_event_time_is_transition_time(process_session, draft):
    from app.applications.state_machine import transition

    before = datetime.now(UTC)
    transition(
        process_session,
        draft,
        "SUBMITTED",
        actor_type="CLIENT",
        actor_id=draft.created_by,
    )
    process_session.flush()
    event = process_session.scalar(
        select(ApplicationEvent).where(ApplicationEvent.application_id == draft.id)
    )
    assert before <= event.created_at <= datetime.now(UTC)


def test_state_writes_are_centralized_and_no_runtime_document_reads():
    for path in (ROOT / "backend/app").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if path.name != "config.py":
            assert not re.search(r"[\"'](?:docs|contracts)/", source), path
        if path.name == "state_machine.py":
            continue
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                assert not any(
                    isinstance(child, ast.Attribute)
                    and child.attr == "state"
                    and isinstance(child.ctx, ast.Store)
                    for target in targets
                    for child in ast.walk(target)
                ), (path, node.lineno)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "setattr":
                    assert not (
                        len(node.args) > 1
                        and isinstance(node.args[1], ast.Constant)
                        and node.args[1].value == "state"
                    ), (path, node.lineno)
                if isinstance(node.func, ast.Attribute) and node.func.attr in {
                    "values",
                    "update",
                }:
                    assert all(keyword.arg != "state" for keyword in node.keywords), (
                        path,
                        node.lineno,
                    )
