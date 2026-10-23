"""Версионируемые параметры модели; все пороги и баллы собраны здесь."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from .models import Grade


@dataclass(frozen=True)
class ProductConfig:
    min_amount: int
    max_amount: int
    min_term: int
    max_term: int
    k: float
    auto_limit: int
    spreads: Mapping[str, int]


@dataclass(frozen=True)
class ScoreBand:
    comparison: Literal["lt", "le", "ge", "eq"]
    threshold: float | str
    points: int


@dataclass(frozen=True)
class FactorConfig:
    title: str
    rule: str
    max_points: int
    bands: tuple[ScoreBand, ...]
    default_points: int


def _products() -> Mapping[str, ProductConfig]:
    return MappingProxyType(
        {
            "EXPRESS": ProductConfig(
                300_000,
                5_000_000,
                6,
                36,
                2.0,
                3_000_000,
                MappingProxyType({"A": 8, "B": 10, "C": 12}),
            ),
            "WORKING_CAPITAL": ProductConfig(
                500_000,
                15_000_000,
                3,
                24,
                3.0,
                5_000_000,
                MappingProxyType({"A": 7, "B": 9, "C": 11}),
            ),
            "OVERDRAFT": ProductConfig(
                100_000,
                5_000_000,
                12,
                12,
                0.4,
                5_000_000,
                MappingProxyType({"A": 10, "B": 12, "C": 14}),
            ),
        }
    )


def _factors() -> Mapping[str, FactorConfig]:
    return MappingProxyType(
        {
            "business_age": FactorConfig(
                "Срок бизнеса",
                "<12 мес. — 0; 12–36 — 5; >36 — 10 (10)",
                10,
                (
                    ScoreBand("lt", 12, 0),
                    ScoreBand("le", 36, 5),
                ),
                10,
            ),
            "industry_risk": FactorConfig(
                "Отраслевой риск (группа ОКВЭД)",
                "низкий — 5; средний — 3; высокий — 0 (5)",
                5,
                (
                    ScoreBand("eq", "low", 5),
                    ScoreBand("eq", "mid", 3),
                ),
                0,
            ),
            "mass_registration": FactorConfig(
                "Массовый руководитель или адрес",
                "нет — 5; да — 0 (5)",
                5,
                (ScoreBand("eq", 0, 5),),
                0,
            ),
            "turnover_stability": FactorConfig(
                "Стабильность (`turnover_cv`)",
                "<0,3 — 10; 0,3–0,6 — 5; >0,6 — 0 (10)",
                10,
                (
                    ScoreBand("lt", 0.3, 10),
                    ScoreBand("le", 0.6, 5),
                ),
                0,
            ),
            "turnover_trend": FactorConfig(
                "Тренд (`turnover_trend`)",
                "≥0,95 — 10; 0,8–0,95 — 5; <0,8 — 0 (10)",
                10,
                (
                    ScoreBand("ge", 0.95, 10),
                    ScoreBand("ge", 0.8, 5),
                ),
                0,
            ),
            "zero_months": FactorConfig(
                "Месяцы без поступлений (`zero_months`)",
                "0 — 10; 1 — 5; ≥2 — 0 (10)",
                10,
                (
                    ScoreBand("eq", 0, 10),
                    ScoreBand("eq", 1, 5),
                ),
                0,
            ),
            "payment_to_turnover": FactorConfig(
                "PTR (платежи к оборотам, см. ниже)",
                "<10% — 15; 10–20% (не вкл.) — 10; 20–30% (не вкл.) — 4; ≥30% — 0 (15)",
                15,
                (
                    ScoreBand("lt", 0.1, 15),
                    ScoreBand("lt", 0.2, 10),
                    ScoreBand("lt", 0.3, 4),
                ),
                0,
            ),
            "debt_to_turnover": FactorConfig(
                "Долг к годовому обороту (`total_balance` / 12 × `avg_turnover`)",
                "<25% — 10; 25–50% — 5; >50% — 0 (10)",
                10,
                (
                    ScoreBand("lt", 0.25, 10),
                    ScoreBand("le", 0.5, 5),
                ),
                0,
            ),
            "delinquency_12m": FactorConfig(
                "Просрочки за 12 мес. (`max_dpd_12m`)",
                "0 — 10; 1–30 дней — 5; 31–60 — 0 (10)",
                10,
                (
                    ScoreBand("eq", 0, 10),
                    ScoreBand("le", 30, 5),
                ),
                0,
            ),
            "credit_history_length": FactorConfig(
                "Длина кредитной истории",
                "≥24 мес. — 5; 1–23 — 3; нет истории — 2 (5)",
                5,
                (
                    ScoreBand("ge", 24, 5),
                    ScoreBand("ge", 1, 3),
                ),
                2,
            ),
            "bureau_inquiries_30d": FactorConfig(
                "Запросы в БКИ за 30 дней",
                "0–1 — 5; 2–3 — 2; ≥4 — 0 (5)",
                5,
                (
                    ScoreBand("le", 1, 5),
                    ScoreBand("le", 3, 2),
                ),
                0,
            ),
            "payment_discipline": FactorConfig(
                "Налоги, исполнительные производства, суды",
                "всё по нулям — 5; есть ниже стоп-порогов — 2 (5)",
                5,
                (ScoreBand("eq", 0, 5),),
                2,
            ),
        }
    )


@dataclass(frozen=True)
class DecisionConfig:
    key_rate: float = 14.0
    products: Mapping[str, ProductConfig] = field(default_factory=_products)
    factors: Mapping[str, FactorConfig] = field(default_factory=_factors)
    industry: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType(
            {
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
            }
        )
    )
    default_industry: str = "mid"
    okved_stop: tuple[str, ...] = ("92", "64.9")
    grade_bounds: tuple[tuple[int, Grade], ...] = ((75, "A"), (60, "B"), (45, "C"))
    stop_min_age: int = 6
    stop_max_dpd: int = 60
    stop_tax_debt: int = 50_000
    stop_enforcement: int = 100_000
    revenue_mismatch_ratio: float = 0.40
    ptr_limit: float = 0.30
    overdraft_payment_ratio: float = 0.10
    zero_month_ratio: float = 0.10
    trend_history_months: int = 9
    counter_step: int = 50_000
    retry_overdue_days: int = 30
    what_if_factor_count: int = 2


DEFAULT_CONFIG = DecisionConfig()
