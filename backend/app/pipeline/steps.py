"""One committed transition at a time; source I/O never holds an app lock."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.applications.state_machine import transition
from app.config import get_settings
from app.decision import DEFAULT_CONFIG, decide, validation_rule
from app.integrations.bureau import BureauProvider
from app.integrations.registry import ProviderUnavailable, RegistryProvider
from app.integrations.tax import TaxProvider
from app.models import Application, Company, Consent, ExternalCheck, InfoRequest, Job
from app.pipeline.inputs import (
    answered_items,
    app_params,
    build_inputs,
    source_responses,
    turnover,
)
from app.pipeline.persist import event, save_decision, save_offer, save_unavailable


def _noop() -> None:
    pass


@dataclass(frozen=True)
class Providers:
    registry: RegistryProvider
    bureau: BureauProvider
    tax: TaxProvider
    heartbeat: Callable[[], None] = _noop


def _locked(session: Session, application_id: UUID) -> Application:
    return session.scalars(
        select(Application).where(Application.id == application_id).with_for_update()
    ).one()


def _delay() -> None:
    time.sleep(get_settings().pipeline_step_delay_sec)


def _schedule(session: Session, application: Application, step: str) -> None:
    session.add(
        Job(
            application_id=application.id,
            step=step,
            status="PENDING",
            attempts=0,
            run_after=datetime.now(UTC),
        )
    )


def validation(factory: sessionmaker[Session], application_id: UUID) -> None:
    _delay()
    with factory.begin() as session:
        application = _locked(session, application_id)
        if application.state == "SUBMITTED":
            transition(
                session, application, "VALIDATION", actor_type="SYSTEM", actor_id=None
            )
        elif application.state != "VALIDATION":
            return
    _delay()
    with factory.begin() as session:
        application = _locked(session, application_id)
        if application.state != "VALIDATION":
            return
        rule = validation_rule(
            app_params(application),
            turnover(session, application),
            answered_items(session, application),
            DEFAULT_CONFIG,
        )
        if rule:
            item_code, question = {
                "VAL_REVENUE_MISMATCH": (
                    "REVENUE_CONFIRM",
                    "Выручка в заявке заметно отличается от поступлений на ваш счёт "
                    "в банке. Подтвердите выручку и поясните разницу",
                ),
                "VAL_PURPOSE_UNCLEAR": (
                    "PURPOSE_DETAILS",
                    "Опишите, на что пойдут деньги",
                ),
            }[rule]
            session.add(
                InfoRequest(
                    application_id=application.id,
                    source="SYSTEM",
                    items=[
                        {
                            "item_code": item_code,
                            "question": question,
                            "requires_value": item_code == "REVENUE_CONFIRM",
                        }
                    ],
                    due_at=datetime.now(UTC)
                    + timedelta(days=get_settings().info_due_days),
                )
            )
            transition(
                session,
                application,
                "INFO_REQUESTED",
                actor_type="SYSTEM",
                actor_id=None,
                payload={"validation_rule": rule},
            )
        else:
            transition(
                session, application, "ENRICHMENT", actor_type="SYSTEM", actor_id=None
            )
            _schedule(session, application, "ENRICHMENT")


def _check_source(
    factory: sessionmaker[Session],
    application_id: UUID,
    source: str,
    providers: Providers,
) -> None:
    with factory.begin() as session:
        application = _locked(session, application_id)
        if application.state != "ENRICHMENT":
            return
        company = session.get(Company, application.company_id)
        inn = company.inn
        check = session.scalar(
            select(ExternalCheck)
            .where(
                ExternalCheck.application_id == application_id,
                ExternalCheck.source == source,
            )
            .order_by(ExternalCheck.created_at.desc())
            .limit(1)
        )
        if check is None:
            request = {"inn": inn}
            if source == "BKI":
                consent = session.scalar(
                    select(Consent)
                    .where(
                        Consent.application_id == application_id,
                        Consent.type == "BKI",
                        Consent.granted.is_(True),
                    )
                    .order_by(Consent.created_at.desc())
                    .limit(1)
                )
                request.update(
                    kind="FULL", consent_id=str(consent.id) if consent else None
                )
            check = ExternalCheck(
                application_id=application_id,
                source=source,
                request=request,
                status="PENDING",
                attempts=0,
            )
            session.add(check)
            session.flush()
            event(session, application, "CHECK_REQUESTED", {"source": source})
        check_id, request = check.id, check.request
    while True:
        providers.heartbeat()
        with factory.begin() as session:
            application = _locked(session, application_id)
            if application.state != "ENRICHMENT":
                return
            check = session.get(ExternalCheck, check_id)
            if check.status == "OK" or check.attempts >= 3:
                return
            check.attempts += 1
        try:
            if source == "EGRUL":
                response = providers.registry.get(inn)
            elif source == "BKI":
                if request["consent_id"] is None:
                    raise ProviderUnavailable()
                response = providers.bureau.get(inn, request["consent_id"])
            else:
                response = providers.tax.get(inn)
            if response is None:
                raise ProviderUnavailable()
            response_data = response.model_dump(mode="json")
        except ProviderUnavailable:
            response_data = None
        providers.heartbeat()
        with factory.begin() as session:
            application = _locked(session, application_id)
            if application.state != "ENRICHMENT":
                return
            check = session.get(ExternalCheck, check_id)
            check.response = response_data
            check.status = "OK" if response_data is not None else "FAILED"
            check.fetched_at = datetime.now(UTC)
            event(
                session,
                application,
                "CHECK_RECEIVED" if response_data is not None else "CHECK_FAILED",
                {"source": source, "attempt": check.attempts},
            )
            finished = response_data is not None or check.attempts >= 3
        if finished:
            return
        time.sleep(get_settings().source_retry_pause_sec)


def enrichment(
    factory: sessionmaker[Session], application_id: UUID, providers: Providers
) -> None:
    for source in ("EGRUL", "BKI", "FNS"):
        _check_source(factory, application_id, source, providers)
    _delay()
    with factory.begin() as session:
        application = _locked(session, application_id)
        if application.state != "ENRICHMENT":
            return
        responses = source_responses(session, application)
        if any(response is None for response in responses.values()):
            save_unavailable(session, application, responses)
            transition(
                session,
                application,
                "MANUAL_REVIEW",
                actor_type="SYSTEM",
                actor_id=None,
                payload={"route_reason": "SOURCE_UNAVAILABLE"},
            )
        else:
            transition(
                session, application, "ASSESSMENT", actor_type="SYSTEM", actor_id=None
            )
            _schedule(session, application, "ASSESSMENT")


def assessment(
    factory: sessionmaker[Session], application_id: UUID, today: Callable[[], date]
) -> None:
    _delay()
    with factory.begin() as session:
        application = _locked(session, application_id)
        if application.state != "ASSESSMENT":
            return
        inputs = build_inputs(session, application, today())
        result = decide(inputs, DEFAULT_CONFIG)
        if result.state == "INFO_REQUESTED":
            raise ValueError("Повторный дозапрос на этапе оценки")
        save_decision(session, application, inputs, result)
        payload = None
        reason_code = None
        if result.state == "OFFER_ISSUED":
            save_offer(session, application, result)
        elif result.state == "DECLINED":
            reason_code = result.client_reason_code
        elif result.state == "MANUAL_REVIEW":
            payload = {"route_reason": result.route_reason}
        transition(
            session,
            application,
            result.state,
            actor_type="SYSTEM",
            actor_id=None,
            reason_code=reason_code,
            payload=payload,
        )


def process_step(
    factory: sessionmaker[Session],
    application_id: UUID,
    step: str,
    providers: Providers,
    today: Callable[[], date],
) -> None:
    if step == "VALIDATION":
        validation(factory, application_id)
    elif step == "ENRICHMENT":
        enrichment(factory, application_id, providers)
    elif step == "ASSESSMENT":
        assessment(factory, application_id, today)
    else:
        raise ValueError("Шаг ещё не поддерживается")
