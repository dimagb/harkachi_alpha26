"""Проверка → стоп-факторы → скоринг → политика → маршрутизация."""

import statistics as st
from dataclasses import replace
from datetime import date

from .config import DecisionConfig
from .models import DecisionInputs, DecisionResult, RuleFired
from .policy import apply_policy, max_at_term
from .scoring import money, months_between, number, score


def _validation(inputs: DecisionInputs, cfg: DecisionConfig) -> RuleFired | None:
    avg = st.mean(inputs.turnover)
    annual = 12 * avg
    mismatch = abs(inputs.app.declared_revenue_year - annual) / annual
    if (
        "REVENUE_CONFIRM" not in inputs.answered_items
        and mismatch > cfg.revenue_mismatch_ratio
    ):
        return RuleFired(
            "VAL_REVENUE_MISMATCH",
            "Нужно подтвердить выручку",
            f"Заявлено {money(inputs.app.declared_revenue_year)}; "
            f"оборот за год {money(annual)}; разница {number(mismatch * 100, 1)}%",
            f"> {number(cfg.revenue_mismatch_ratio * 100)}%",
            "INFO",
        )
    if (
        inputs.app.purpose == "OTHER"
        and not inputs.app.purpose_text
        and "PURPOSE_DETAILS" not in inputs.answered_items
    ):
        return RuleFired(
            "VAL_PURPOSE_UNCLEAR",
            "Нужно описать цель",
            "Другое, описание отсутствует",
            "Непустое описание цели",
            "INFO",
        )
    return None


def _stops(inputs: DecisionInputs, cfg: DecisionConfig) -> list[RuleFired]:
    company, bureau, tax, risk = inputs.company, inputs.bureau, inputs.tax, inputs.risk
    age = months_between(company.reg_date, inputs.as_of)
    checks = [
        (
            company.status != "ACTIVE",
            "SF_INACTIVE",
            "Компания не действует",
            company.status,
            "ACTIVE",
        ),
        (
            tax.bankruptcy,
            "SF_BANKRUPTCY",
            "Процедура банкротства",
            "Есть сведения о банкротстве",
            "Нет банкротства",
        ),
        (
            age < cfg.stop_min_age,
            "SF_AGE",
            "Недостаточный срок бизнеса",
            f"{age} мес.",
            f"≥ {cfg.stop_min_age} мес.",
        ),
        (
            bureau.current_overdue_total > 0 or bureau.max_dpd_12m > cfg.stop_max_dpd,
            "SF_OVERDUE",
            "Просроченная задолженность",
            f"Просрочка {money(bureau.current_overdue_total)}; "
            f"максимум {bureau.max_dpd_12m} дн.",
            f"Просрочка = 0 ₽; максимум ≤ {cfg.stop_max_dpd} дн.",
        ),
        (
            tax.tax_debt > cfg.stop_tax_debt
            or tax.enforcement_sum > cfg.stop_enforcement,
            "SF_TAX_DEBT",
            "Налоги и обязательства",
            f"Налоговый долг {money(tax.tax_debt)}; "
            f"исполнительные производства {money(tax.enforcement_sum)}",
            f"Налоговый долг ≤ {money(cfg.stop_tax_debt)}; "
            f"исполнительные производства ≤ {money(cfg.stop_enforcement)}",
        ),
        (
            company.okved_main.startswith(cfg.okved_stop),
            "SF_OKVED",
            "Вид деятельности не подходит",
            company.okved_main,
            f"ОКВЭД вне стоп-листа: {', '.join(cfg.okved_stop)}",
        ),
        (
            risk.aml_flag or risk.fraud_flag,
            "SF_ADDITIONAL",
            "Дополнительные проверки",
            f"ПОД/ФТ: {'да' if risk.aml_flag else 'нет'}; "
            f"антифрод: {'да' if risk.fraud_flag else 'нет'}",
            "Нет флагов ПОД/ФТ и антифрода",
        ),
    ]
    return [
        RuleFired(code, title, value, threshold, "STOP")
        for fired, code, title, value, threshold in checks
        if fired
    ]


def eligible_date(reg_date: date, cfg: DecisionConfig) -> date:
    """Первый день месяца, в котором бизнес проходит SF_AGE."""
    month_index = reg_date.year * 12 + reg_date.month - 1 + cfg.stop_min_age
    year, month = month_index // 12, month_index % 12 + 1
    return date(year, month, 1)


