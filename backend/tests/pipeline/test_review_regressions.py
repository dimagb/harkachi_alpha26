from datetime import UTC, date, datetime
from functools import partial

import pytest
from sqlalchemy import delete, select

from app.applications.state_machine import transition
from app.integrations.registry import FakeRegistryProvider
from app.models import (
    AccountTurnover,
    Application,
    ApplicationEvent,
    ExternalCheck,
    Job,
)
from app.pipeline.inputs import source_responses, turnover
from app.pipeline.queue import run_once

from .test_pipeline import drain, providers_for, submit_persona


@pytest.fixture
def retry_context(pipeline_factory, persona_data):
    application_id = submit_persona(pipeline_factory, persona_data["personas"][0])
    drain(
        pipeline_factory,
        providers_for(persona_data, registry=FakeRegistryProvider({})),
        persona_data,
    )
    with pipeline_factory.begin() as session:
        application = session.get(Application, application_id)
        assert application.state == "MANUAL_REVIEW"
        transition(
            session, application, "ENRICHMENT", actor_type="UNDERWRITER", actor_id=None
        )
        session.add(
            Job(
                application_id=application_id,
                step="ENRICHMENT",
                status="PENDING",
                run_after=datetime.now(UTC),
            )
        )
    return application_id


def test_retry_enrichment_ignores_responses_from_previous_pass(
    pipeline_factory, retry_context
):
    with pipeline_factory() as session:
        application = session.get(Application, retry_context)
        assert source_responses(session, application) == {
            "EGRUL": None,
            "BKI": None,
            "FNS": None,
        }


def test_retry_enrichment_requeries_all_sources_and_reaches_offer(
    pipeline_factory, persona_data, retry_context
):
    application_id = retry_context
    healthy = providers_for(persona_data)
    calls = []

    class RecordingProvider:
        def __init__(self, source, provider):
            self.source, self.provider = source, provider

        def get(self, *args):
            calls.append((self.source, args[0]))
            return self.provider.get(*args)

    providers = providers_for(
        persona_data,
        registry=RecordingProvider("EGRUL", healthy.registry),
        bureau=RecordingProvider("BKI", healthy.bureau),
        tax=RecordingProvider("FNS", healthy.tax),
    )
    today = partial(date.fromisoformat, persona_data["_meta"]["as_of"])
    assert run_once(pipeline_factory, providers, today)
    with pipeline_factory() as session:
        assert session.get(Application, application_id).state == "ASSESSMENT"
        started_at = session.scalar(
            select(ApplicationEvent.created_at)
            .where(
                ApplicationEvent.application_id == application_id,
                ApplicationEvent.event_type == "STATE_CHANGED",
                ApplicationEvent.to_state == "ENRICHMENT",
            )
            .order_by(ApplicationEvent.created_at.desc())
            .limit(1)
        )
        checks = list(
            session.scalars(
                select(ExternalCheck).where(
                    ExternalCheck.application_id == application_id,
                    ExternalCheck.created_at > started_at,
                )
            )
        )
        assert len(checks) == 3
        assert all(check.status == "OK" and check.attempts == 1 for check in checks)
        old_checks = list(
            session.scalars(
                select(ExternalCheck).where(
                    ExternalCheck.application_id == application_id,
                    ExternalCheck.created_at < started_at,
                )
            )
        )
        assert len(old_checks) == 3
        assert next(c for c in old_checks if c.source == "EGRUL").attempts == 3
    assert calls == [
        (source, persona_data["personas"][0]["inn"])
        for source in ("EGRUL", "BKI", "FNS")
    ]
    drain(pipeline_factory, providers, persona_data)
    with pipeline_factory() as session:
        assert session.get(Application, application_id).state == "OFFER_ISSUED"


def test_turnover_uses_latest_twelve_months_in_chronological_order(
    pipeline_factory, persona_data
):
    application_id = submit_persona(pipeline_factory, persona_data["personas"][0])
    with pipeline_factory.begin() as session:
        application = session.get(Application, application_id)
        session.execute(
            delete(AccountTurnover).where(
                AccountTurnover.company_id == application.company_id
            )
        )
        session.add_all(
            [
                AccountTurnover(
                    company_id=application.company_id,
                    month=f"{2025 + index // 12}-{index % 12 + 1:02}",
                    credit_turnover=(index + 1) * 100_000,
                )
                for index in reversed(range(14))
            ]
        )
    with pipeline_factory() as session:
        assert turnover(session, session.get(Application, application_id)) == (
            300_000,
            400_000,
            500_000,
            600_000,
            700_000,
            800_000,
            900_000,
            1_000_000,
            1_100_000,
            1_200_000,
            1_300_000,
            1_400_000,
        )


def test_turnover_without_rows_reports_clear_error(pipeline_factory, persona_data):
    application_id = submit_persona(pipeline_factory, persona_data["personas"][0])
    with pipeline_factory.begin() as session:
        application = session.get(Application, application_id)
        session.execute(
            delete(AccountTurnover).where(
                AccountTurnover.company_id == application.company_id
            )
        )
    with pipeline_factory() as session:
        with pytest.raises(ValueError, match="Нет данных об оборотах"):
            turnover(session, session.get(Application, application_id))
