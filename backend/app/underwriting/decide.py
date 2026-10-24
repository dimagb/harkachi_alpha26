"""Transactional manual decisions; all state changes use transition()."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.applications.state_machine import transition
from app.catalog.calculator import validate_terms
from app.config import get_settings
from app.decision import DEFAULT_CONFIG
from app.decision.scoring import annuity, rub
from app.errors import ApiErrorException
from app.models import (
    Application,
    ApplicationEvent,
    Decision,
    DecisionConfig,
    InfoRequest,
    Job,
    Offer,
    User,
)
from app.objections import service as objections
from app.pipeline.persist import config_version
from app.schemas.api import ApplicationBank, UnderwriterDecisionRequest
from app.underwriting.card import get_application, to_bank
from app.underwriting.queue import current_route


def _invalid(field: str, message: str):
    raise ApiErrorException(
        422,
        "VALIDATION_ERROR",
        "Проверьте данные решения",
        {"fields": {field: message}},
    )


def _validate(
    session: Session,
    application: Application,
    body: UnderwriterDecisionRequest,
    auto: Decision | None,
):
    if application.state != "MANUAL_REVIEW":
        raise ApiErrorException(
            409, "INVALID_TRANSITION", "Заявка не находится на рассмотрении специалиста"
        )
    if not 5 <= len(body.comment.strip()) <= 2000:
        _invalid("comment", "Введите комментарий от 5 до 2000 символов")
    if body.outcome in {"APPROVE", "COUNTER"}:
        if body.amount is None:
            _invalid("amount", "Укажите сумму кредита")
        if body.term_months is None:
            _invalid("term_months", "Укажите срок кредита")
        same = (body.amount, body.term_months) == (
            application.amount,
            application.term_months,
        )
        if body.outcome == "APPROVE" and not same:
            _invalid(
                "amount", "Для другой суммы или срока выберите встречное предложение"
            )
        if body.outcome == "COUNTER" and same:
            _invalid("amount", "Это параметры заявки — выберите одобрение")
        return validate_terms(
            session, application.product_code, body.amount, body.term_months
        )
    if body.outcome == "DECLINE" and body.client_reason_category is None:
        _invalid("client_reason_category", "Укажите причину отказа")
    if body.outcome == "REQUEST_INFO" and (
        not body.info_questions
        or not 1 <= len(body.info_questions) <= 5
        or any(
            not 5 <= len(question) <= 500 or len(question.strip()) < 5
            for question in body.info_questions
        )
    ):
        _invalid(
            "info_questions", "Укажите от 1 до 5 вопросов, каждый от 5 до 500 символов"
        )
    if body.outcome == "RETRY_ENRICHMENT" and (
        auto is None or auto.route_reason != "SOURCE_UNAVAILABLE"
    ):
        raise ApiErrorException(
            409,
            "INVALID_TRANSITION",
            "Повторный сбор возможен, если источник данных был недоступен",
        )
    return None


def _event(
    session: Session,
    application: Application,
    user: User,
    event_type: str,
    payload: dict,
):
    session.add(
        ApplicationEvent(
            application_id=application.id,
            event_type=event_type,
            actor_type="UNDERWRITER",
            actor_id=user.id,
            payload=payload,
            created_at=datetime.now(UTC),
        )
    )


def make_decision(
    session: Session, application_id: UUID, body: UnderwriterDecisionRequest, user: User
) -> ApplicationBank:
    try:
        application = get_application(session, application_id, lock=True)
        auto = session.scalar(
            select(Decision)
            .where(Decision.application_id == application.id, Decision.kind == "AUTO")
            .order_by(Decision.created_at.desc(), Decision.id.desc())
            .limit(1)
        )
        _validate(session, application, body, auto)
        version = auto.config_version if auto else config_version(session)
        now = datetime.now(UTC)
        decision = Decision(
            application_id=application.id,
            kind="MANUAL",
            outcome=body.outcome,
            route_reason=current_route(session, application, auto),
            grade=auto.grade if auto else None,
            score=auto.score if auto else None,
            factors=[],
            rules_fired=[],
            internal_reasons=[],
            what_if=[],
            policy=None,
            recommendation=None,
            made_by=user.id,
            comment=body.comment,
            config_version=version,
            client_reason_code="UNDERWRITER_DECLINE"
            if body.outcome == "DECLINE"
            else None,
            inputs_snapshot={
                "amount": body.amount,
                "term_months": body.term_months,
                "client_category": body.client_reason_category,
                "info_questions": body.info_questions,
            },
            created_at=now,
        )
        session.add(decision)
        _event(
            session,
            application,
            user,
            "DECISION_MADE",
            {"outcome": body.outcome, "kind": "MANUAL", "comment": body.comment},
        )
        if body.outcome in {"APPROVE", "COUNTER"}:
            cfg = session.scalar(
                select(DecisionConfig).where(DecisionConfig.version == version)
            )
            rate = (
                Decimal(str(auto.policy["rate"]))
                if auto and auto.policy is not None
                else Decimal(str(cfg.key_rate))
                + Decimal(
                    str(
                        cfg.params.get("products", {})
                        .get(application.product_code, {})
                        .get(
                            "spread",
                            DEFAULT_CONFIG.products[application.product_code].spreads,
                        )["C"]
                    )
                )
            )
            offer = Offer(
                application_id=application.id,
                version=1,
                kind="APPROVED" if body.outcome == "APPROVE" else "COUNTER",
                product_code=application.product_code,
                amount=body.amount,
                term_months=body.term_months,
                rate=rate,
                monthly_payment=None
                if application.product_code == "OVERDRAFT"
                else rub(annuity(body.amount, float(rate), body.term_months)),
                status="ACTIVE",
                expires_at=now + timedelta(days=get_settings().offer_valid_days),
            )
            session.add(offer)
            session.flush()
            application.current_offer_id = offer.id
            target = "OFFER_ISSUED"
            _event(
                session, application, user, "OFFER_ISSUED", {"offer_id": str(offer.id)}
            )
        elif body.outcome == "DECLINE":
            target = "DECLINED"
        elif body.outcome == "REQUEST_INFO":
            session.add(
                InfoRequest(
                    application_id=application.id,
                    source="UNDERWRITER",
                    items=[
                        {
                            "item_code": "UNDERWRITER_QUESTION",
                            "question": question,
                            "requires_value": False,
                        }
                        for question in body.info_questions
                    ],
                    due_at=now + timedelta(days=get_settings().info_due_days),
                )
            )
            target = "INFO_REQUESTED"
        else:
            target = "ENRICHMENT"
            session.add(
                Job(
                    application_id=application.id,
                    step="ENRICHMENT",
                    status="PENDING",
                    attempts=0,
                    run_after=now,
                )
            )
        if (
            body.outcome in {"APPROVE", "COUNTER", "DECLINE"}
            and auto
            and auto.recommendation
        ):
            recommended = auto.recommendation
            chosen = {
                "outcome": body.outcome,
                "amount": body.amount if body.outcome != "DECLINE" else None,
                "term_months": body.term_months if body.outcome != "DECLINE" else None,
            }
            if any(recommended.get(key) != value for key, value in chosen.items()):
                _event(
                    session,
                    application,
                    user,
                    "UNDERWRITER_OVERRIDE",
                    {"recommended": recommended, "chosen": chosen},
                )
        transition(
            session,
            application,
            target,
            actor_type="UNDERWRITER",
            actor_id=user.id,
            reason_code=decision.client_reason_code if target == "DECLINED" else None,
        )
        if body.outcome in {"APPROVE", "COUNTER", "DECLINE"}:
            objections.resolve(session, application, body.outcome)
        session.flush()
        result = to_bank(session, application, user)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
