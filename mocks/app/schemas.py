from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"] = "ok"


class Director(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str
    inn: str


class Founder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str
    share_pct: int


class RegistryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inn: str
    ogrn: str
    kind: Literal["IP", "OOO"]
    name: str
    status: Literal["ACTIVE", "LIQUIDATING", "LIQUIDATED"]
    reg_date: str
    okved_main: str
    address: str
    director: Director
    founders: list[Founder]


class BkiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inn: str
    kind: Literal["INFO", "FULL"]
    consent_id: str | None = None


class Loan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    balance: int
    monthly_payment: int
    current_overdue: int
    max_dpd_12m: int


class BkiSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    monthly_payments_total: int
    total_balance: int
    current_overdue_total: int
    max_dpd_12m: int
    credit_history_months: int
    inquiries_30d: int


class BkiInfoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inn: str
    kind: Literal["INFO"] = "INFO"
    summary: BkiSummary


class BkiFullResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inn: str
    kind: Literal["FULL"] = "FULL"
    summary: BkiSummary
    loans: list[Loan]


class MspRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    included: bool
    category: str


class FnsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inn: str
    tax_debt: int
    enforcement_sum: int
    arbitration_defendant_sum: int
    bankruptcy: bool
    msp_registry: MspRegistry
    mass_director: bool
    mass_address: bool


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Literal["NOT_FOUND", "FORBIDDEN", "SERVICE_UNAVAILABLE", "VALIDATION_ERROR"]
    message: str
    details: dict[str, object]


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: ErrorDetail
