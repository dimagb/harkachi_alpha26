import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pipeline.test_pipeline import drain, providers_for
from sqlalchemy import event, func, select

from app.auth.deps import current_user
from app.integrations.registry import FakeRegistryProvider
from app.main import app
from app.models import (
    Application,
    ApplicationEvent,
    Decision,
    ExternalCheck,
    InfoRequest,
    Objection,
    User,
)


def decide(client, application_id, **body):
    return client.post(
        f"/api/v1/underwriting/{application_id}/decision",
        json={
            "outcome": "APPROVE",
            "amount": 1_000_000,
            "term_months": 24,
            "comment": "Проверены данные компании",
            **body,
        },
    )


def client_get(client, factory, application_id):
    with factory() as session:
        application = session.get(Application, application_id)
        user = session.get(User, application.created_by)
    previous = app.dependency_overrides[current_user]
    app.dependency_overrides[current_user] = lambda: user
    try:
        response = client.get(f"/api/v1/applications/{application_id}")
        assert response.status_code == 200, response.text
        return response
    finally:
        app.dependency_overrides[current_user] = previous


@pytest.mark.parametrize(
    "role,status", [("CLIENT", 403), ("GUARANTOR", 403), (None, 401)]
)
def test_access_all_three_endpoints(bank_context, role, status):
    client, _ = bank_context
    if role is None:
        app.dependency_overrides.pop(current_user)
    else:
        app.dependency_overrides[current_user] = lambda: User(
            id=uuid4(), login="other", role=role, full_name="Другой", password_hash=""
        )
    for method, path in [
        ("GET", "/underwriting/queue"),
        ("GET", f"/underwriting/applications/{uuid4()}"),
        ("POST", f"/underwriting/{uuid4()}/decision"),
    ]:
        response = client.request(
            method,
            "/api/v1" + path,
            json={"outcome": "DECLINE", "comment": "Проверено"},
        )
        assert response.status_code == status, response.text
        assert response.json()["error"]["code"] == (
            "UNAUTHORIZED" if status == 401 else "FORBIDDEN"
        )


def test_missing_application(bank_context):
    client, _ = bank_context
    assert client.get(f"/api/v1/underwriting/applications/{uuid4()}").status_code == 404
    assert decide(client, uuid4()).status_code == 404


@pytest.mark.parametrize(
    "code", ["ip_good", "ip_bad", "ooo_border", "ooo_aml", "ooo_load", "ooo_gap"]
)
def test_bank_card_all_states(
    bank_context, pipeline_factory, persona_data, run_persona, code
):
    application_id = run_persona(code)
    client, _ = bank_context
    response = client.get(f"/api/v1/underwriting/applications/{application_id}")
    assert response.status_code == 200, response.text
    card = response.json()
    assert card["allowed_actions"] == []
    assert all(not p["is_me"] for p in card["parties"])
    assert all(not re.fullmatch(r"[A-Z_]+", e["note"] or "") for e in card["events"])
    titles = [f["title"] for d in card["decisions"] for f in d["factors"]]
    assert all("`" not in t and "_" not in t for t in titles), titles
    if code != "ooo_gap":
        assert {c["source"] for c in card["external_checks"]} == {"EGRUL", "BKI", "FNS"}
    if code == "ooo_border":
        expected = next(p for p in persona_data["personas"] if p["code"] == code)[
            "demo"
        ]["expected"]["recommendation"]
        decision = card["decisions"][0]
        assert decision["kind"] == "AUTO" and decision["score"] == 54
        assert {f["code"]: f["points"] for f in decision["factors"]} == expected[
            "points"
        ]
        assert decision["recommendation"] == {
            "outcome": expected["outcome"],
            **{k: expected["offer"][k] for k in ("amount", "term_months", "rate")},
        }
        assert len(decision["factors"]) == 12
        assert decision["key_rate"] == 14 and decision["config_version"] == "1"
        assert len(card["turnover_12m"]) == 12
        assert [m["month"] for m in card["turnover_12m"]] == sorted(
            m["month"] for m in card["turnover_12m"]
        )
        persona = next(p for p in persona_data["personas"] if p["code"] == code)
        assert card["company"]["founders"] == persona["founders"]
        assert all(c["response"] for c in card["external_checks"])
        assert "Пограничная оценка" in [e["note"] for e in card["events"]]
    if code == "ooo_aml":
        assert card["risk_flags"]["aml_flag"]
        assert any(
            r["code"] == "SF_ADDITIONAL" and r["effect"] == "STOP"
            for r in card["decisions"][0]["rules_fired"]
        )
        assert (
            "SF_ADDITIONAL"
            not in client_get(client, pipeline_factory, application_id).text
        )


