"""Build immutable decision inputs from the stored source responses."""

from datetime import date
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.decision import DecisionInputs
from app.decision.models import (
    AppParams,
    BureauSummary,
    CompanyFacts,
    RiskFlags,
    TaxCheck,
)
from app.models import (
    AccountTurnover,
    Application,
    ApplicationEvent,
    Consent,
    ExternalCheck,
    InfoRequest,
    RiskFlag,
)


def app_params(application: Application) -> AppParams:
    return AppParams(
        **{
            key: getattr(application, key)
            for key in (
                "product_code",
                "amount",
                "term_months",
                "purpose",
                "purpose_text",
                "declared_revenue_year",
            )
        }
    )


def turnover(session: Session, application: Application) -> tuple[int, ...]:
    amounts = tuple(
        session.scalars(
            select(AccountTurnover.credit_turnover)
            .where(AccountTurnover.company_id == application.company_id)
            .order_by(AccountTurnover.month.desc())
            .limit(12)
        )
    )
    if not amounts:
        raise ValueError("Нет данных об оборотах компании за последние 12 месяцев")
    return amounts[::-1]


def answered_items(session: Session, application: Application) -> frozenset[str]:
    requests = session.scalars(
        select(InfoRequest).where(
            InfoRequest.application_id == application.id,
            InfoRequest.source == "SYSTEM",
            InfoRequest.responded_at.is_not(None),
        )
    )
    return frozenset(
        item["item_code"] for request in requests for item in (request.response or [])
    )


def current_checks(application_id: UUID) -> Select[tuple[ExternalCheck]]:
    started_at = (
        select(func.max(ApplicationEvent.created_at))
        .where(
            ApplicationEvent.application_id == application_id,
            ApplicationEvent.event_type == "STATE_CHANGED",
            ApplicationEvent.to_state == "ENRICHMENT",
        )
        .scalar_subquery()
    )
    return select(ExternalCheck).where(
        ExternalCheck.application_id == application_id,
        ExternalCheck.created_at > started_at,
    )


def source_responses(
    session: Session, application: Application
) -> dict[str, dict[str, object] | None]:
    checks = session.scalars(
        current_checks(application.id).order_by(ExternalCheck.created_at)
    )
    responses = {"EGRUL": None, "BKI": None, "FNS": None}
    for check in checks:
        responses[check.source] = check.response if check.status == "OK" else None
    return responses


def build_inputs(
    session: Session, application: Application, as_of: date
) -> DecisionInputs:
    responses = source_responses(session, application)
    registry, bki, fns = (responses[source] for source in ("EGRUL", "BKI", "FNS"))
    if registry is None or bki is None or fns is None:
        raise ValueError("Не все источники доступны для оценки")
    risk = session.scalar(
        select(RiskFlag).where(RiskFlag.company_id == application.company_id)
    )
    consent = session.scalar(
        select(Consent.granted)
        .where(
            Consent.application_id == application.id, Consent.type == "AUTO_DECISION"
        )
        .order_by(Consent.created_at.desc())
        .limit(1)
    )
    return DecisionInputs(
        company=CompanyFacts(
            kind=registry["kind"],
            status=registry["status"],
            reg_date=date.fromisoformat(registry["reg_date"]),
            okved_main=registry["okved_main"],
            mass_director=fns["mass_director"],
            mass_address=fns["mass_address"],
        ),
        bureau=BureauSummary(**bki["summary"]),
        tax=TaxCheck(
            **{
                key: fns[key]
                for key in (
                    "tax_debt",
                    "enforcement_sum",
                    "arbitration_defendant_sum",
                    "bankruptcy",
                )
            }
        ),
        risk=RiskFlags(
            aml_flag=risk.aml_flag if risk else False,
            fraud_flag=risk.fraud_flag if risk else False,
        ),
        app=app_params(application),
        turnover=turnover(session, application),
        auto_decision_consent=bool(consent),
        answered_items=answered_items(session, application),
        as_of=as_of,
    )
