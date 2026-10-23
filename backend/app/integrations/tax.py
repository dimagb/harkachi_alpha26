from collections.abc import Mapping
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app.config import get_settings
from app.integrations.registry import ProviderUnavailable


class MspRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    included: bool
    category: str | None


class TaxRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inn: str
    tax_debt: int
    enforcement_sum: int
    arbitration_defendant_sum: int
    bankruptcy: bool
    msp_registry: MspRegistry
    mass_director: bool
    mass_address: bool


class TaxProvider(Protocol):
    def get(self, inn: str) -> TaxRecord: ...


class HttpTaxProvider:
    def __init__(self, client: httpx.Client | None = None):
        self.client = client
        self.base_url = get_settings().mocks_url.rstrip("/")

    def _get(self, client: httpx.Client, inn: str) -> TaxRecord:
        try:
            response = client.get(f"{self.base_url}/fns/check/{inn}", timeout=3.0)
            response.raise_for_status()
            return TaxRecord.model_validate(response.json())
        except (httpx.HTTPError, ValidationError, ValueError) as error:
            raise ProviderUnavailable() from error

    def get(self, inn: str) -> TaxRecord:
        if self.client is not None:
            return self._get(self.client, inn)
        with httpx.Client() as client:
            return self._get(client, inn)


class FakeTaxProvider:
    def __init__(self, records: Mapping[str, TaxRecord | dict[str, object]]):
        self.records = records

    def get(self, inn: str) -> TaxRecord:
        if inn not in self.records:
            raise ProviderUnavailable()
        return TaxRecord.model_validate(self.records[inn])


def get_tax_provider() -> TaxProvider:
    return HttpTaxProvider()