@pytest.mark.parametrize("route", [{"code": "GRADE_C"}, "FOO", None, 123, []])
def test_bank_card_ignores_invalid_event_route(
    bank_context, pipeline_factory, run_persona, route
):
    client, _ = bank_context
    identity = run_persona()
    with pipeline_factory.begin() as session:
        entry = session.scalar(
            select(ApplicationEvent).where(
                ApplicationEvent.application_id == identity,
                ApplicationEvent.to_state == "MANUAL_REVIEW",
            )
        )
        entry.payload = {"route_reason": route}
    response = client.get(f"/api/v1/underwriting/applications/{identity}")
    assert response.status_code == 200, response.text
    events = [
        entry
        for entry in response.json()["events"]
        if entry["to_state"] == "MANUAL_REVIEW"
    ]
    assert len(events) == 1
    assert events[0]["note"] is None


def test_bank_card_objection_note_and_client_projection(
    bank_context, pipeline_factory, run_persona
):
    application_id = run_persona("ip_bad")
    client, _ = bank_context
    before = client.get(f"/api/v1/underwriting/applications/{application_id}").json()[
        "events"
    ]
    with pipeline_factory() as session:
        application = session.get(Application, application_id)
        user = session.get(User, application.created_by)
    original = app.dependency_overrides[current_user]
    app.dependency_overrides[current_user] = lambda: user
    text = "Просрочка погашена 20.10, справка есть"
    try:
        response = client.post(
            f"/api/v1/applications/{application_id}/objection", json={"text": text}
        )
        assert response.status_code == 200, response.text
        assert text not in response.text
        public = client.get(f"/api/v1/applications/{application_id}")
        assert public.status_code == 200, public.text
        assert text not in public.text
    finally:
        app.dependency_overrides[current_user] = original

    response = client.get(f"/api/v1/underwriting/applications/{application_id}")
    assert response.status_code == 200, response.text
    events = response.json()["events"]
    review = [entry for entry in events if entry["to_state"] == "MANUAL_REVIEW"]
    assert len(review) == 1
    assert review[0]["note"] == (
        "Клиент не согласен с решением: «Просрочка погашена 20.10, справка есть»"
    )
    assert "OBJECTION" not in review[0]["note"]
    assert events[: len(before)] == before


@pytest.mark.parametrize(
    "recommendation, expected",
    [
        ({"outcome": "APPROVE", "amount": 800_000, "term_months": 24}, "800 000"),
        ({"outcome": "APPROVE", "amount": 1_000_000, "term_months": 12}, "12 мес."),
        (
            {"outcome": "COUNTER", "amount": 1_000_000, "term_months": 24},
            "Встречное предложение",
        ),
    ],
)
def test_approval_note_marks_different_recommendation(
    bank_context, pipeline_factory, run_persona, recommendation, expected
):
    identity = run_persona("ooo_border")
    client, _ = bank_context
    with pipeline_factory.begin() as session:
        auto = session.scalar(
            select(Decision).where(
                Decision.application_id == identity, Decision.kind == "AUTO"
            )
        )
        auto.recommendation = {**recommendation, "rate": 26}
    response = decide(client, identity)
    assert response.status_code == 200, response.text
    notes = [
        e["note"]
        for e in response.json()["events"]
        if e["event_type"] == "DECISION_MADE" and e["actor"].startswith("Андеррайтер")
    ]
    assert len(notes) == 1
    assert notes[0].startswith("Проверены данные компании")
    assert "Решение отличается от рекомендации системы" in notes[0]
    assert expected in notes[0]
    public = client_get(client, pipeline_factory, identity)
    assert "Решение отличается" not in public.text


def test_matching_recommendation_keeps_only_specialist_comment(
    bank_context, run_persona
):
    identity = run_persona("ooo_border")
    client, _ = bank_context
    response = decide(client, identity)
    assert response.status_code == 200, response.text
    notes = [
        e["note"]
        for e in response.json()["events"]
        if e["event_type"] == "DECISION_MADE" and e["actor"].startswith("Андеррайтер")
    ]
    assert notes == ["Проверены данные компании"]


