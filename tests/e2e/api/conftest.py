"""Общий контракт и единая проверка доступности для модуля живого стенда."""

import json
import os
from pathlib import Path

import httpx
import pytest
from client import DEFAULT_BASE_URL, ApiClient

ROOT = Path(__file__).resolve().parents[3]


def require_ready(base_url, *, transport=None):
    with httpx.Client(transport=transport, timeout=3, trust_env=False) as http:
        try:
            ready = http.get(base_url.rstrip("/") + "/ready").status_code == 200
        except httpx.RequestError:
            ready = False
    if not ready:
        # TODO(lead): разрешённый A-03 пропуск всего модуля до появления стенда M1/M2.
        pytest.skip(f"Стенд недоступен: {base_url}", allow_module_level=True)


class StandModule(pytest.Module):
    def collect(self):
        require_ready(os.getenv("E2E_BASE_URL", DEFAULT_BASE_URL))
        return super().collect()


def pytest_pycollect_makemodule(module_path, parent):
    if module_path.name == "test_personas.py":
        return StandModule.from_parent(parent, path=module_path)
    return None


@pytest.fixture(scope="session")
def persona_data():
    return json.loads((ROOT / "contracts/personas.json").read_text(encoding="utf-8"))


@pytest.fixture
def client():
    with ApiClient() as api:
        yield api


@pytest.fixture
def bank(persona_data):
    with ApiClient() as api:
        api.login(persona_data["staff"][0]["login"])
        yield api
