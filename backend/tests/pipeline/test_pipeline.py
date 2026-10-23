from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from functools import partial
from threading import Barrier, Event
from uuid import UUID

import pytest
from sqlalchemy import func, select, text

from app.applications.state_machine import transition
from app.config import get_settings
from app.integrations.registry import FakeRegistryProvider, ProviderUnavailable
from app.models import (
    Application,
    ApplicationEvent,
    Company,
    Consent,
    Decision,
    ExternalCheck,
    InfoRequest,
    Job,
    Offer,
    User,
)
from app.signing import otp
from app.signing.submit import submit


def providers_for(data, **overrides):
    from app.integrations.bureau import FakeBureauProvider
    from app.integrations.tax import FakeTaxProvider
    from app.pipeline.steps import Providers

    personas = data["personas"]
    return Providers(
        **{
            "registry": FakeRegistryProvider(
                {
                    p["inn"]: {
                        key: p[key]
                        for key in (
                            "inn",
                            "ogrn",
                            "kind",
                            "name",
                            "status",
                            "reg_date",
                            "okved_main",
                            "address",
                            "director",
                            "founders",
                        )
                    }
                    for p in personas
                }
            ),
            "bureau": FakeBureauProvider(
                {
                    p["inn"]: {"inn": p["inn"], "kind": "FULL", **p["bki"]}
                    for p in personas
                }
            ),
            "tax": FakeTaxProvider(
                {p["inn"]: {"inn": p["inn"], **p["fns"]} for p in personas}
            ),
            **overrides,
        }
    )


def submit_persona(factory, persona):
    # A fresh draft is sent through the actual B-06 OTP and submit functions.
    from app.schemas.api import OtpRequest, SubmitRequest

    params = persona["demo"]["app"]
    with factory() as session:
        company = session.scalar(select(Company).where(Company.inn == persona["inn"]))
        user = session.scalar(select(User).where(User.login == persona["code"]))
        application = Application(
            company_id=company.id,
            created_by=user.id,
            product_code=params["product"],
            amount=params["amount"],
            term_months=params["term"],
            purpose=params["purpose"],
            purpose_text=params.get("purpose_text"),
            declared_revenue_year=params["declared_revenue_year"],
            state="DRAFT",
        )
        session.add(application)
        session.commit()
        result = otp.issue(
            session, application.id, OtpRequest(purpose="CONSENTS"), user
        )
        body = SubmitRequest.model_validate(
            {
                "otp_id": str(result.otp_id),
                "code": result.demo_code,
                "consents": persona["demo"]["consents"],
            }
        )
        submit(session, application.id, body, user)
        return application.id


def drain(factory, providers, data):
    from app.pipeline.queue import run_once

    def today():
        return date.fromisoformat(data["_meta"]["as_of"])

    for _ in range(12):
        if not run_once(factory, providers, today):
            return
    pytest.fail("Конвейер не опустошил очередь")


def assert_expected(session, application_id, expected, as_of):
    application = session.get(Application, application_id)
    assert application.state == expected["state"]
    decision = session.scalar(
        select(Decision).where(Decision.application_id == application_id)
    )
    assert decision.kind == "AUTO"
    scoring = expected.get("recommendation", expected)
    assert decision.grade == scoring.get("grade")
    assert decision.score == scoring.get("score")
    assert {f["code"]: f["points"] for f in decision.factors} == scoring.get(
        "points", {}
    )
    if "reason_code" in expected:
        assert decision.client_reason_code == expected["client_reason_code"]
        assert decision.internal_reasons[0] == expected["reason_code"]
    if "route_reason" in expected:
        assert decision.outcome == "MANUAL"
        assert decision.route_reason == expected["route_reason"]
        recommendation = expected["recommendation"]
        offer = recommendation.get("offer", {})
        assert decision.recommendation == {
            "outcome": recommendation["outcome"],
            **{key: offer.get(key) for key in ("amount", "term_months", "rate")},
        }
    else:
        assert decision.outcome == expected["outcome"]
    if "offer" in expected:
        offer = session.get(Offer, application.current_offer_id)
        assert {key: getattr(offer, key) for key in expected["offer"]} == expected[
            "offer"
        ]
        assert offer.version == 1 and offer.status == "ACTIVE"
        assert offer.kind == (
            "APPROVED" if expected["outcome"] == "APPROVE" else "COUNTER"
        )
        assert offer.expires_at > datetime.now(UTC) + timedelta(days=29)
    assert decision.config_version == 1
    assert decision.inputs_snapshot["as_of"] == as_of
    assert len(decision.inputs_snapshot["turnover"]) == 12
    assert isinstance(decision.inputs_snapshot["answered_items"], list)
    assert (
        decision.policy is not None
        if decision.score is not None
        else decision.policy is None
    )
    assert isinstance(decision.what_if, list)


