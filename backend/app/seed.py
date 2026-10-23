"""Idempotent demo data loader: python -m app.seed."""

import json
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, SessionLocal
from app.models import (
    AccountTurnover,
    Company,
    CompanyMember,
    DecisionConfig,
    Product,
    ReasonCatalog,
    RiskFlag,
    User,
)
from app.security import hash_password

# TODO(lead): replace PRODUCTS from decision_reference.py with B-02 DEFAULT_CONFIG.
PRODUCT_PARAMS = {
    "EXPRESS": {
        "min": 300_000,
        "max": 5_000_000,
        "tmin": 6,
        "tmax": 36,
        "k": 2,
        "auto": 3_000_000,
        "spread": {"A": 8, "B": 10, "C": 12},
    },
    "WORKING_CAPITAL": {
        "min": 500_000,
        "max": 15_000_000,
        "tmin": 3,
        "tmax": 24,
        "k": 3,
        "auto": 5_000_000,
        "spread": {"A": 7, "B": 9, "C": 11},
    },
    "OVERDRAFT": {
        "min": 100_000,
        "max": 5_000_000,
        "tmin": 12,
        "tmax": 12,
        "k": 0.4,
        "auto": 5_000_000,
        "spread": {"A": 10, "B": 12, "C": 14},
    },
}
PRODUCT_TEXT = {
    "EXPRESS": ("Экспресс-кредит", "На любые цели бизнеса"),
    "WORKING_CAPITAL": ("Оборотный кредит", "На пополнение оборотных средств"),
    "OVERDRAFT": ("Овердрафт", "На покрытие кассовых разрывов"),
}
DECISION_PARAMS = {
    "products": PRODUCT_PARAMS,
    "industry": {
        "52": "low",
        "62": "low",
        "69": "low",
        "56": "mid",
        "47": "mid",
        "43": "mid",
        "46": "mid",
        "33": "mid",
        "41": "high",
        "01": "high",
    },
    "okved_stop": ["92", "64.9"],
    "stop": {
        "max_dpd_12m": 60,
        "tax_debt": 50_000,
        "enforcement_sum": 100_000,
        "min_age_months": 6,
    },
    "validation": {"revenue_mismatch": 0.40},
    "grades": {"A": 75, "B": 60, "C": 45},
    "policy": {
        "free_payment_share": 0.30,
        "counter_round": 50_000,
        "overdraft_payment_share": 0.10,
    },
}

# code, category, text, action, visible, BKI category from codes.md.
REASON_ROWS = [
    (
        "SF_INACTIVE",
        "Данные о компании",
        "По данным реестра компания не действует",
        "Проверьте сведения о компании в ЕГРЮЛ/ЕГРИП",
        True,
        "несоответствие данных",
    ),
    (
        "SF_BANKRUPTCY",
        "Финансовое положение",
        "Есть сведения о процедуре банкротства",
        None,
        True,
        "банкротство",
    ),
    (
        "SF_AGE",
        "Срок ведения бизнеса",
        "Бизнесу меньше 6 месяцев",
        "Подайте заявку после {date}",
        True,
        "кредитная политика",
    ),
    (
        "SF_OVERDUE",
        "Кредитная история",
        "Есть просроченная задолженность по кредитам",
        "Погасите просрочку и подайте заявку повторно через 30 дней",
        True,
        "кредитная история",
    ),
    (
        "SF_TAX_DEBT",
        "Налоги и обязательства",
        "Есть задолженность перед бюджетом или по исполнительным листам",
        "Погасите задолженность и подайте заявку снова",
        True,
        "кредитная политика",
    ),
    (
        "SF_OKVED",
        "Условия продукта",
        "Вид деятельности не подходит для этого продукта",
        None,
        True,
        "кредитная политика",
    ),
    (
        "SF_ADDITIONAL",
        None,
        "(клиенту не показывается — используется ADDITIONAL_CHECKS)",
        None,
        False,
        "предупреждение мошенничества",
    ),
    (
        "ADDITIONAL_CHECKS",
        "Дополнительные проверки",
        "Заявка не прошла дополнительные проверки банка",
        None,
        True,
        None,
    ),
    (
        "LOW_SCORE",
        "Финансовые показатели",
        "Финансовые показатели бизнеса пока не позволяют одобрить заявку",
        "Попробуйте меньшую сумму или овердрафт",
        True,
        "кредитная политика",
    ),
    (
        "HIGH_LOAD",
        "Долговая нагрузка",
        "Ежемесячный платёж был бы слишком большим для текущих оборотов",
        "Рассмотрите овердрафт или подайте заявку позже",
        True,
        "долговая нагрузка",
    ),
    (
        "UNDERWRITER_DECLINE",
        None,
        "Заявку рассмотрел специалист банка и не смог её одобрить",
        None,
        True,
        None,
    ),
    (
        "CLIENT_REJECTED_OFFER",
        None,
        "Вы отказались от предложения банка",
        "Можно подать новую заявку",
        True,
        None,
    ),
    (
        "CLIENT_WITHDREW",
        None,
        "Вы отозвали заявку",
        "Можно подать новую заявку",
        True,
        None,
    ),
    (
        "EXPIRED_INFO",
        None,
        "Срок ответа на запрос банка истёк",
        "Подайте новую заявку",
        True,
        None,
    ),
    (
        "EXPIRED_OFFER",
        None,
        "Срок действия предложения истёк",
        "Подайте новую заявку",
        True,
        None,
    ),
]


