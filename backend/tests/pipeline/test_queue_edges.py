from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from functools import partial

import pytest
from sqlalchemy import select

from app.applications.state_machine import transition
from app.models import (
    Application,
    ApplicationEvent,
    Consent,
    Decision,
    ExternalCheck,
    InfoRequest,
    Job,
)

from .test_pipeline import drain, providers_for, submit_persona


def test_queue_skips_locked_and_future_jobs_and_orders_due_jobs(
    pipeline_factory, persona_data
):
    from app.pipeline.queue import run_once

    first = submit_persona(pipeline_factory, persona_data["personas"][0])
    second = submit_persona(pipeline_factory, persona_data["personas"][1])
    future = submit_persona(pipeline_factory, persona_data["personas"][2])
    now = datetime.now(UTC)
    with pipeline_factory.begin() as session:
        for job in session.scalars(select(Job)):
            job.run_after = (
                now + timedelta(days=1)
                if job.application_id == future
                else now - timedelta(seconds=2 if job.application_id == first else 1)
            )
    providers = providers_for(persona_data)
    today = partial(date.fromisoformat, persona_data["_meta"]["as_of"])
    with pipeline_factory.begin() as lock:
        locked = lock.scalar(
            select(Job).where(Job.application_id == first).with_for_update()
        )
        assert run_once(pipeline_factory, providers, today)
        with pipeline_factory() as observer:
            assert observer.get(Job, locked.id).attempts == 0
            assert observer.get(Application, second).state == "ENRICHMENT"
            assert observer.get(Application, future).state == "SUBMITTED"
    # The oldest due job becomes available as soon as its lock is released.
    assert run_once(pipeline_factory, providers, today)
    with pipeline_factory() as session:
        assert session.get(Application, first).state == "ENRICHMENT"
        job = session.scalar(
            select(Job).where(Job.application_id == first, Job.step == "VALIDATION")
        )
        assert job.status == "DONE" and job.attempts == 1
        assert session.get(Application, future).state == "SUBMITTED"


def test_validation_resumes_after_committed_first_transition(
    pipeline_factory, persona_data
):
    from app.pipeline.queue import run_once

    application_id = submit_persona(pipeline_factory, persona_data["personas"][0])
    with pipeline_factory.begin() as session:
        app = session.get(Application, application_id)
        transition(session, app, "VALIDATION", actor_type="SYSTEM", actor_id=None)
    assert run_once(
        pipeline_factory,
        providers_for(persona_data),
        partial(date.fromisoformat, persona_data["_meta"]["as_of"]),
    )
    with pipeline_factory() as session:
        assert session.get(Application, application_id).state == "ENRICHMENT"
        assert (
            len(
                list(
                    session.scalars(
                        select(ApplicationEvent).where(
                            ApplicationEvent.to_state == "VALIDATION"
                        )
                    )
                )
            )
            == 1
        )


def test_registry_not_found_is_retried_and_other_sources_are_collected(
    pipeline_factory, persona_data
):
    from app.integrations.registry import FakeRegistryProvider

    application_id = submit_persona(pipeline_factory, persona_data["personas"][0])
    drain(
        pipeline_factory,
        providers_for(persona_data, registry=FakeRegistryProvider({})),
        persona_data,
    )
    with pipeline_factory() as session:
        check = session.scalar(
            select(ExternalCheck).where(ExternalCheck.source == "EGRUL")
        )
        assert check.attempts == 3 and check.status == "FAILED"
        assert session.get(Application, application_id).state == "MANUAL_REVIEW"
        assert session.scalar(select(Decision)).inputs_snapshot["failed"] == ["EGRUL"]
        assert set(
            session.scalars(
                select(ExternalCheck.source).where(ExternalCheck.status == "OK")
            )
        ) == {"BKI", "FNS"}


@pytest.mark.parametrize("consent_mode", ["missing", "denied"])
def test_ip_without_auto_consent_keeps_decline_as_flat_recommendation(
    pipeline_factory, persona_data, consent_mode
):
    persona = next(p for p in persona_data["personas"] if p["code"] == "ip_bad")
    application_id = submit_persona(pipeline_factory, persona)
    with pipeline_factory.begin() as session:
        consent = session.scalar(select(Consent).where(Consent.type == "AUTO_DECISION"))
        if consent_mode == "missing":
            # Signatures reference a document UUID, not a consent foreign key.
            session.delete(consent)
        else:
            consent.granted = False
    drain(pipeline_factory, providers_for(persona_data), persona_data)
    with pipeline_factory() as session:
        assert session.get(Application, application_id).state == "MANUAL_REVIEW"
        decision = session.scalar(select(Decision))
        assert (
            decision.route_reason == "NO_AUTO_CONSENT" and decision.outcome == "MANUAL"
        )
        assert decision.recommendation == {
            "outcome": "DECLINE",
            "amount": None,
            "term_months": None,
            "rate": None,
        }
        assert decision.inputs_snapshot["auto_decision_consent"] is False


def test_purpose_request_ignores_underwriter_answers(pipeline_factory, persona_data):
    persona = deepcopy(persona_data["personas"][0])
    persona["demo"]["app"].update(purpose="OTHER", purpose_text=None)
    application_id = submit_persona(pipeline_factory, persona)
    with pipeline_factory.begin() as session:
        session.add(
            InfoRequest(
                application_id=application_id,
                source="UNDERWRITER",
                items=[],
                due_at=datetime.now(UTC) + timedelta(days=1),
                responded_at=datetime.now(UTC),
                response=[
                    {"item_code": "PURPOSE_DETAILS", "comment": "Ответ специалисту"}
                ],
            )
        )
    drain(pipeline_factory, providers_for(persona_data), persona_data)
    with pipeline_factory() as session:
        request = session.scalar(
            select(InfoRequest).where(InfoRequest.source == "SYSTEM")
        )
        assert request.items == [
            {
                "item_code": "PURPOSE_DETAILS",
                "question": "Опишите, на что пойдут деньги",
                "requires_value": False,
            }
        ]
        assert session.get(Application, application_id).state == "INFO_REQUESTED"
