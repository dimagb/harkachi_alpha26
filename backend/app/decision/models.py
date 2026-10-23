"""Неизменяемые входы и результаты чистого движка решения."""

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Literal

Outcome = Literal["APPROVE", "COUNTER", "DECLINE"]
State = Literal["INFO_REQUESTED", "MANUAL_REVIEW", "OFFER_ISSUED", "DECLINED"]
Grade = Literal["A", "B", "C", "D"]


@dataclass(frozen=True)
class CompanyFacts:
    kind: str
    status: str
    reg_date: date
    okved_main: str
    mass_director: bool
    mass_address: bool


@dataclass(frozen=True)
class BureauSummary:
    monthly_payments_total: int
    total_balance: int
    current_overdue_total: int
    max_dpd_12m: int
    credit_history_months: int
    inquiries_30d: int


@dataclass(frozen=True)
class TaxCheck:
    tax_debt: int
    enforcement_sum: int
    arbitration_defendant_sum: int
    bankruptcy: bool


@dataclass(frozen=True)
class RiskFlags:
    aml_flag: bool
    fraud_flag: bool


@dataclass(frozen=True)
class AppParams:
    product_code: str
    amount: int
    term_months: int
    purpose: str
    purpose_text: str | None
    declared_revenue_year: int


@dataclass(frozen=True)
class DecisionInputs:
    company: CompanyFacts
    bureau: BureauSummary
    tax: TaxCheck
    risk: RiskFlags
    app: AppParams
    turnover: tuple[int, ...]
    auto_decision_consent: bool
    answered_items: frozenset[str]
    as_of: date

    def __post_init__(self):
        if len(self.turnover) != 12:
            raise ValueError("Обороты должны содержать ровно 12 месяцев")
        object.__setattr__(self, "turnover", tuple(self.turnover))
        object.__setattr__(self, "answered_items", frozenset(self.answered_items))


@dataclass(frozen=True)
class FactorLine:
    code: str
    title: str
    value: str
    points: int
    max_points: int
    rule: str


@dataclass(frozen=True)
class RuleFired:
    code: str
    title: str
    value: str
    threshold: str
    effect: Literal["STOP", "ROUTE", "INFO", "POLICY"]


@dataclass(frozen=True)
class PolicyCalc:
    rate: float
    avg_turnover: int
    existing_payments: int
    free_payment: int
    cap_by_turnover: int
    max_amount: int
    requested_payment: int | None
    ptr_requested: float | None
    steps: list[str]


@dataclass(frozen=True)
class Offer:
    amount: int
    term_months: int
    rate: float
    monthly_payment: int | None


@dataclass(frozen=True)
class DecisionResult:
    state: State
    validation_rule: str | None = None
    outcome: Outcome | None = None
    reason_code: str | None = None
    client_reason_code: str | None = None
    grade: Grade | None = None
    score: int | None = None
    points: dict[str, int] = field(default_factory=dict)
    ptr_pct: float | None = None
    offer: Offer | None = None
    route_reason: str | None = None
    recommendation: dict[str, object] | None = None
    factors: list[FactorLine] = field(default_factory=list)
    rules_fired: list[RuleFired] = field(default_factory=list)
    policy: PolicyCalc | None = None
    what_if: list[str] = field(default_factory=list)

    def _outcome_expected(self) -> dict[str, object]:
        result: dict[str, object] = {"outcome": self.outcome}
        if self.reason_code is not None:
            result.update(
                reason_code=self.reason_code, client_reason_code=self.client_reason_code
            )
        if self.offer is not None:
            result["offer"] = asdict(self.offer)
        result.update(grade=self.grade, score=self.score)
        if self.score is not None:
            result.update(points=dict(self.points), ptr_pct=self.ptr_pct)
        return result

    def to_expected(self) -> dict[str, object]:
        """Формат оракула: отсутствующие у него ключи не добавляются."""
        if self.state == "INFO_REQUESTED":
            return {"state": self.state, "validation_rule": self.validation_rule}
        if self.state == "MANUAL_REVIEW":
            return {
                "state": self.state,
                "route_reason": self.route_reason,
                "recommendation": self._outcome_expected(),
            }
        return {"state": self.state, **self._outcome_expected()}