@pytest.mark.parametrize("count", [1, 10])
def test_manual_notes_use_historical_recommendation_with_constant_queries(
    pipeline_factory, run_persona, count
):
    from app.underwriting.card import _events

    identity = run_persona("ooo_border")
    now = datetime.now(UTC)
    with pipeline_factory.begin() as session:
        auto = session.scalar(
            select(Decision).where(Decision.application_id == identity)
        )
        auto.recommendation = {
            "outcome": "APPROVE",
            "amount": 800_000,
            "term_months": 24,
            "rate": 26,
        }
        for index in range(count):
            at = now + timedelta(minutes=index)
            session.add(
                Decision(
                    application_id=identity,
                    kind="MANUAL",
                    outcome="APPROVE",
                    factors=[],
                    rules_fired=[],
                    internal_reasons=[],
                    config_version=auto.config_version,
                    inputs_snapshot={
                        "amount": 1_000_000 if index % 2 == 0 else 800_000,
                        "term_months": 24,
                    },
                    comment=f"Решение {index}",
                    created_at=at,
                )
            )
            session.add(
                ApplicationEvent(
                    application_id=identity,
                    event_type="DECISION_MADE",
                    actor_type="UNDERWRITER",
                    payload={"comment": f"Решение {index}"},
                    created_at=at + timedelta(seconds=1),
                )
            )
        session.add(
            Decision(
                application_id=identity,
                kind="AUTO",
                outcome="APPROVE",
                factors=[],
                rules_fired=[],
                internal_reasons=[],
                config_version=auto.config_version,
                inputs_snapshot={},
                recommendation={
                    "outcome": "APPROVE",
                    "amount": 1_000_000,
                    "term_months": 24,
                    "rate": 26,
                },
                created_at=now + timedelta(days=1),
            )
        )
    statements = []
    engine = pipeline_factory.kw["bind"]

    def record(*args):
        statements.append(args[2])

    with pipeline_factory() as session:
        application = session.get(Application, identity)
        event.listen(engine, "before_cursor_execute", record)
        try:
            entries = _events(session, application)
        finally:
            event.remove(engine, "before_cursor_execute", record)
    notes = [
        e.note
        for e in entries
        if e.event_type == "DECISION_MADE" and e.actor.startswith("Андеррайтер")
    ]
    assert len(notes) == count
    for index, note in enumerate(notes):
        if index % 2 == 0:
            assert note.startswith(f"Решение {index}; Решение отличается")
            assert "800 000" in note
        else:
            assert note == f"Решение {index}"
    assert len(statements) <= 3


def test_approval_after_objection_marks_stop_factor(
    bank_context, pipeline_factory, run_persona
):
    identity = run_persona("ip_bad", app_params={"amount": 1_000_000, "term": 24})
    client, _ = bank_context
    with pipeline_factory() as session:
        user = session.get(User, session.get(Application, identity).created_by)
    previous = app.dependency_overrides[current_user]
    app.dependency_overrides[current_user] = lambda: user
    try:
        response = client.post(
            f"/api/v1/applications/{identity}/objection",
            json={"text": "Просрочка уже погашена, прошу пересмотреть"},
        )
        assert response.status_code == 200, response.text
    finally:
        app.dependency_overrides[current_user] = previous
    response = decide(client, identity)
    assert response.status_code == 200, response.text
    notes = [
        e["note"]
        for e in response.json()["events"]
        if e["event_type"] == "DECISION_MADE" and e["actor"].startswith("Андеррайтер")
    ]
    assert len(notes) == 1
    assert notes[0].startswith("Проверены данные компании")
    assert "Решение вопреки стоп-фактору:" in notes[0]
    assert "просроч" in notes[0].lower()
    assert "SF_" not in notes[0] and "APPROVE" not in notes[0]
    public = client_get(client, pipeline_factory, identity)
    assert "стоп-фактор" not in public.text