def get_or_create[Model: Base](
    session: Session, model: type[Model], key: dict[str, object], **values: object
) -> Model:
    instance = session.scalar(select(model).filter_by(**key))
    if instance is None:
        instance = model(**key, **values)
        session.add(instance)
        session.flush()
    return instance


def seed(session: Session) -> None:
    settings = get_settings()
    data = json.loads((settings.contracts_dir / "personas.json").read_text("utf-8"))
    for persona in data["personas"]:
        company = get_or_create(
            session,
            Company,
            {"inn": persona["inn"]},
            **{
                field: persona[field]
                for field in ("ogrn", "kind", "name", "okved_main", "address")
            },
            reg_date=date.fromisoformat(persona["reg_date"]),
        )
        for person in persona["users"]:
            user = session.scalar(select(User).where(User.login == person["login"]))
            if user is None:
                user = get_or_create(
                    session,
                    User,
                    {"login": person["login"]},
                    full_name=person["full_name"],
                    role=person["role"],
                    password_hash=hash_password(settings.demo_password),
                )
            get_or_create(
                session,
                CompanyMember,
                {"user_id": user.id, "company_id": company.id},
                **{
                    field: person[field]
                    for field in ("position", "can_sign", "is_founder", "share_pct")
                },
            )
        for offset, amount in enumerate(persona["turnover"]):
            year, month = divmod(2025 * 12 + 9 + offset, 12)
            get_or_create(
                session,
                AccountTurnover,
                {"company_id": company.id, "month": f"{year}-{month + 1:02d}"},
                credit_turnover=amount,
            )
        get_or_create(session, RiskFlag, {"company_id": company.id}, **persona["risk"])

    for staff in data["staff"]:
        if session.scalar(select(User).where(User.login == staff["login"])) is None:
            get_or_create(
                session,
                User,
                {"login": staff["login"]},
                full_name=staff["full_name"],
                role=staff["role"],
                password_hash=hash_password(settings.demo_password),
            )
    for code, params in PRODUCT_PARAMS.items():
        name, description = PRODUCT_TEXT[code]
        get_or_create(
            session,
            Product,
            {"code": code},
            name=name,
            description=description,
            params=params,
        )
    get_or_create(
        session,
        DecisionConfig,
        {"version": 1},
        key_rate=Decimal("14.00"),
        key_rate_date=date(2026, 10, 23),
        params=DECISION_PARAMS,
        active=True,
    )
    for code, category, client_text, action, visible, bki_code in REASON_ROWS:
        get_or_create(
            session,
            ReasonCatalog,
            {"code": code},
            client_category=category,
            client_text=client_text,
            client_action=action,
            client_visible=visible,
            bki_reason_code=bki_code,
        )


def main() -> None:
    with SessionLocal.begin() as session:
        seed(session)


if __name__ == "__main__":
    main()