@pytest.mark.parametrize(
    "code", ["ip_good", "ooo_load", "ooo_gap", "ip_bad", "ooo_border", "ooo_aml"]
)
def test_golden_submission_to_decision(pipeline_factory, persona_data, code):
    persona = next(p for p in persona_data["personas"] if p["code"] == code)
    application_id = submit_persona(pipeline_factory, persona)
    providers = providers_for(persona_data)
    drain(pipeline_factory, providers, persona_data)
    expected = persona["demo"]["expected"]
    if "first_state" in expected:
        with pipeline_factory.begin() as session:
            application = session.get(Application, application_id)
            assert application.state == expected["first_state"]
            request = session.scalar(
                select(InfoRequest).where(InfoRequest.application_id == application_id)
            )
            assert request.source == "SYSTEM"
            assert request.items == [
                {
                    "item_code": "REVENUE_CONFIRM",
                    "question": "Выручка в заявке заметно отличается от поступлений "
                    "на ваш счёт в банке. Подтвердите выручку и поясните разницу",
                    "requires_value": True,
                }
            ]
            assert request.due_at > datetime.now(UTC) + timedelta(days=4)
            event = session.scalar(
                select(ApplicationEvent).where(
                    ApplicationEvent.to_state == "INFO_REQUESTED"
                )
            )
            assert event.payload == {"validation_rule": expected["validation_rule"]}
            assert event.reason_code is None
            request.response = persona["demo"]["info_response"]
            request.responded_at = datetime.now(UTC)
            transition(
                session,
                application,
                "VALIDATION",
                actor_type="CLIENT",
                actor_id=application.created_by,
            )
            session.add(
                Job(
                    application_id=application_id,
                    step="VALIDATION",
                    status="PENDING",
                    run_after=datetime.now(UTC),
                )
            )
        drain(pipeline_factory, providers, persona_data)
        expected = expected["after_info"]
    with pipeline_factory() as session:
        assert_expected(
            session, application_id, expected, persona_data["_meta"]["as_of"]
        )
        assert set(session.scalars(select(Job.status))) == {"DONE"}


