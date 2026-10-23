"""Баллы по двенадцати настраиваемым признакам."""

import operator
import statistics as st
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .config import DecisionConfig
from .models import DecisionInputs, FactorLine, Grade

COMPARISONS = {
    "lt": operator.lt,
    "le": operator.le,
    "ge": operator.ge,
    "eq": operator.eq,
}


def rub(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def annuity(amount: int, rate: float, term: int) -> float:
    monthly_rate = rate / 1200
    if monthly_rate == 0:
        return amount / term
    return amount * monthly_rate / (1 - (1 + monthly_rate) ** -term)


def present_value(payment: float, rate: float, term: int) -> float:
    monthly_rate = rate / 1200
    if monthly_rate == 0:
        return payment * term
    return payment * (1 - (1 + monthly_rate) ** -term) / monthly_rate


def months_between(reg_date: date, as_of: date) -> int:
    return (as_of.year - reg_date.year) * 12 + as_of.month - reg_date.month


def number(value: float, precision: int = 0) -> str:
    return f"{value:,.{precision}f}".replace(",", " ").replace(".", ",")


def money(value: float) -> str:
    return f"{number(rub(value))} ₽"


def score(
    inputs: DecisionInputs,
    cfg: DecisionConfig,
) -> tuple[dict[str, int], int, Grade, float, list[FactorLine]]:
    company, bureau, tax, app = inputs.company, inputs.bureau, inputs.tax, inputs.app
    turnover = inputs.turnover
    avg = st.mean(turnover)
    rate = cfg.key_rate + cfg.products[app.product_code].spreads["C"]
    new_payment = (
        cfg.overdraft_payment_ratio * app.amount
        if app.product_code == "OVERDRAFT"
        else annuity(app.amount, rate, app.term_months)
    )
    age = months_between(company.reg_date, inputs.as_of)
    cv = st.pstdev(turnover) / avg
    trend = st.mean(turnover[cfg.trend_history_months :]) / st.mean(
        turnover[: cfg.trend_history_months]
    )
    zero = sum(1 for value in turnover if value < cfg.zero_month_ratio * avg)
    ptr = (bureau.monthly_payments_total + new_payment) / avg
    leverage = bureau.total_balance / (12 * avg)
    industry = cfg.industry.get(company.okved_main[:2], cfg.default_industry)
    mass = company.mass_director or company.mass_address
    obligations = tax.tax_debt + tax.enforcement_sum + tax.arbitration_defendant_sum
    values = {
        "business_age": age,
        "industry_risk": industry,
        "mass_registration": mass,
        "turnover_stability": cv,
        "turnover_trend": trend,
        "zero_months": zero,
        "payment_to_turnover": ptr,
        "debt_to_turnover": leverage,
        "delinquency_12m": bureau.max_dpd_12m,
        "credit_history_length": bureau.credit_history_months,
        "bureau_inquiries_30d": bureau.inquiries_30d,
        "payment_discipline": obligations,
    }
    display = {
        "business_age": f"{age} мес.",
        "industry_risk": {"low": "Низкий", "mid": "Средний", "high": "Высокий"}[
            industry
        ],
        "mass_registration": "Да" if mass else "Нет",
        "turnover_stability": number(cv, 2),
        "turnover_trend": number(trend, 2),
        "zero_months": str(zero),
        "payment_to_turnover": f"{number(ptr * 100, 1)}%",
        "debt_to_turnover": f"{number(leverage * 100, 1)}%",
        "delinquency_12m": f"{bureau.max_dpd_12m} дн.",
        "credit_history_length": f"{bureau.credit_history_months} мес.",
        "bureau_inquiries_30d": str(bureau.inquiries_30d),
        "payment_discipline": money(obligations),
    }
    points, factors = {}, []
    for code, spec in cfg.factors.items():
        earned = next(
            (
                band.points
                for band in spec.bands
                if COMPARISONS[band.comparison](values[code], band.threshold)
            ),
            spec.default_points,
        )
        points[code] = earned
        factors.append(
            FactorLine(
                code, spec.title, display[code], earned, spec.max_points, spec.rule
            )
        )
    total = sum(points.values())
    grade = next(
        (grade for minimum, grade in cfg.grade_bounds if total >= minimum), "D"
    )
    return points, total, grade, round(ptr * 100, 1), factors
