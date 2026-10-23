from collections.abc import Mapping
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app.config import get_settings
from app.integrations.registry import ProviderUnavailable


class BureauLoan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    balance: int
    monthly_payment: int
    current_overdue: int
    max_dpd_12m: int


class BureauSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    monthly_payments_total: int
    total_balance: int
    current_overdue_total: int
    max_dpd_12m: int
    credit_history_months: int
    inquiries_30d: int


class BureauReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inn: str
    kind: Literal["FULL"]
    loans: list[BureauLoan]
    summary: BureauSummary


class BureauProvider(Protocol):
    def get(self, inn: str, consent_id: str) -> BureauReport: ...


class HttpBureauProvider:
    def __init__(self, client: httpx.Client | None = None):
        self.client = client
        self.base_url = get_settings().mocks_url.rstrip("/")

    def _get(self, client: httpx.Client, inn: str, consent_id: str) -> BureauReport:
        try:
            response = client.post(
                f"{self.base_url}/bki/report",
                json={"inn": inn, "kind": "FULL", "consent_id": consent_id},
                timeout=3.0,
            )
            response.raise_for_status()
            return BureauReport.model_validate(response.json())
        except (httpx.HTTPError, ValidationError, ValueError) as error:
            raise ProviderUnavailable() from error

    def get(self, inn: str, consent_id: str) -> BureauReport:
        if self.client is not None:
            return self._get(self.client, inn, consent_id)
        with httpx.Client() as client:
            return self._get(client, inn, consent_id)


class FakeBureauProvider:
    def __init__(self, records: Mapping[str, BureauReport | dict[str, object]]):
        self.records = records

    def get(self, inn: str, consent_id: str) -> BureauReport:
        if not consent_id or inn not in self.records:
            raise ProviderUnavailable()
        return BureauReport.model_validate(self.records[inn])


def get_bureau_provider() -> BureauProvider:
    return HttpBureauProvider()
