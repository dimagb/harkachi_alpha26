"""Persist the engine protocol without exposing it through client schemas."""

import json
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.decision import DecisionInputs, DecisionResult
from app.models import Application, ApplicationEvent, Decision, DecisionConfig, Offer


def event(
    session: Session,
    application: Application,
    event_type: str,
    payload: dict[str, object],
) -> None:
    session.add(
        ApplicationEvent(
            application_id=application.id,
            event_type=event_type,
            actor_type="SYSTEM",
            actor_id=None,
            payload=payload,
            created_at=datetime.now(UTC),
        )
    )


def config_version(session: Session) -> int:
    version = session.scalar(
        select(DecisionConfig.version)
        .where(DecisionConfig.active.is_(True))
        .order_by(DecisionConfig.version.desc())
        .limit(1)
    )
    if version is None:
        raise ValueError("Нет активной конфигурации решения")
    return version


def _json_default(value):
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, frozenset):
        return sorted(value)
    raise TypeError("Неподдерживаемое значение снимка")


def save_decision(
    session: Session,
    application: Application,
    inputs: DecisionInputs,
    result: DecisionResult,
) -> None:
    recommendation = None
    if result.recommendation is not None:
        offer = result.recommendation.get("offer", {})
        recommendation = {
            "outcome": result.recommendation["outcome"],
            **{key: offer.get(key) for key in ("amount", "term_months", "rate")},
        }
    outcome = "MANUAL" if result.state == "MANUAL_REVIEW" else result.outcome
    session.add(
        Decision(
            application_id=application.id,
            kind="AUTO",
            outcome=outcome,
            route_reason=result.route_reason,
            grade=result.grade,
            score=result.score,
            factors=[asdict(factor) for factor in result.factors],
            rules_fired=[asdict(rule) for rule in result.rules_fired],
            policy=asdict(result.policy) if result.policy else None,
            what_if=result.what_if,
            internal_reasons=[
                rule.code for rule in result.rules_fired if rule.effect == "STOP"
            ],
            client_reason_code=result.client_reason_code,
            recommendation=recommendation,
            config_version=config_version(session),
            inputs_snapshot=json.loads(
                json.dumps(asdict(inputs), default=_json_default)
            ),
        )
    )
    event(
        session,
        application,
        "DECISION_MADE",
        {"outcome": outcome, "grade": result.grade},
    )


def save_offer(
    session: Session, application: Application, result: DecisionResult
) -> None:
    if result.offer is None:
        raise ValueError("Решение не содержит оферту")
    offer = Offer(
        application_id=application.id,
        version=1,
        kind="APPROVED" if result.outcome == "APPROVE" else "COUNTER",
        product_code=application.product_code,
        amount=result.offer.amount,
        term_months=result.offer.term_months,
        rate=Decimal(str(result.offer.rate)),
        monthly_payment=result.offer.monthly_payment,
        status="ACTIVE",
        expires_at=datetime.now(UTC) + timedelta(days=get_settings().offer_valid_days),
    )
    session.add(offer)
    session.flush()
    application.current_offer_id = offer.id
    event(session, application, "OFFER_ISSUED", {"offer_id": str(offer.id)})


def save_unavailable(
    session: Session,
    application: Application,
    responses: dict[str, dict[str, object] | None],
) -> None:
    session.add(
        Decision(
            application_id=application.id,
            kind="AUTO",
            outcome="MANUAL",
            route_reason="SOURCE_UNAVAILABLE",
            grade=None,
            score=None,
            factors=[],
            rules_fired=[],
            internal_reasons=[],
            policy=None,
            what_if=[],
            client_reason_code=None,
            recommendation=None,
            config_version=config_version(session),
            inputs_snapshot={
                "registry": responses["EGRUL"],
                "bki": responses["BKI"],
                "fns": responses["FNS"],
                "failed": [
                    source for source, response in responses.items() if response is None
                ],
            },
        )
    )
    event(session, application, "DECISION_MADE", {"outcome": "MANUAL", "grade": None})
