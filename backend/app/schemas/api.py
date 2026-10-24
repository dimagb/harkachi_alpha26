"""Pydantic representation of contracts/api-types.ts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.errors import ApiError, ErrorCode

__all__ = ["ApiError", "ErrorCode"]

Role = Literal["CLIENT", "UNDERWRITER", "GUARANTOR"]
CompanyKind = Literal["IP", "OOO"]
ProductCode = Literal["EXPRESS", "WORKING_CAPITAL", "OVERDRAFT"]
Purpose = Literal["WORKING_CAPITAL", "CASH_GAP", "EQUIPMENT", "OTHER"]
ApplicationState = Literal[
    "DRAFT",
    "SUBMITTED",
    "VALIDATION",
    "INFO_REQUESTED",
    "ENRICHMENT",
    "ASSESSMENT",
    "MANUAL_REVIEW",
    "OFFER_ISSUED",
    "DECLINED",
    "SIGNING",
    "SIGNED",
    "DISBURSED",
    "WITHDRAWN",
    "EXPIRED",
]
StageCode = Literal[
    "APPLICATION", "CHECK", "ASSESSMENT", "DECISION", "SIGNING", "DISBURSEMENT"
]
StageStatus = Literal[
    "done", "current", "action_required", "pending", "failed", "cancelled"
]
ClientAction = Literal[
    "EDIT_DRAFT",
    "SUBMIT",
    "REQUEST_SIGNATURE",
    "ANSWER_INFO_REQUEST",
    "ACCEPT_OFFER",
    "REJECT_OFFER",
    "SIGN",
    "WITHDRAW",
    "OBJECT",
    "NEW_APPLICATION",
]
InfoItemCode = Literal["REVENUE_CONFIRM", "PURPOSE_DETAILS", "UNDERWRITER_QUESTION"]
OfferKind = Literal["APPROVED", "COUNTER"]
OfferStatus = Literal["ACTIVE", "ACCEPTED", "REJECTED", "EXPIRED", "SUPERSEDED"]
PartyRole = Literal["BORROWER_SIGNATORY", "GUARANTOR"]
OtpPurpose = Literal["CONSENTS", "OFFER", "GUARANTEE"]
Grade = Literal["A", "B", "C", "D"]
RouteReason = Literal[
    "GRADE_C",
    "AMOUNT_ABOVE_AUTO",
    "NO_AUTO_CONSENT",
    "SOURCE_UNAVAILABLE",
    "OBJECTION",
    "INFO_RESPONSE",
]
UnderwriterOutcome = Literal[
    "APPROVE", "COUNTER", "DECLINE", "REQUEST_INFO", "RETRY_ENRICHMENT"
]
ClientReasonCategory = Literal[
    "Данные о компании",
    "Финансовое положение",
    "Срок ведения бизнеса",
    "Кредитная история",
    "Налоги и обязательства",
    "Условия продукта",
    "Дополнительные проверки",
    "Финансовые показатели",
    "Долговая нагрузка",
]
CheckSource = Literal["BKI", "EGRUL", "FNS"]
CheckStatus = Literal["PENDING", "OK", "FAILED"]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(Schema):
    login: str
    password: str


class UserBrief(Schema):
    id: str
    full_name: str
    role: Role


class LoginResponse(Schema):
    access_token: str
    token_type: Literal["bearer"]
    expires_in: int
    user: UserBrief


class CompanyBrief(Schema):
    id: str
    inn: str
    kind: CompanyKind
    name: str


class Membership(Schema):
    company: CompanyBrief
    position: str
    can_sign: bool
    is_founder: bool


class MeResponse(Schema):
    user: UserBrief
    companies: list[Membership]


class Product(Schema):
    code: ProductCode
    name: str
    description: str
    purposes: list[Purpose]
    min_amount: int
    max_amount: int
    min_term_months: int
    max_term_months: int
    rate_from: float
    requires_guarantor_ooo: bool
    key_rate: float
    key_rate_date: str


class CalculatorRequest(Schema):
    product_code: ProductCode
    amount: int = Field(gt=0)
    term_months: int = Field(gt=0)


class CalculatorResponse(Schema):
    rate_estimate: float
    monthly_payment: int | None


class Founder(Schema):
    full_name: str
    share_pct: float


class CompanyProfile(Schema):
    id: str
    inn: str
    ogrn: str
    kind: CompanyKind
    name: str
    status: Literal["ACTIVE", "LIQUIDATING", "LIQUIDATED"]
    reg_date: str
    okved_main: str
    address: str
    director_full_name: str
    founders: list[Founder]
    avg_monthly_turnover: int
    source_note: str


class ApplicationCreate(Schema):
    company_id: str
    product_code: ProductCode
    amount: int = Field(gt=0)
    term_months: int = Field(gt=0)
    purpose: Purpose
    purpose_text: str | None = Field(default=None, min_length=10, max_length=500)
    declared_revenue_year: int = Field(gt=0)


class ApplicationPatch(Schema):
    product_code: ProductCode | None = None
    amount: int | None = Field(default=None, gt=0)
    term_months: int | None = Field(default=None, gt=0)
    purpose: Purpose | None = None
    purpose_text: str | None = Field(default=None, min_length=10, max_length=500)
    declared_revenue_year: int | None = Field(default=None, gt=0)


class TimelineItem(Schema):
    stage_code: StageCode
    title: str
    status: StageStatus
    at: str | None


class Stage(Schema):
    index: Literal[1, 2, 3, 4, 5, 6]
    code: StageCode
    title: str
    what_happens: str
    what_to_do: str | None


class RequestedTerms(Schema):
    amount: int
    term_months: int


class OfferClient(Schema):
    id: str
    version: int
    kind: OfferKind
    status: OfferStatus
    product_code: ProductCode
    amount: int
    term_months: int
    rate: float
    monthly_payment: int | None
    expires_at: str
    explanation: list[str] = Field(min_length=1, max_length=3)
    requested: RequestedTerms | None
    counter_reason: str | None


class ClientReason(Schema):
    code: str
    category: ClientReasonCategory | None
    text: str
    action: str | None
    retry_after: str | None


class InfoRequestItem(Schema):
    item_code: InfoItemCode
    question: str
    requires_value: bool


class InfoRequestClient(Schema):
    id: str
    items: list[InfoRequestItem]
    due_at: str


class PartyClient(Schema):
    id: str
    role: PartyRole
    full_name: str
    signed: bool
    is_me: bool


class ObjectionClient(Schema):
    status: Literal["PENDING", "RESOLVED"]
    created_at: str
    outcome_text: str | None


class ApplicationClient(Schema):
    id: str
    number: int
    version: int
    company_id: str
    state: ApplicationState
    stage: Stage
    timeline: list[TimelineItem]
    product_code: ProductCode
    amount: int
    term_months: int
    purpose: Purpose
    purpose_text: str | None
    declared_revenue_year: int
    offer: OfferClient | None
    client_reason: ClientReason | None
    info_request: InfoRequestClient | None
    parties: list[PartyClient]
    allowed_actions: list[ClientAction]
    awaiting_signature: bool
    objection: ObjectionClient | None
    created_at: str
    updated_at: str


class ApplicationListItem(Schema):
    id: str
    number: int
    state: ApplicationState
    stage: Stage
    product_code: ProductCode
    amount: int
    awaiting_signature: bool
    updated_at: str


class OtpRequest(Schema):
    purpose: OtpPurpose
    party_id: str | None = None


class OtpResponse(Schema):
    otp_id: str
    demo_code: str
    expires_at: str


class Consents(Schema):
    pdn: Literal[True]
    bki: Literal[True]
    auto_decision: bool


class SubmitRequest(Schema):
    otp_id: str
    code: str
    consents: Consents


class InfoAnswer(Schema):
    item_code: InfoItemCode
    value: int | None = None
    comment: str = Field(min_length=3, max_length=1000)


class InfoResponseRequest(Schema):
    answers: list[InfoAnswer]


class AcceptOfferRequest(Schema):
    offer_version: int


class SignRequest(Schema):
    otp_id: str
    code: str
    party_id: str


class ObjectionRequest(Schema):
    text: str = Field(min_length=10, max_length=2000)


class QueueItem(Schema):
    id: str
    number: int
    company_name: str
    company_kind: CompanyKind
    product_code: ProductCode
    amount: int
    grade: Grade | None
    route_reason: RouteReason
    waiting_since: str


class FactorLine(Schema):
    code: str
    title: str
    value: str
    points: int
    max_points: int
    rule: str


class RuleFired(Schema):
    code: str
    title: str
    value: str
    threshold: str
    effect: Literal["STOP", "ROUTE", "INFO", "POLICY"]


class PolicyCalc(Schema):
    rate: float
    avg_turnover: int
    existing_payments: int
    free_payment: int
    cap_by_turnover: int
    max_amount: int
    requested_payment: int | None
    ptr_requested: float | None
    steps: list[str]


class Recommendation(Schema):
    outcome: Literal["APPROVE", "COUNTER", "DECLINE"]
    amount: int | None
    term_months: int | None
    rate: float | None


class DecisionBank(Schema):
    id: str
    kind: Literal["AUTO", "MANUAL"]
    outcome: Literal[
        "APPROVE", "COUNTER", "DECLINE", "MANUAL", "REQUEST_INFO", "RETRY_ENRICHMENT"
    ]
    client_reason_code: str | None
    route_reason: RouteReason | None
    grade: Grade | None
    score: int | None
    factors: list[FactorLine]
    rules_fired: list[RuleFired]
    internal_reasons: list[str]
    policy: PolicyCalc | None
    recommendation: Recommendation | None
    what_if: list[str]
    config_version: str
    key_rate: float
    made_by: str | None
    comment: str | None
    created_at: str


class ExternalCheckBank(Schema):
    source: CheckSource
    status: CheckStatus
    attempts: int
    fetched_at: str | None
    response: dict[str, object] | None


class EventBank(Schema):
    at: str
    event_type: str
    from_state: ApplicationState | None
    to_state: ApplicationState | None
    actor: str
    reason_code: str | None
    note: str | None


class RiskFlags(Schema):
    aml_flag: bool
    fraud_flag: bool


class TurnoverMonth(Schema):
    month: str
    amount: int


class ApplicationBank(ApplicationClient):
    company: CompanyProfile
    risk_flags: RiskFlags
    turnover_12m: list[TurnoverMonth]
    decisions: list[DecisionBank]
    external_checks: list[ExternalCheckBank]
    events: list[EventBank]


class UnderwriterDecisionRequest(Schema):
    outcome: UnderwriterOutcome
    amount: int | None = Field(default=None, gt=0)
    term_months: int | None = Field(default=None, gt=0)
    client_reason_category: ClientReasonCategory | None = None
    info_questions: list[str] | None = Field(default=None, min_length=1, max_length=5)
    comment: str = Field(min_length=5, max_length=2000)


class BankListItem(Schema):
    id: str
    number: int
    company_name: str
    company_kind: CompanyKind
    product_code: ProductCode
    amount: int
    grade: Grade | None
    route_reason: RouteReason | None
    waiting_since: str | None
    state: ApplicationState
    updated_at: str


class Page[T](Schema):
    items: list[T]
    total: int
    page: int
    size: int = Field(le=100)


class TimeShiftRequest(Schema):
    application_id: str
    days: int = Field(ge=1, le=400)


class TimeShiftResponse(Schema):
    application_id: str
    expired_now: bool
    state: ApplicationState
