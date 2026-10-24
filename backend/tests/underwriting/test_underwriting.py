import re
from uuid import uuid4

import pytest
from pipeline.test_pipeline import drain, providers_for
from sqlalchemy import event, func, select

from app.auth.deps import current_user
from app.integrations.registry import FakeRegistryProvider
from app.main import app
from app.models import Application, ApplicationEvent, Decision, ExternalCheck, User


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