def _stop_action(code: str, inputs: DecisionInputs, cfg: DecisionConfig) -> str:
    eligible = eligible_date(inputs.company.reg_date, cfg)
    return {
        "SF_INACTIVE": "Проверьте сведения в ЕГРЮЛ/ЕГРИП.",
        "SF_BANKRUPTCY": "Есть сведения о процедуре банкротства.",
        "SF_AGE": f"Подайте заявку с {eligible:%d.%m.%Y}",
        "SF_OVERDUE": "Погасите просроченную задолженность; повторная заявка через "
        f"{cfg.retry_overdue_days} дней.",
        "SF_TAX_DEBT": "Погасите задолженность перед бюджетом или по исполнительным "
        "листам и подайте снова.",
        "SF_OKVED": "Вид деятельности не подходит для этого продукта.",
        "SF_ADDITIONAL": "Заявка не прошла дополнительные проверки банка.",
    }[code]


def _route(
    result: DecisionResult,
    inputs: DecisionInputs,
    cfg: DecisionConfig,
) -> DecisionResult:
    route = None
    if inputs.company.kind == "IP" and not inputs.auto_decision_consent:
        route = RuleFired(
            "NO_AUTO_CONSENT",
            "Нет согласия на автоматическое решение",
            "Согласие ИП отсутствует",
            "Согласие ИП получено",
            "ROUTE",
        )
    elif result.grade == "C":
        bounds = dict((grade, minimum) for minimum, grade in cfg.grade_bounds)
        route = RuleFired(
            "GRADE_C",
            "Пограничная оценка",
            f"Оценка C; баллы {result.score}",
            f"C: от {bounds['C']} до {bounds['B'] - 1} баллов",
            "ROUTE",
        )
    elif (
        result.outcome != "DECLINE"
        and inputs.app.amount > cfg.products[inputs.app.product_code].auto_limit
    ):
        route = RuleFired(
            "AMOUNT_ABOVE_AUTO",
            "Сумма выше порога автоматического решения",
            money(inputs.app.amount),
            f"≤ {money(cfg.products[inputs.app.product_code].auto_limit)}",
            "ROUTE",
        )
    if route is None:
        return result
    return replace(
        result,
        state="MANUAL_REVIEW",
        route_reason=route.code,
        recommendation=result._outcome_expected(),
        rules_fired=[*result.rules_fired, route],
    )


def decide(inputs: DecisionInputs, cfg: DecisionConfig) -> DecisionResult:
    validation = _validation(inputs, cfg)
    if validation is not None:
        return DecisionResult(
            state="INFO_REQUESTED",
            validation_rule=validation.code,
            rules_fired=[validation],
        )
    stops = _stops(inputs, cfg)
    if stops:
        reason = stops[0].code
        result = DecisionResult(
            state="DECLINED",
            outcome="DECLINE",
            reason_code=reason,
            client_reason_code="ADDITIONAL_CHECKS"
            if reason == "SF_ADDITIONAL"
            else reason,
            rules_fired=stops,
            what_if=[_stop_action(reason, inputs, cfg)],
        )
        return _route(result, inputs, cfg)
    points, total, grade, ptr_pct, factors = score(inputs, cfg)
    if grade == "D":
        result = DecisionResult(
            state="DECLINED",
            outcome="DECLINE",
            reason_code="LOW_SCORE",
            client_reason_code="LOW_SCORE",
            grade=grade,
            score=total,
            points=points,
            ptr_pct=ptr_pct,
            factors=factors,
        )
    else:
        outcome, offer, policy, rules = apply_policy(inputs, cfg, grade)
        reason = "HIGH_LOAD" if outcome == "DECLINE" else None
        what_if = []
        if outcome == "COUNTER" or reason == "HIGH_LOAD":
            maximum = max_at_term(inputs, cfg, policy.rate, inputs.app.term_months)
            what_if.append(
                "Рассмотрите овердрафт или подайте заявку позже"
                if maximum < cfg.products[inputs.app.product_code].min_amount
                else f"Одобрение при сумме ≤ {money(maximum)} "
                f"на {inputs.app.term_months} мес."
            )
        result = DecisionResult(
            state="DECLINED" if outcome == "DECLINE" else "OFFER_ISSUED",
            outcome=outcome,
            reason_code=reason,
            client_reason_code=reason,
            grade=grade,
            score=total,
            points=points,
            ptr_pct=ptr_pct,
            offer=offer,
            factors=factors,
            rules_fired=rules,
            policy=policy,
            what_if=what_if,
        )
    if grade in ("C", "D"):
        deficient = sorted(factors, key=lambda f: f.max_points - f.points, reverse=True)
        result = replace(
            result,
            what_if=[
                *result.what_if,
                *[
                    f"Оценка выше при: {factor.title}"
                    for factor in deficient[: cfg.what_if_factor_count]
                ],
            ],
        )
    return _route(result, inputs, cfg)