def test_gap_response_note_contains_question_value_and_comment(
    bank_context, pipeline_factory, run_persona
):
    identity = run_persona("ooo_gap")
    client, _ = bank_context
    public = client_get(client, pipeline_factory, identity).json()
    question = public["info_request"]["items"][0]["question"]
    with pipeline_factory() as session:
        user = session.get(User, session.get(Application, identity).created_by)
    previous = app.dependency_overrides[current_user]
    app.dependency_overrides[current_user] = lambda: user
    try:
        response = client.post(
            f"/api/v1/applications/{identity}/info-response",
            json={
                "answers": [
                    {
                        "item_code": "REVENUE_CONFIRM",
                        "value": 7_200_000,
                        "comment": "Подтверждаю выручку по отчётности",
                    }
                ]
            },
        )
        assert response.status_code == 200, response.text
        before = client.get(f"/api/v1/applications/{identity}").json()
    finally:
        app.dependency_overrides[current_user] = previous
    response = client.get(f"/api/v1/underwriting/applications/{identity}")
    assert response.status_code == 200, response.text
    entries = [
        e for e in response.json()["events"] if e["from_state"] == "INFO_REQUESTED"
    ]
    assert len(entries) == 1
    note = entries[0]["note"]
    assert note.startswith("Клиент ответил:")
    assert question in note and "7 200 000" in note
    assert "комментарий: «Подтверждаю выручку по отчётности»" in note
    assert "REVENUE_CONFIRM" not in note
    assert client_get(client, pipeline_factory, identity).json() == before


@pytest.mark.parametrize("count", [1, 10])
def test_response_notes_keep_each_round_and_constant_queries(
    pipeline_factory, run_persona, count
):
    from app.underwriting.card import _events

    identity = run_persona("ooo_gap")
    other = run_persona("ooo_gap")
    now = datetime.now(UTC)
    with pipeline_factory.begin() as session:
        for index in range(count):
            at = now + timedelta(minutes=index)
            session.add(
                InfoRequest(
                    application_id=identity,
                    source="UNDERWRITER",
                    items=[
                        {
                            "item_code": "UNDERWRITER_QUESTION",
                            "question": f"Вопрос {index}",
                            "requires_value": False,
                        }
                    ],
                    response=[
                        {
                            "item_code": "UNDERWRITER_QUESTION",
                            "comment": f"Ответ {index}",
                        }
                    ],
                    due_at=at + timedelta(days=1),
                    responded_at=at,
                )
            )
            session.add(
                ApplicationEvent(
                    application_id=identity,
                    event_type="STATE_CHANGED",
                    actor_type="CLIENT",
                    from_state="INFO_REQUESTED",
                    to_state="MANUAL_REVIEW",
                    payload={"route_reason": "INFO_RESPONSE"},
                    created_at=at + timedelta(seconds=1),
                )
            )
        session.add(
            InfoRequest(
                application_id=other,
                source="UNDERWRITER",
                items=[],
                response=[],
                due_at=now + timedelta(days=1),
                responded_at=now + timedelta(days=1),
            )
        )
        session.add(
            ApplicationEvent(
                application_id=identity,
                event_type="STATE_CHANGED",
                actor_type="CLIENT",
                from_state="INFO_REQUESTED",
                to_state="WITHDRAWN",
                reason_code="CLIENT_WITHDREW",
                payload={},
                created_at=now + timedelta(days=1),
            )
        )
    statements = []
    engine = pipeline_factory.kw["bind"]

    def record(*args):
        statements.append(args[2])

    with pipeline_factory() as session:
        application = session.get(Application, identity)
        event.listen(engine, "before_cursor_execute", record)
        try:
            entries = _events(session, application)
        finally:
            event.remove(engine, "before_cursor_execute", record)
    withdrawn = [e for e in entries if e.to_state == "WITHDRAWN"]
    assert len(withdrawn) == 1
    assert withdrawn[0].note is None
    notes = [
        e.note
        for e in entries
        if e.from_state == "INFO_REQUESTED" and e.to_state == "MANUAL_REVIEW"
    ]
    assert len(notes) == count
    for index, note in enumerate(notes):
        assert f"Вопрос {index}" in note and f"«Ответ {index}»" in note
        assert "UNDERWRITER_QUESTION" not in note
    assert len(statements) <= 3