def test_journal_committed_steps_and_replay_has_no_effect(
    pipeline_factory, persona_data, monkeypatch
):
    from app.pipeline.queue import run_once

    application_id = submit_persona(pipeline_factory, persona_data["personas"][0])
    observed = []

    def observe_delay(_):
        # Another connection must observe the previously committed intermediate state.
        with pipeline_factory.begin() as session:
            session.execute(text("SET LOCAL lock_timeout = '100ms'"))
            app = session.scalar(
                select(Application)
                .where(Application.id == application_id)
                .with_for_update(nowait=True)
            )
            observed.append(app.state)

    monkeypatch.setattr("app.pipeline.steps.time.sleep", observe_delay)
    drain(pipeline_factory, providers_for(persona_data), persona_data)
    with pipeline_factory.begin() as session:
        events = list(
            session.scalars(
                select(ApplicationEvent).order_by(ApplicationEvent.created_at)
            )
        )
        transitions = [e for e in events if e.event_type == "STATE_CHANGED"]
        assert [e.to_state for e in transitions] == [
            "SUBMITTED",
            "VALIDATION",
            "ENRICHMENT",
            "ASSESSMENT",
            "OFFER_ISSUED",
        ]
        assert len({e.created_at for e in transitions}) == 5
        assert set(observed) >= {"SUBMITTED", "VALIDATION", "ENRICHMENT", "ASSESSMENT"}
        assert [e.event_type for e in events].count("CHECK_REQUESTED") == 3
        assert [e.event_type for e in events].count("CHECK_RECEIVED") == 3
        assert [e.event_type for e in events].count("DECISION_MADE") == 1
        assert [e.event_type for e in events].count("OFFER_ISSUED") == 1
        assert all(e.reason_code is None for e in events)
        before = [(e.id, e.payload) for e in events]
        for job in session.scalars(select(Job)):
            job.status = "PENDING"
    drain(pipeline_factory, providers_for(persona_data), persona_data)
    with pipeline_factory() as session:
        assert [
            (e.id, e.payload)
            for e in session.scalars(
                select(ApplicationEvent).order_by(ApplicationEvent.created_at)
            )
        ] == before
    assert (
        run_once(
            pipeline_factory,
            providers_for(persona_data),
            partial(date.fromisoformat, persona_data["_meta"]["as_of"]),
        )
        is False
    )


@pytest.mark.parametrize("failures", [2, 3])
def test_bureau_retry_and_other_sources_still_run(
    pipeline_factory, persona_data, failures
):
    normal = providers_for(persona_data)
    calls = []

    class FlakyBureau:
        def get(self, inn, consent_id):
            with pipeline_factory.begin() as session:
                session.execute(text("SET LOCAL lock_timeout = '100ms'"))
                # Source I/O must not run inside a transaction locking the application.
                session.scalar(select(Application).with_for_update(nowait=True))
                consent = session.get(Consent, UUID(consent_id))
                assert consent.type == "BKI" and consent.granted
            calls.append(inn)
            if len(calls) <= failures:
                raise ProviderUnavailable("secret=never-store-this")
            return normal.bureau.get(inn, consent_id)

    heartbeats = []
    application_id = submit_persona(pipeline_factory, persona_data["personas"][0])
    drain(
        pipeline_factory,
        providers_for(
            persona_data,
            bureau=FlakyBureau(),
            heartbeat=lambda: heartbeats.append(True),
        ),
        persona_data,
    )
    assert len(heartbeats) >= 3
    with pipeline_factory() as session:
        check = session.scalar(
            select(ExternalCheck).where(ExternalCheck.source == "BKI")
        )
        assert check.attempts == 3
        assert (
            session.scalar(
                select(ExternalCheck.status).where(ExternalCheck.source == "FNS")
            )
            == "OK"
        )
        failed = list(
            session.scalars(
                select(ApplicationEvent).where(
                    ApplicationEvent.event_type == "CHECK_FAILED"
                )
            )
        )
        assert len(failed) == failures
        assert all(e.payload["source"] == "BKI" for e in failed)
        if failures == 3:
            assert session.get(Application, application_id).state == "MANUAL_REVIEW"
            event = session.scalar(
                select(ApplicationEvent).where(
                    ApplicationEvent.application_id == application_id,
                    ApplicationEvent.event_type == "STATE_CHANGED",
                    ApplicationEvent.to_state == "MANUAL_REVIEW",
                )
            )
            assert event.payload == {"route_reason": "SOURCE_UNAVAILABLE"}
            decision = session.scalar(select(Decision))
            assert (
                decision.outcome == "MANUAL"
                and decision.route_reason == "SOURCE_UNAVAILABLE"
            )
            assert decision.grade is None and decision.score is None
            assert decision.factors == decision.rules_fired == []
            assert decision.inputs_snapshot["failed"] == ["BKI"]
            assert decision.inputs_snapshot["bki"] is None
            assert (
                decision.inputs_snapshot["registry"] and decision.inputs_snapshot["fns"]
            )
            assert set(session.scalars(select(Job.status))) == {"DONE"}
        else:
            assert session.get(Application, application_id).state == "OFFER_ISSUED"


