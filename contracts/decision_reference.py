"""Эталонный расчёт модели решения (decision-model.md) — НЕ продуктовый код.

Назначение: оракул для golden-тестов и сверки реализации бэкенда; генератор contracts/personas.json.
Запуск:  python -X utf8 contracts/decision_reference.py            — печать исходов персонажей
         python -X utf8 contracts/decision_reference.py --write    — перезаписать contracts/personas.json
Правила: деньги — целые рубли; платёж округляется до рубля по ROUND_HALF_UP; сумма встречного — вниз до 50 000;
возраст бизнеса считается на дату подачи заявки (as_of); в эталоне as_of = 2026-10-23, КС = 14.00.
"""
import json
import statistics as st
import sys
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

AS_OF = date(2026, 10, 23)
KEY_RATE = 14.0
PRODUCTS = {
    "EXPRESS": dict(min=300_000, max=5_000_000, tmin=6, tmax=36, k=2.0, auto=3_000_000, spread={"A": 8, "B": 10, "C": 12}),
    "WORKING_CAPITAL": dict(min=500_000, max=15_000_000, tmin=3, tmax=24, k=3.0, auto=5_000_000, spread={"A": 7, "B": 9, "C": 11}),
    "OVERDRAFT": dict(min=100_000, max=5_000_000, tmin=12, tmax=12, k=0.4, auto=5_000_000, spread={"A": 10, "B": 12, "C": 14}),
}
INDUSTRY = {"52": "low", "62": "low", "69": "low", "56": "mid", "47": "mid", "43": "mid", "46": "mid", "33": "mid", "41": "high", "01": "high"}
OKVED_STOP = ("92", "64.9")


def rub(x):
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def annuity(amount, rate, n):
    r = rate / 1200
    return amount * r / (1 - (1 + r) ** -n)


def pv(payment, rate, n):
    r = rate / 1200
    return payment * (1 - (1 + r) ** -n) / r


def months_between(d):
    return (AS_OF.year - d.year) * 12 + AS_OF.month - d.month


def validation(p, app, answered=()):
    avg = st.mean(p["turnover"])
    if "REVENUE_CONFIRM" not in answered and abs(app["declared_revenue_year"] - 12 * avg) / (12 * avg) > 0.40:
        return "VAL_REVENUE_MISMATCH"
    if app["purpose"] == "OTHER" and not app.get("purpose_text") and "PURPOSE_DETAILS" not in answered:
        return "VAL_PURPOSE_UNCLEAR"
    return None


def stop_factor(p):
    b, f = p["bki"]["summary"], p["fns"]
    if p["status"] != "ACTIVE":
        return "SF_INACTIVE"
    if f["bankruptcy"]:
        return "SF_BANKRUPTCY"
    if months_between(date.fromisoformat(p["reg_date"])) < 6:
        return "SF_AGE"
    if b["current_overdue_total"] > 0 or b["max_dpd_12m"] > 60:
        return "SF_OVERDUE"
    if f["tax_debt"] > 50_000 or f["enforcement_sum"] > 100_000:
        return "SF_TAX_DEBT"
    if p["okved_main"].startswith(OKVED_STOP):
        return "SF_OKVED"
    if p["risk"]["aml_flag"] or p["risk"]["fraud_flag"]:
        return "SF_ADDITIONAL"
    return None