@pytest.mark.parametrize("count", [1, 10])
def test_objection_event_note_uses_latest_text_in_one_query(
    pipeline_factory, run_persona, count
):
    from app.underwriting.card import _events

    identity = run_persona("ip_bad")
    other = run_persona("ip_bad")
    now = datetime.now(UTC)
    with pipeline_factory.begin() as session:
        session.add_all(
            [
                Objection(
                    application_id=identity,
                    text="Старое возражение",
                    created_at=now - timedelta(days=1),
                ),
                Objection(
                    application_id=identity,
                    text="Актуальное возражение",
                    created_at=now,
                ),
                Objection(
                    application_id=other,
                    text="Чужое возражение",
                    created_at=now + timedelta(days=1),
                ),
            ]
        )
        for _ in range(count):
            session.add(
                ApplicationEvent(
                    application_id=identity,
                    from_state="DECLINED",
                    to_state="MANUAL_REVIEW",
                    event_type="STATE_CHANGED",
                    actor_type="CLIENT",
                    payload={"route_reason": "OBJECTION"},
                )
            )
        session.add(
            ApplicationEvent(
                application_id=identity,
                from_state="MANUAL_REVIEW",
                to_state="DECLINED",
                event_type="STATE_CHANGED",
                actor_type="SYSTEM",
                payload={"route_reason": "OBJECTION"},
            )
        )

    statements = []
    engine = pipeline_factory.kw["bind"]

    def record(*args):
        statements.append(args[2])

    with pipeline_factory() as session:
        application = session.get(Application, identity)
        event.listen(engine, "before_cursor_execute", record)
        try:
            entries = _events(session, application)
        finally:
            event.remove(engine, "before_cursor_execute", record)
    review = [entry for entry in entries if entry.to_state == "MANUAL_REVIEW"]
    assert len(review) == count
    assert all(
        entry.note == "Клиент не согласен с решением: «Актуальное возражение»"
        for entry in review
    )
    declined = [
        entry
        for entry in entries
        if entry.from_state == "MANUAL_REVIEW" and entry.to_state == "DECLINED"
    ]
    assert len(declined) == 1
    assert declined[0].note == "Клиент не согласен с решением"
    assert len(statements) == 1


def test_queue_current_event_order_and_constant_queries(
    bank_context, pipeline_factory, run_persona
):
    first = run_persona()
    second = run_persona("ip_good", registry=FakeRegistryProvider({}))
    client, _ = bank_context
    response = client.get("/api/v1/underwriting/queue")
    assert response.status_code == 200, response.text
    rows = response.json()
    assert [r["id"] for r in rows] == [str(first), str(second)]
    assert rows[0]["grade"] == "C" and rows[0]["route_reason"] == "GRADE_C"
    assert rows[1]["grade"] is None and rows[1]["route_reason"] == "SOURCE_UNAVAILABLE"
    assert [r["waiting_since"] for r in rows] == sorted(
        r["waiting_since"] for r in rows
    )
    # A later manual decision must not hide the AUTO grade/fallback route.
    with pipeline_factory.begin() as session:
        entry = session.scalar(
            select(ApplicationEvent).where(
                ApplicationEvent.application_id == first,
                ApplicationEvent.to_state == "MANUAL_REVIEW",
            )
        )
        entry.payload = {}
    from app.underwriting.queue import get_queue

    with pipeline_factory() as session:
        assert get_queue(session)[0].route_reason == "GRADE_C"


@pytest.mark.parametrize("route", ["FOO", "", None, 123, {"code": "GRADE_C"}])
def test_current_route_ignores_invalid_entry(pipeline_factory, run_persona, route):
    from app.underwriting.queue import current_route

    identity = run_persona()
    with pipeline_factory.begin() as session:
        entry = session.scalar(
            select(ApplicationEvent).where(
                ApplicationEvent.application_id == identity,
                ApplicationEvent.to_state == "MANUAL_REVIEW",
            )
        )
        entry.payload = {"route_reason": route}
        auto = session.scalar(
            select(Decision).where(
                Decision.application_id == identity, Decision.kind == "AUTO"
            )
        )
        assert current_route(session, session.get(Application, identity), auto) == (
            "GRADE_C"
        )


@pytest.mark.parametrize("count", [1, 10])
def test_queue_constant_queries(bank_context, pipeline_factory, run_persona, count):
    for _ in range(count):
        run_persona()
    from app.underwriting.queue import get_queue

    statements = []
    engine = pipeline_factory.kw["bind"]

    def record(*args):
        statements.append(args[2])

    event.listen(engine, "before_cursor_execute", record)
    try:
        with pipeline_factory() as session:
            result = get_queue(session)
            assert len(result) == count
            assert all(row.route_reason == "GRADE_C" for row in result)
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert len(statements) <= 3