def test_two_workers_do_not_claim_same_job(pipeline_factory, persona_data):
    from app.pipeline.queue import run_once

    application_id = submit_persona(pipeline_factory, persona_data["personas"][0])
    normal = providers_for(persona_data)
    today = partial(date.fromisoformat, persona_data["_meta"]["as_of"])
    assert run_once(pipeline_factory, normal, today)  # VALIDATION schedules ENRICHMENT
    barrier, release = Barrier(2), Event()

    class BlockingRegistry:
        def get(self, inn):
            barrier.wait(timeout=10)
            assert release.wait(timeout=10)
            return normal.registry.get(inn)

    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(
            run_once,
            pipeline_factory,
            providers_for(persona_data, registry=BlockingRegistry()),
            today,
        )
        try:
            barrier.wait(timeout=10)
            assert (
                pool.submit(run_once, pipeline_factory, normal, today).result(timeout=5)
                is False
            )
        finally:
            release.set()
        assert future.result(timeout=10) is True
    with pipeline_factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ApplicationEvent)
                .where(
                    ApplicationEvent.application_id == application_id,
                    ApplicationEvent.to_state == "ASSESSMENT",
                )
            )
            == 1
        )


def test_recover_only_stale_running_jobs(pipeline_factory, persona_data):
    from app.pipeline.queue import recover_stale

    application_id = submit_persona(pipeline_factory, persona_data["personas"][0])
    now = datetime.now(UTC)
    with pipeline_factory.begin() as session:
        stale = session.scalar(select(Job))
        stale.status = "RUNNING"
        stale.updated_at = now - timedelta(seconds=61)
        recent = Job(
            application_id=application_id,
            step="ENRICHMENT",
            status="RUNNING",
            run_after=now,
        )
        session.add(recent)
        session.flush()
        stale_id, recent_id = stale.id, recent.id
    assert recover_stale(pipeline_factory) == 1
    with pipeline_factory() as session:
        assert session.get(Job, stale_id).status == "PENDING"
        assert session.get(Job, recent_id).status == "RUNNING"


def test_unexpected_assessment_info_request_fails_without_partial_decision(
    pipeline_factory, persona_data, monkeypatch, caplog
):
    from app.decision import DecisionResult
    from app.pipeline.queue import run_once

    application_id = submit_persona(pipeline_factory, persona_data["personas"][0])
    providers = providers_for(persona_data)
    today = partial(date.fromisoformat, persona_data["_meta"]["as_of"])
    assert run_once(pipeline_factory, providers, today)
    assert run_once(pipeline_factory, providers, today)
    monkeypatch.setattr(
        "app.pipeline.steps.decide", lambda *_: DecisionResult(state="INFO_REQUESTED")
    )
    assert run_once(pipeline_factory, providers, today)
    with pipeline_factory() as session:
        assert session.get(Application, application_id).state == "ASSESSMENT"
        assert session.scalar(select(func.count()).select_from(Decision)) == 0
        job = session.scalar(select(Job).where(Job.step == "ASSESSMENT"))
        assert job.status == "FAILED" and "ValueError" in job.last_error
    assert any(record.levelname == "ERROR" for record in caplog.records)


def test_pipeline_default_durations():
    settings = get_settings()
    assert settings.pipeline_step_delay_sec == 2
    assert settings.source_retry_pause_sec == 1
    assert settings.info_due_days == 5
    assert settings.offer_valid_days == 30
