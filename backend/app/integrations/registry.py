from collections.abc import Mapping
from datetime import date
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app.config import get_settings


class RegistryDirector(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_name: str
    inn: str | None = None


class RegistryFounder(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_name: str
    share_pct: float


class RegistryRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    inn: str
    ogrn: str
    kind: Literal["IP", "OOO"]
    name: str
    status: Literal["ACTIVE", "LIQUIDATING", "LIQUIDATED"]
    reg_date: date
    okved_main: str
    address: str
    director: RegistryDirector
    founders: list[RegistryFounder]


class ProviderUnavailable(Exception):
    pass


class RegistryProvider(Protocol):
    def get(self, inn: str) -> RegistryRecord | None: ...


class HttpRegistryProvider:
    def __init__(self, client: httpx.Client | None = None):
        self.client = client
        self.base_url = get_settings().mocks_url.rstrip("/")

    def _get(self, client: httpx.Client, inn: str) -> RegistryRecord | None:
        try:
            response = client.get(f"{self.base_url}/registry/{inn}", timeout=3.0)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return RegistryRecord.model_validate(response.json())
        except (httpx.HTTPError, ValidationError, ValueError) as error:
            raise ProviderUnavailable() from error

    def get(self, inn: str) -> RegistryRecord | None:
        if self.client is not None:
            return self._get(self.client, inn)
        with httpx.Client() as client:
            return self._get(client, inn)


class FakeRegistryProvider:
    def __init__(self, records: Mapping[str, RegistryRecord | dict[str, object]]):
        self.records = records

    def get(self, inn: str) -> RegistryRecord | None:
        record = self.records.get(inn)
        return None if record is None else RegistryRecord.model_validate(record)


def get_registry_provider() -> RegistryProvider:
    return HttpRegistryProvider()