def test_approve_recommendation_client_projection_and_duplicate(
    bank_context, pipeline_factory, run_persona
):
    application_id = run_persona()
    client, user_id = bank_context
    response = decide(client, application_id)
    assert response.status_code == 200, response.text
    card = response.json()
    assert card["state"] == "OFFER_ISSUED" and card["version"] > 1
    assert card["decisions"][0]["kind"] == "MANUAL"
    assert card["decisions"][0]["made_by"] == "Специалист Банка"
    assert card["decisions"][0]["grade"] == "C" and card["decisions"][0]["score"] == 54
    assert not any(e["event_type"] == "UNDERWRITER_OVERRIDE" for e in card["events"])
    manual_events = [
        e
        for e in card["events"]
        if e["event_type"] in {"DECISION_MADE", "OFFER_ISSUED"}
        and e["actor"].startswith("Андеррайтер")
    ]
    assert len(manual_events) == 2 and all(
        e["actor"] == "Андеррайтер: Специалист Банка" for e in manual_events
    )
    public = client_get(client, pipeline_factory, application_id).json()
    assert {
        k: public["offer"][k]
        for k in ("amount", "term_months", "rate", "monthly_payment")
    } == {"amount": 1_000_000, "term_months": 24, "rate": 26, "monthly_payment": 53875}
    assert public["offer"]["explanation"] == [
        "Руководитель и адрес компании не массовые",
        "Поступления на счёт каждый месяц",
        "Нет просрочек по кредитам",
    ]
    assert decide(client, application_id).status_code == 409
    with pipeline_factory() as session:
        decisions = list(
            session.scalars(
                select(Decision).where(
                    Decision.application_id == application_id, Decision.kind == "MANUAL"
                )
            )
        )
        assert len(decisions) == 1 and decisions[0].made_by == user_id
        assert decisions[0].inputs_snapshot == {
            "amount": 1_000_000,
            "term_months": 24,
            "client_category": None,
            "info_questions": None,
        }


def test_counter_and_override(bank_context, pipeline_factory, run_persona):
    application_id = run_persona()
    client, _ = bank_context
    response = decide(client, application_id, outcome="COUNTER", amount=800_000)
    assert response.status_code == 200, response.text
    offer = response.json()["offer"]
    assert offer["kind"] == "COUNTER" and offer["amount"] == 800_000
    assert offer["monthly_payment"] == 43100
    assert (
        offer["counter_reason"] == "Специалист банка подобрал сумму и срок "
        "с учётом ваших оборотов и обязательств"
    )
    with pipeline_factory() as session:
        override = session.scalar(
            select(ApplicationEvent).where(
                ApplicationEvent.application_id == application_id,
                ApplicationEvent.event_type == "UNDERWRITER_OVERRIDE",
            )
        )
        assert override.payload["recommended"]["amount"] == 1_000_000
        assert override.payload["chosen"]["amount"] == 800_000


def test_decline_category_and_no_internal_leak(
    bank_context, pipeline_factory, run_persona
):
    application_id = run_persona()
    client, _ = bank_context
    response = decide(
        client,
        application_id,
        outcome="DECLINE",
        client_reason_category="Финансовое положение",
        comment="Внутренний комментарий специалиста",
    )
    assert response.status_code == 200, response.text
    public = client_get(client, pipeline_factory, application_id)
    assert public.json()["client_reason"] == {
        "code": "UNDERWRITER_DECLINE",
        "category": "Финансовое положение",
        "text": "Заявку рассмотрел специалист банка и не смог её одобрить",
        "action": None,
        "retry_after": None,
    }
    assert all(
        forbidden not in public.text
        for forbidden in (
            '"comment"',
            '"made_by"',
            "Внутренний комментарий",
            "UNDERWRITER_OVERRIDE",
            '"score"',
        )
    )
    with pipeline_factory() as session:
        state_event = session.scalar(
            select(ApplicationEvent).where(
                ApplicationEvent.application_id == application_id,
                ApplicationEvent.to_state == "DECLINED",
            )
        )
        assert state_event.reason_code == "UNDERWRITER_DECLINE"


