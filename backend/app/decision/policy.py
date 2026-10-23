"""Политика продукта и расчёт встречного предложения без пересчёта оценки."""

import statistics as st

from .config import DecisionConfig
from .models import DecisionInputs, Grade, Offer, Outcome, PolicyCalc, RuleFired
from .scoring import annuity, money, number, present_value, rub


def floor_amount(value: float, cfg: DecisionConfig) -> int:
    return int(value // cfg.counter_step * cfg.counter_step)


def max_at_term(
    inputs: DecisionInputs,
    cfg: DecisionConfig,
    rate: float,
    term: int,
) -> int:
    product = cfg.products[inputs.app.product_code]
    avg = st.mean(inputs.turnover)
    cap = product.k * avg
    if inputs.app.product_code == "OVERDRAFT":
        maximum = min(cap, product.max_amount)
    else:
        free = cfg.ptr_limit * avg - inputs.bureau.monthly_payments_total
        maximum = min(cap, present_value(max(0, free), rate, term), product.max_amount)
    return floor_amount(maximum, cfg)


def apply_policy(
    inputs: DecisionInputs,
    cfg: DecisionConfig,
    grade: Grade,
) -> tuple[Outcome, Offer | None, PolicyCalc, list[RuleFired]]:
    app = inputs.app
    product = cfg.products[app.product_code]
    avg = st.mean(inputs.turnover)
    rate = cfg.key_rate + product.spreads[grade]
    cap = product.k * avg
    existing = inputs.bureau.monthly_payments_total
    free = cfg.ptr_limit * avg - existing
    overdraft = app.product_code == "OVERDRAFT"
    requested_payment = (
        None if overdraft else annuity(app.amount, rate, app.term_months)
    )
    max_amount = max_at_term(inputs, cfg, rate, product.max_term)
    steps = [
        f"Ставка: {number(cfg.key_rate, 2)}% + "
        f"{number(product.spreads[grade], 2)} п.п. = {number(rate, 2)}%.",
        f"Лимит по оборотам: {number(product.k, 2)} × {money(avg)} = {money(cap)}.",
    ]
    rules = []
    if app.amount > cap:
        rules.append(
            RuleFired(
                "HIGH_LOAD",
                "Превышен лимит по оборотам",
                money(app.amount),
                f"≤ {money(cap)}",
                "POLICY",
            )
        )
    if overdraft:
        limit = min(app.amount, cap)
        steps.append(
            f"Лимит овердрафта: min({money(app.amount)}, {money(cap)}) "
            f"= {money(limit)}; нагрузка не проверяется."
        )
        if limit < product.min_amount:
            outcome, offer = "DECLINE", None
            rules.append(
                RuleFired(
                    "HIGH_LOAD",
                    "Лимит ниже минимума продукта",
                    money(limit),
                    f"≥ {money(product.min_amount)}",
                    "POLICY",
                )
            )
            steps.append(f"Отказ: лимит ниже {money(product.min_amount)}.")
        else:
            outcome = "APPROVE" if limit == app.amount else "COUNTER"
            amount = app.amount if outcome == "APPROVE" else floor_amount(limit, cfg)
            offer = Offer(amount, product.max_term, rate, None)
            steps.append(
                f"{'Одобрение' if outcome == 'APPROVE' else 'Встречное'}: "
                f"{money(amount)} на {product.max_term} мес."
            )
    else:
        steps.append(
            f"Свободный платёж: {number(cfg.ptr_limit * 100)}% × "
            f"{money(avg)} − {money(existing)} = {money(free)}."
        )
        steps.append(f"Платёж на {app.term_months} мес.: {money(requested_payment)}.")
        if free <= 0 or requested_payment > free:
            rules.append(
                RuleFired(
                    "HIGH_LOAD",
                    "Превышена допустимая нагрузка",
                    f"Платёж {money(requested_payment)}; свободно {money(free)}",
                    f"PTR ≤ {number(cfg.ptr_limit * 100)}%",
                    "POLICY",
                )
            )
        outcome, offer = _credit_offer(inputs, cfg, rate, cap, free, steps)
    calc = PolicyCalc(
        rate=rate,
        avg_turnover=rub(avg),
        existing_payments=existing,
        free_payment=rub(free),
        cap_by_turnover=rub(cap),
        max_amount=max_amount,
        requested_payment=None if overdraft else rub(requested_payment),
        ptr_requested=None if overdraft else (existing + requested_payment) / avg,
        steps=steps,
    )
    return outcome, offer, calc, rules


def _credit_offer(
    inputs: DecisionInputs,
    cfg: DecisionConfig,
    rate: float,
    cap: float,
    free: float,
    steps: list[str],
) -> tuple[Outcome, Offer | None]:
    app = inputs.app
    product = cfg.products[app.product_code]
    if free <= 0:
        steps.append("Отказ: свободный платёж ≤ 0 ₽.")
        return "DECLINE", None
    if app.amount <= cap and annuity(app.amount, rate, app.term_months) <= free:
        steps.append("Одобрение: сумма и платёж укладываются в ограничения.")
        return "APPROVE", Offer(
            app.amount,
            app.term_months,
            rate,
            rub(annuity(app.amount, rate, app.term_months)),
        )
    for term in range(app.term_months + 1, product.max_term + 1):
        payment = annuity(app.amount, rate, term)
        steps.append(
            f"Проверка срока {term} мес.: платёж {money(payment)}, "
            f"предел {money(free)}; сумма {money(app.amount)}, "
            f"лимит {money(cap)}."
        )
        if app.amount <= cap and payment <= free:
            steps.append(f"Встречное: та же сумма на {term} мес.")
            return "COUNTER", Offer(app.amount, term, rate, rub(payment))
    affordable = present_value(free, rate, product.max_term)
    amount = floor_amount(min(cap, affordable), cfg)
    steps.append(
        f"Сумма на {product.max_term} мес.: min({money(cap)}, {money(affordable)}) "
        f"с округлением вниз до {money(cfg.counter_step)} = {money(amount)}."
    )
    if amount >= product.min_amount:
        steps.append(f"Встречное: {money(amount)} на {product.max_term} мес.")
        return "COUNTER", Offer(
            amount,
            product.max_term,
            rate,
            rub(annuity(amount, rate, product.max_term)),
        )
    steps.append(f"Отказ: сумма ниже минимума {money(product.min_amount)}.")
    return "DECLINE", None