def score(p, app):
    t = p["turnover"]; avg = st.mean(t); b = p["bki"]["summary"]; f = p["fns"]
    prod = app["product"]
    srate = KEY_RATE + PRODUCTS[prod]["spread"]["C"]
    new_pay = 0.10 * app["amount"] if prod == "OVERDRAFT" else annuity(app["amount"], srate, app["term"])
    x = dict(age=months_between(date.fromisoformat(p["reg_date"])), cv=st.pstdev(t) / avg,
             trend=st.mean(t[9:]) / st.mean(t[:9]), zero=sum(1 for v in t if v < 0.1 * avg),
             ptr=(b["monthly_payments_total"] + new_pay) / avg, lev=b["total_balance"] / (12 * avg))
    pts = {
        "business_age": 0 if x["age"] < 12 else 5 if x["age"] <= 36 else 10,
        "industry_risk": {"low": 5, "mid": 3, "high": 0}[INDUSTRY.get(p["okved_main"][:2], "mid")],
        "mass_registration": 0 if (f["mass_director"] or f["mass_address"]) else 5,
        "turnover_stability": 10 if x["cv"] < .3 else 5 if x["cv"] <= .6 else 0,
        "turnover_trend": 10 if x["trend"] >= .95 else 5 if x["trend"] >= .8 else 0,
        "zero_months": 10 if x["zero"] == 0 else 5 if x["zero"] == 1 else 0,
        "payment_to_turnover": 15 if x["ptr"] < .1 else 10 if x["ptr"] < .2 else 4 if x["ptr"] < .3 else 0,
        "debt_to_turnover": 10 if x["lev"] < .25 else 5 if x["lev"] <= .5 else 0,
        "delinquency_12m": 10 if b["max_dpd_12m"] == 0 else 5 if b["max_dpd_12m"] <= 30 else 0,
        "credit_history_length": 5 if b["credit_history_months"] >= 24 else 3 if b["credit_history_months"] >= 1 else 2,
        "bureau_inquiries_30d": 5 if b["inquiries_30d"] <= 1 else 2 if b["inquiries_30d"] <= 3 else 0,
        "payment_discipline": 5 if f["tax_debt"] + f["enforcement_sum"] + f["arbitration_defendant_sum"] == 0 else 2,
    }
    s = sum(pts.values())
    grade = "A" if s >= 75 else "B" if s >= 60 else "C" if s >= 45 else "D"
    return pts, s, grade, x