def test_two_questions_and_answer_round_trip(
    bank_context, pipeline_factory, run_persona
):
    application_id = run_persona()
    client, _ = bank_context
    response = decide(
        client,
        application_id,
        outcome="REQUEST_INFO",
        info_questions=[
            "Уточните ваши обязательства",
            "Как планируете использовать кредит?",
        ],
    )
    assert response.status_code == 200, response.text
    public = client_get(client, pipeline_factory, application_id).json()
    assert public["state"] == "INFO_REQUESTED"
    assert len(public["info_request"]["items"]) == 2
    assert all(
        i["item_code"] == "UNDERWRITER_QUESTION" and not i["requires_value"]
        for i in public["info_request"]["items"]
    )
    with pipeline_factory() as session:
        user = session.get(User, session.get(Application, application_id).created_by)
    original = app.dependency_overrides[current_user]
    app.dependency_overrides[current_user] = lambda: user
    try:
        response = client.post(
            f"/api/v1/applications/{application_id}/info-response",
            json={
                "answers": [
                    {
                        "item_code": "UNDERWRITER_QUESTION",
                        "comment": "Обязательств нет",
                    },
                    {
                        "item_code": "UNDERWRITER_QUESTION",
                        "comment": "На покупку оборудования",
                    },
                ]
            },
        )
    finally:
        app.dependency_overrides[current_user] = original
    assert response.status_code == 200, response.text
    assert (
        client.get("/api/v1/underwriting/queue").json()[0]["route_reason"]
        == "INFO_RESPONSE"
    )
    assert decide(client, application_id).status_code == 200


@pytest.mark.parametrize(
    "product,amount,term,rate,payment",
    [
        # Independent Decimal annuity: 80811.850447590258... -> 80812 RUB.
        ("EXPRESS", 1_500_000, 24, 26, 80812),
        ("OVERDRAFT", 500_000, 12, 28, None),
    ],
)
def test_conservative_rate_without_policy(
    bank_context, run_persona, product, amount, term, rate, payment
):
    application_id = run_persona(
        "ip_good",
        app_params={"product": product, "amount": amount, "term": term},
        registry=FakeRegistryProvider({}),
    )
    client, _ = bank_context
    response = decide(client, application_id, amount=amount, term_months=term)
    assert response.status_code == 200, response.text
    card = response.json()
    assert card["offer"]["rate"] == rate
    assert card["offer"]["monthly_payment"] == payment
    assert card["company"]["status"] == "ACTIVE"
    assert card["company"]["director_full_name"] == ""
    assert card["company"]["founders"] == []
    assert card["company"]["source_note"] == "Данные из ЕГРИП не получены"


def test_overdraft_counter_term_must_be_twelve(bank_context, run_persona):
    application_id = run_persona(
        "ip_good",
        app_params={"product": "OVERDRAFT", "amount": 500_000, "term": 12},
        registry=FakeRegistryProvider({}),
    )
    client, _ = bank_context
    response = decide(
        client, application_id, outcome="COUNTER", amount=400_000, term_months=11
    )
    assert response.status_code == 422, response.text
    assert "term_months" in response.json()["error"]["details"]["fields"]


@pytest.mark.parametrize("unavailable", [False, True])
def test_answer_returns_current_route_then_approve_or_retry(
    bank_context, pipeline_factory, persona_data, run_persona, unavailable
):
    application_id = (
        run_persona("ip_good", registry=FakeRegistryProvider({}))
        if unavailable
        else run_persona()
    )
    client, _ = bank_context
    assert (
        decide(
            client,
            application_id,
            outcome="REQUEST_INFO",
            info_questions=["Уточните обязательства компании"],
        ).status_code
        == 200
    )
    with pipeline_factory() as session:
        user = session.get(User, session.get(Application, application_id).created_by)
    original = app.dependency_overrides[current_user]
    app.dependency_overrides[current_user] = lambda: user
    response = client.post(
        f"/api/v1/applications/{application_id}/info-response",
        json={
            "answers": [
                {
                    "item_code": "UNDERWRITER_QUESTION",
                    "comment": "Все обязательства указаны",
                }
            ]
        },
    )
    app.dependency_overrides[current_user] = original
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "MANUAL_REVIEW"
    queue = client.get("/api/v1/underwriting/queue").json()
    assert queue[0]["route_reason"] == "INFO_RESPONSE"
    response = decide(
        client, application_id, outcome="RETRY_ENRICHMENT" if unavailable else "APPROVE"
    )
    assert response.status_code == 200, response.text
    if unavailable:
        assert response.json()["state"] == "ENRICHMENT"
        assert response.json()["decisions"][0]["route_reason"] == "INFO_RESPONSE"
        drain(pipeline_factory, providers_for(persona_data), persona_data)
        with pipeline_factory() as session:
            assert session.get(Application, application_id).state == "OFFER_ISSUED"


