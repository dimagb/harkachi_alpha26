"""Explicit bank projection using only persisted company and source data."""

from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.applications.serializers import to_client
from app.errors import ApiErrorException
from app.models import (
    AccountTurnover,
    Application,
    ApplicationEvent,
    Company,
    Decision,
    DecisionConfig,
    ExternalCheck,
    RiskFlag,
    User,
)
from app.schemas.api import (
    ApplicationBank,
    CompanyProfile,
    DecisionBank,
    EventBank,
    ExternalCheckBank,
    RiskFlags,
    TurnoverMonth,
)

ROUTE_LABELS = {
    "GRADE_C": "Пограничная оценка",
    "AMOUNT_ABOVE_AUTO": "Сумма выше порога автоматического решения",
    "NO_AUTO_CONSENT": "Нет согласия на автоматическое решение",
    "SOURCE_UNAVAILABLE": "Источник данных недоступен",
    "INFO_RESPONSE": "Клиент ответил на вопросы",
    "OBJECTION": "Клиент не согласен с решением",
}
ACTOR_LABELS = {
    "CLIENT": "Клиент",
    "GUARANTOR": "Поручитель",
    "UNDERWRITER": "Андеррайтер",
}


def get_application(session: Session, application_id: UUID, *, lock: bool = False):
    statement = select(Application).where(Application.id == application_id)
    if lock:
        statement = statement.with_for_update()
    application = session.scalar(statement)
    if application is None:
        raise ApiErrorException(404, "NOT_FOUND", "Заявка не найдена")
    return application


def _company(session: Session, application: Application, checks) -> CompanyProfile:
    company = session.get(Company, application.company_id)
    registry = next(
        (c for c in checks if c.source == "EGRUL" and c.status == "OK"), None
    )
    response = registry.response if registry else {}
    average = session.scalar(
        select(func.avg(AccountTurnover.credit_turnover)).where(
            AccountTurnover.company_id == company.id
        )
    )
    source = "ЕГРЮЛ" if company.kind == "OOO" else "ЕГРИП"
    note = f"Данные из {source} не получены"
    if registry is not None and registry.fetched_at is not None:
        day = registry.fetched_at.astimezone(ZoneInfo("Europe/Moscow"))
        note = f"Данные из {source} на {day:%d.%m.%Y}"
    return CompanyProfile(
        id=str(company.id),
        inn=company.inn,
        ogrn=company.ogrn,
        kind=company.kind,
        name=company.name,
        status=response.get("status", "ACTIVE"),
        reg_date=company.reg_date.isoformat(),
        okved_main=company.okved_main,
        address=company.address,
        director_full_name=response.get("director", {}).get("full_name", ""),
        founders=response.get("founders", []),
        avg_monthly_turnover=int(
            Decimal(average or 0).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        ),
        source_note=note,
    )


def _decisions(session: Session, application: Application) -> list[DecisionBank]:
    rows = session.execute(
        select(Decision, DecisionConfig.key_rate, User.full_name)
        .join(DecisionConfig, DecisionConfig.version == Decision.config_version)
        .outerjoin(User, User.id == Decision.made_by)
        .where(Decision.application_id == application.id)
        .order_by(Decision.created_at.desc(), Decision.id.desc())
    )
    fields = (
        "kind",
        "outcome",
        "client_reason_code",
        "route_reason",
        "grade",
        "score",
        "factors",
        "rules_fired",
        "internal_reasons",
        "policy",
        "recommendation",
        "what_if",
        "comment",
    )
    return [
        DecisionBank(
            id=str(decision.id),
            **{name: getattr(decision, name) for name in fields},
            config_version=str(decision.config_version),
            key_rate=key_rate,
            made_by=full_name,
            created_at=decision.created_at.isoformat(),
        )
        for decision, key_rate, full_name in rows
    ]


def _events(session: Session, application: Application) -> list[EventBank]:
    rows = session.execute(
        select(ApplicationEvent, User.full_name)
        .outerjoin(User, User.id == ApplicationEvent.actor_id)
        .where(ApplicationEvent.application_id == application.id)
        .order_by(ApplicationEvent.created_at, ApplicationEvent.id)
    )
    result = []
    for entry, full_name in rows:
        payload = entry.payload or {}
        actor = (
            "Система"
            if entry.actor_type == "SYSTEM"
            else f"{ACTOR_LABELS[entry.actor_type]}: {full_name or ''}"
        )
        result.append(
            EventBank(
                at=entry.created_at.isoformat(),
                event_type=entry.event_type,
                from_state=entry.from_state,
                to_state=entry.to_state,
                actor=actor,
                reason_code=entry.reason_code,
                note=payload.get("comment")
                or ROUTE_LABELS.get(payload.get("route_reason")),
            )
        )
    return result


def to_bank(session: Session, application: Application, user: User) -> ApplicationBank:
    base = to_client(session, application, user, for_bank=True)
    checks = list(
        session.scalars(
            select(ExternalCheck)
            .where(ExternalCheck.application_id == application.id)
            .order_by(ExternalCheck.created_at.desc(), ExternalCheck.id.desc())
        )
    )
    latest = {}
    for check in checks:
        latest.setdefault(check.source, check)
    risk = session.scalar(
        select(RiskFlag).where(RiskFlag.company_id == application.company_id)
    )
    months = list(
        session.scalars(
            select(AccountTurnover)
            .where(AccountTurnover.company_id == application.company_id)
            .order_by(AccountTurnover.month.desc())
            .limit(12)
        )
    )
    return ApplicationBank(
        **base.model_dump(),
        company=_company(session, application, checks),
        risk_flags=RiskFlags(
            aml_flag=risk.aml_flag if risk else False,
            fraud_flag=risk.fraud_flag if risk else False,
        ),
        turnover_12m=[
            TurnoverMonth(month=m.month, amount=m.credit_turnover)
            for m in reversed(months)
        ],
        decisions=_decisions(session, application),
        external_checks=[
            ExternalCheckBank(
                source=check.source,
                status=check.status,
                attempts=check.attempts,
                fetched_at=check.fetched_at.isoformat() if check.fetched_at else None,
                response=check.response,
            )
            for check in latest.values()
        ],
        events=_events(session, application),
    )