def policy(p, app, grade):
    """Итог политики: dict(outcome, amount, term, rate, payment) или dict(outcome='DECLINE', reason)."""
    P = PRODUCTS[app["product"]]; avg = st.mean(p["turnover"])
    rate = KEY_RATE + P["spread"][grade]  # скидки за поручительство в MVP нет (decision-model §5)
    cap = P["k"] * avg
    if app["product"] == "OVERDRAFT":
        limit = min(app["amount"], cap)
        if limit < P["min"]:
            return dict(outcome="DECLINE", reason="HIGH_LOAD")
        out = "APPROVE" if limit == app["amount"] else "COUNTER"
        return dict(outcome=out, amount=int(limit // 50_000 * 50_000) if out == "COUNTER" else app["amount"], term=12, rate=rate, payment=None)
    free = 0.30 * avg - p["bki"]["summary"]["monthly_payments_total"]
    if free <= 0:
        return dict(outcome="DECLINE", reason="HIGH_LOAD")
    a, t = app["amount"], app["term"]
    if a <= cap and annuity(a, rate, t) <= free:
        return dict(outcome="APPROVE", amount=a, term=t, rate=rate, payment=rub(annuity(a, rate, t)))
    for tt in range(t + 1, P["tmax"] + 1):
        if a <= cap and annuity(a, rate, tt) <= free:
            return dict(outcome="COUNTER", amount=a, term=tt, rate=rate, payment=rub(annuity(a, rate, tt)))
    m = int(min(cap, pv(free, rate, P["tmax"])) // 50_000 * 50_000)
    if m >= P["min"]:
        return dict(outcome="COUNTER", amount=m, term=P["tmax"], rate=rate, payment=rub(annuity(m, rate, P["tmax"])))
    return dict(outcome="DECLINE", reason="HIGH_LOAD")


def decide(p, app, consents, answered=()):
    """Полный путь после подачи: возвращает ожидаемый итог (формат demo.expected)."""
    v = validation(p, app, answered)
    if v:
        return dict(state="INFO_REQUESTED", validation_rule=v)
    is_ip = p["kind"] == "IP"
    no_auto = is_ip and not consents.get("auto_decision", False)
    sf = stop_factor(p)
    if sf:
        res = dict(outcome="DECLINE", reason_code=sf, client_reason_code="ADDITIONAL_CHECKS" if sf == "SF_ADDITIONAL" else sf, grade=None, score=None)
    else:
        pts, s, g, x = score(p, app)
        base = dict(grade=g, score=s, points=pts, ptr_pct=round(x["ptr"] * 100, 1))
        if g == "D":
            res = dict(outcome="DECLINE", reason_code="LOW_SCORE", client_reason_code="LOW_SCORE", **base)
        else:
            pol = policy(p, app, g)
            if pol["outcome"] == "DECLINE":
                res = dict(outcome="DECLINE", reason_code=pol["reason"], client_reason_code=pol["reason"], **base)
            else:
                res = dict(outcome=pol["outcome"], offer=dict(amount=pol["amount"], term_months=pol["term"], rate=pol["rate"], monthly_payment=pol["payment"]), **base)
    route = None
    if no_auto:
        route = "NO_AUTO_CONSENT"
    elif res.get("grade") == "C":
        route = "GRADE_C"
    elif res["outcome"] != "DECLINE" and app["amount"] > PRODUCTS[app["product"]]["auto"]:
        route = "AMOUNT_ABOVE_AUTO"
    if route:
        return dict(state="MANUAL_REVIEW", route_reason=route, recommendation=res)
    return dict(state="OFFER_ISSUED" if res["outcome"] != "DECLINE" else "DECLINED", **res)


# ---------------- Персонажи ----------------
def inn10(b):
    w = [2, 4, 10, 3, 5, 9, 4, 6, 8]; return b + str(sum(int(c) * k for c, k in zip(b, w)) % 11 % 10)


def inn12(b):
    d = [int(c) for c in b]
    c1 = sum(x * k for x, k in zip(d, [7, 2, 4, 10, 3, 5, 9, 4, 6, 8])) % 11 % 10; d.append(c1)
    c2 = sum(x * k for x, k in zip(d, [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8])) % 11 % 10
    return b + str(c1) + str(c2)


def turn(avg, cv, trend=1.0):
    d = avg * cv
    return [int((avg + d if i % 2 else avg - d) * (trend if i >= 9 else 1)) for i in range(12)]


def bki(pay=0, bal=0, overdue=0, dpd=0, hist=36, inq=0):
    loans = [] if bal == 0 else [dict(type="CREDIT", balance=bal, monthly_payment=pay, current_overdue=overdue, max_dpd_12m=dpd)]
    return dict(loans=loans, summary=dict(monthly_payments_total=pay, total_balance=bal, current_overdue_total=overdue,
                                          max_dpd_12m=dpd, credit_history_months=hist, inquiries_30d=inq))


def fns(tax=0, enf=0, arb=0, bank=False, md=False, ma=False):
    return dict(tax_debt=tax, enforcement_sum=enf, arbitration_defendant_sum=arb, bankruptcy=bank,
                mass_director=md, mass_address=ma, msp_registry=dict(included=True, category="MICRO"))


def user(login, full_name, pos, sign=True, founder=True, share=100):
    return dict(login=login, full_name=full_name, role="CLIENT", position=pos, can_sign=sign, is_founder=founder, share_pct=share)


def company(code, kind, inn, ogrn, name, okved, reg, address, director, turnover, b, f, users, demo, aml=False, fraud=False, note=None):
    founders = [dict(full_name=director, share_pct=100)] if kind == "OOO" else []
    return dict(code=code, kind=kind, inn=inn, ogrn=ogrn, name=name, okved_main=okved, reg_date=reg, status="ACTIVE",
                address=address, director=dict(full_name=director), founders=founders,
                turnover=turnover, bki=b, fns=f, risk=dict(aml_flag=aml, fraud_flag=fraud, note=note), users=users, demo=demo)


PERSONAS = [
    company("ip_good", "IP", inn12("7701123456"), "322774600012345", "ИП Смирнова Анна Викторовна", "56.10", "2022-09-01",
            "г. Москва, ул. Покровка, д. 12", "Смирнова Анна Викторовна", turn(1_200_000, .15), bki(hist=40), fns(),
            [user("ip_good", "Смирнова Анна Викторовна", "Индивидуальный предприниматель")],
            dict(app=dict(product="EXPRESS", amount=1_500_000, term=24, purpose="WORKING_CAPITAL", declared_revenue_year=14_000_000),
                 consents=dict(pdn=True, bki=True, auto_decision=True))),
    company("ooo_load", "OOO", inn10("770212345"), "1237700012345", "ООО «Северный склад»", "52.10", "2023-03-01",
            "г. Москва, Складской пр., д. 4", "Петров Илья Игоревич", turn(2_000_000, .35), bki(pay=450_000, bal=7_000_000, hist=30, inq=3), fns(),
            [user("ooo_load", "Петров Илья Игоревич", "Генеральный директор"),
             user("ooo_load_accountant", "Белова Ольга Сергеевна", "Главный бухгалтер", sign=False, founder=False, share=0)],
            dict(app=dict(product="WORKING_CAPITAL", amount=4_000_000, term=12, purpose="WORKING_CAPITAL", declared_revenue_year=24_000_000),
                 consents=dict(pdn=True, bki=True, auto_decision=False))),
    company("ooo_gap", "OOO", inn10("770312345"), "1247700023456", "ООО «Ремонт-Сервис»", "43.39", "2024-09-01",
            "г. Москва, ул. Мастеровая, д. 7", "Гусев Артём Павлович", turn(1_500_000, .2), bki(hist=12, inq=1), fns(),
            [user("ooo_gap", "Гусев Артём Павлович", "Генеральный директор")],
            dict(app=dict(product="EXPRESS", amount=1_000_000, term=24, purpose="EQUIPMENT", declared_revenue_year=48_000_000),
                 consents=dict(pdn=True, bki=True, auto_decision=False),
                 info_response=[dict(item_code="REVENUE_CONFIRM", value=48_000_000,
                                     comment="Часть выручки поступает на расчётный счёт в другом банке")])),
    company("ip_bad", "IP", inn12("7704123456"), "321774600054321", "ИП Козлов Дмитрий Сергеевич", "47.71", "2021-04-01",
            "г. Москва, ул. Торговая, д. 3", "Козлов Дмитрий Сергеевич", turn(800_000, .3), bki(pay=60_000, bal=900_000, overdue=35_000, dpd=45, hist=50, inq=4), fns(),
            [user("ip_bad", "Козлов Дмитрий Сергеевич", "Индивидуальный предприниматель")],
            dict(app=dict(product="EXPRESS", amount=700_000, term=12, purpose="WORKING_CAPITAL", declared_revenue_year=9_500_000),
                 consents=dict(pdn=True, bki=True, auto_decision=True))),
    company("ooo_border", "OOO", inn10("770512345"), "1257700034567", "ООО «ТехноМонтаж»", "43.21", "2025-08-01",
            "г. Москва, Электродный пр., д. 9", "Захаров Роман Олегович", turn(1_000_000, .5, .7), bki(pay=150_000, bal=7_000_000, hist=14, inq=2), fns(tax=20_000),
            [user("ooo_border", "Захаров Роман Олегович", "Генеральный директор")],
            dict(app=dict(product="EXPRESS", amount=1_000_000, term=24, purpose="WORKING_CAPITAL", declared_revenue_year=12_000_000),
                 consents=dict(pdn=True, bki=True, auto_decision=False))),
    company("ooo_aml", "OOO", inn10("770612345"), "1227700045678", "ООО «Альфа-Трейд»", "46.90", "2022-01-01",
            "г. Москва, ул. Оптовая, д. 21", "Сорокин Виктор Андреевич", turn(3_000_000, .2), bki(), fns(),
            [user("ooo_aml", "Сорокин Виктор Андреевич", "Генеральный директор")],
            dict(app=dict(product="EXPRESS", amount=1_000_000, term=12, purpose="WORKING_CAPITAL", declared_revenue_year=36_000_000),
                 consents=dict(pdn=True, bki=True, auto_decision=False)), aml=True, note="Синтетический флаг ПОД/ФТ для теста"),
]


def run():
    for p in PERSONAS:
        d = p["demo"]
        first = decide(p, d["app"], d["consents"])
        if first["state"] == "INFO_REQUESTED":
            answered = tuple(a["item_code"] for a in d.get("info_response", []))
            d["expected"] = dict(first_state="INFO_REQUESTED", validation_rule=first["validation_rule"],
                                 after_info=decide(p, d["app"], d["consents"], answered))
        else:
            d["expected"] = first
        print(p["code"], json.dumps(d["expected"], ensure_ascii=False))


if __name__ == "__main__":
    run()
    if "--write" in sys.argv:
        meta = dict(as_of=AS_OF.isoformat(), key_rate=KEY_RATE, turnover_months="2025-10…2026-09 (YYYY-MM)",
                    note="Единственный источник данных персонажей: сиды БД и фикстуры external-mocks генерируются отсюда. "
                         "demo.expected — golden-тест (decision_reference.py). Пароль всех учёток — DEMO_PASSWORD из .env.example.")
        out = dict(_meta=meta, staff=[dict(login="underwriter", full_name="Орлова Мария Андреевна", role="UNDERWRITER")], personas=PERSONAS)
        Path(__file__).with_name("personas.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