def test_retry_only_unavailable(
    bank_context, run_persona, pipeline_factory, persona_data
):
    client, _ = bank_context
    application_id = run_persona()
    assert decide(client, application_id, outcome="RETRY_ENRICHMENT").status_code == 409
    failed_id = run_persona("ip_good", registry=FakeRegistryProvider({}))
    response = decide(client, failed_id, outcome="RETRY_ENRICHMENT")
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "ENRICHMENT"
    drain(pipeline_factory, providers_for(persona_data), persona_data)
    with pipeline_factory() as session:
        assert session.get(Application, failed_id).state == "OFFER_ISSUED"
        assert (
            session.scalar(
                select(func.count())
                .select_from(ExternalCheck)
                .where(ExternalCheck.application_id == failed_id)
            )
            == 6
        )


@pytest.mark.parametrize(
    "body,field",
    [
        ({"comment": None}, "comment"),
        ({"comment": "1234"}, "comment"),
        ({"amount": None}, "amount"),
        ({"term_months": None}, "term_months"),
        ({"amount": 900_000}, "amount"),
        ({"term_months": 25}, "amount"),
        ({"outcome": "COUNTER"}, "amount"),
        ({"outcome": "COUNTER", "amount": 1}, "amount"),
        ({"outcome": "COUNTER", "term_months": 1000}, "term_months"),
        ({"outcome": "DECLINE"}, "client_reason_category"),
        ({"outcome": "REQUEST_INFO"}, "info_questions"),
        (
            {"outcome": "REQUEST_INFO", "info_questions": ["Вопрос"] * 6},
            "info_questions",
        ),
        ({"outcome": "REQUEST_INFO", "info_questions": ["Раз"]}, "info_questions"),
        ({"outcome": "REQUEST_INFO", "info_questions": ["а" * 501]}, "info_questions"),
        (
            {"outcome": "REQUEST_INFO", "info_questions": ["Вопрос" + " " * 500]},
            "info_questions",
        ),
    ],
)
def test_field_validation(bank_context, run_persona, body, field):
    application_id = run_persona()
    client, _ = bank_context
    if body.get("comment", "") is None:
        payload = {"outcome": "APPROVE", "amount": 1_000_000, "term_months": 24}
        response = client.post(
            f"/api/v1/underwriting/{application_id}/decision", json=payload
        )
    else:
        response = decide(client, application_id, **body)
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert field in error["details"]["fields"]


def test_wrong_state_is_atomic(bank_context, pipeline_factory, run_persona):
    application_id = run_persona("ip_good")
    client, _ = bank_context
    assert decide(client, application_id).status_code == 409
    with pipeline_factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Decision)
                .where(
                    Decision.application_id == application_id, Decision.kind == "MANUAL"
                )
            )
            == 0
        )


@pytest.mark.parametrize(
    "outcome,missing",
    [
        ("APPROVE", "amount"),
        ("APPROVE", "term_months"),
        ("COUNTER", "amount"),
        ("COUNTER", "term_months"),
        ("DECLINE", "client_reason_category"),
        ("REQUEST_INFO", "info_questions"),
    ],
)
def test_decision_conditional_required_fields(
    bank_context, run_persona, outcome, missing
):
    # Migrated from test_schemas_validation.py per B-08 answer 24.10 ~18:15:
    # conditional checks now belong to the service and name the actual field.
    application_id = run_persona()
    client, _ = bank_context
    body = {
        "outcome": outcome,
        "amount": 800_000,
        "term_months": 24,
        "comment": "Проверены сведения компании",
        "client_reason_category": "Финансовое положение",
        "info_questions": ["Уточните обязательства компании"],
    }
    body.pop(missing)
    response = client.post(f"/api/v1/underwriting/{application_id}/decision", json=body)
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert missing in error["details"]["fields"]
    assert "request" not in error["details"]["fields"]
