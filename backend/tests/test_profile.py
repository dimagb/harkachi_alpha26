from datetime import date

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from test_auth import PERSONAS, api_client

from app.models import AccountTurnover, Company


@pytest.fixture(autouse=True)
def clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def profile_context(migrated_database):
    from app.integrations.registry import FakeRegistryProvider

    engine, _ = migrated_database
    with Session(engine) as session:
        provider = FakeRegistryProvider(
            {persona["inn"]: persona for persona in PERSONAS}
        )
        with api_client(session, provider) as client:
            yield client, session
        session.rollback()


@pytest.mark.parametrize(
    "code,turnover,source",
    [("ip_good", 1200000, "ЕГРИП"), ("ooo_border", 912500, "ЕГРЮЛ")],
)
def test_profile(profile_context, code, turnover, source):
    client, session = profile_context
    persona = next(persona for persona in PERSONAS if persona["code"] == code)
    token = client.post(
        "/auth/login",
        json={"login": persona["users"][0]["login"], "password": "b03-test-password"},
    ).json()["access_token"]
    company = session.scalar(select(Company).where(Company.inn == persona["inn"]))
    response = client.get(
        f"/companies/{company.id}/profile", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert set(data) == {
        "id",
        "inn",
        "ogrn",
        "kind",
        "name",
        "status",
        "reg_date",
        "okved_main",
        "address",
        "director_full_name",
        "founders",
        "avg_monthly_turnover",
        "source_note",
    }
    assert data["id"] == str(company.id)
    for field in (
        "inn",
        "ogrn",
        "kind",
        "name",
        "status",
        "reg_date",
        "okved_main",
        "address",
        "founders",
    ):
        assert data[field] == persona[field]
    assert data["director_full_name"] == persona["director"]["full_name"]
    assert data["avg_monthly_turnover"] == turnover
    assert data["source_note"] == f"Данные из {source} на {date.today():%d.%m.%Y}"


@pytest.mark.parametrize("values,expected", [([], 0), ([1, 2], 2)])
def test_turnover_rounding(profile_context, values, expected):
    from app.companies.profile import company_profile
    from app.integrations.registry import FakeRegistryProvider

    _, session = profile_context
    persona = PERSONAS[0]
    company = session.scalar(select(Company).where(Company.inn == persona["inn"]))
    session.execute(
        delete(AccountTurnover).where(AccountTurnover.company_id == company.id)
    )
    session.add_all(
        [
            AccountTurnover(
                company_id=company.id, month=f"2026-{i:02d}", credit_turnover=v
            )
            for i, v in enumerate(values, start=1)
        ]
    )
    session.flush()
    result = company_profile(
        session, company, FakeRegistryProvider({company.inn: persona})
    )
    assert result.avg_monthly_turnover == expected


@pytest.mark.parametrize("missing,expected", [(False, 503), (True, 404)])
def test_registry_profile_errors(migrated_database, missing, expected):
    from app.integrations.registry import FakeRegistryProvider, ProviderUnavailable

    class UnavailableRegistry:
        def get(self, inn):
            raise ProviderUnavailable()

    engine, _ = migrated_database
    with Session(engine) as session:
        provider = FakeRegistryProvider({}) if missing else UnavailableRegistry()
        with api_client(session, provider) as client:
            token = client.post(
                "/auth/login",
                json={"login": "ip_good", "password": "b03-test-password"},
            ).json()["access_token"]
            company_id = client.get(
                "/me", headers={"Authorization": f"Bearer {token}"}
            ).json()["companies"][0]["company"]["id"]
            response = client.get(
                f"/companies/{company_id}/profile",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == expected
            assert response.json()["error"]["code"] == (
                "NOT_FOUND" if missing else "SERVICE_UNAVAILABLE"
            )
            if not missing:
                assert response.json()["error"]["message"] == (
                    "Реестр временно недоступен, попробуйте позже"
                )


@pytest.mark.parametrize("status", [200, 404, 500, "timeout", "connection"])
def test_http_registry(status, monkeypatch):
    from app.integrations.registry import HttpRegistryProvider, ProviderUnavailable

    persona = PERSONAS[0]
    calls = []
    monkeypatch.setenv("MOCKS_URL", "http://registry.test/mock/v1")

    def respond(request):
        calls.append(request)
        assert request.url.host == "registry.test"
        assert request.url.path == f"/mock/v1/registry/{persona['inn']}"
        assert request.extensions["timeout"]["read"] == 3.0
        if status == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        if status == "connection":
            raise httpx.ConnectError("connection", request=request)
        return httpx.Response(status, json=persona)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = HttpRegistryProvider(client=client)
        if status == 200:
            record = provider.get(persona["inn"])
            assert record.inn == persona["inn"]
            assert record.director.full_name == persona["director"]["full_name"]
            assert record.director.inn is None
            assert "risk" not in record.model_dump()
        elif status == 404:
            assert provider.get(persona["inn"]) is None
        else:
            with pytest.raises(ProviderUnavailable):
                provider.get(persona["inn"])
    assert len(calls) == 1
