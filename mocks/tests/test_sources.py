import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[2]
PERSONAS = json.loads((ROOT / "contracts/personas.json").read_text(encoding="utf-8"))[
    "personas"
]
REGISTRY_FIELDS = (
    "inn",
    "ogrn",
    "kind",
    "name",
    "status",
    "reg_date",
    "okved_main",
    "address",
    "founders",
)


def valid_inn(value):
    if not value.isascii() or not value.isdigit():
        return False
    digits = [int(digit) for digit in value]
    if len(value) == 10:
        weights = [(2, 4, 10, 3, 5, 9, 4, 6, 8)]
    elif len(value) == 12:
        weights = [(7, 2, 4, 10, 3, 5, 9, 4, 6, 8), (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)]
    else:
        return False
    return all(
        sum(d * w for d, w in zip(digits, row, strict=False)) % 11 % 10
        == digits[len(row)]
        for row in weights
    )


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    monkeypatch.delenv("DATA_ROOT", raising=False)
    monkeypatch.delenv("MOCK_FAILURE_INN", raising=False)
    monkeypatch.setenv("MOCK_LATENCY_MS", "0")


@pytest.fixture
def client():
    with TestClient(app) as connection:
        yield connection


def request_source(client, source, inn, **body):
    if source == "bki":
        return client.post("/mock/v1/bki/report", json={"inn": inn, **body})
    path = f"registry/{inn}" if source == "registry" else f"fns/check/{inn}"
    return client.get(f"/mock/v1/{path}")


@pytest.mark.parametrize("company", PERSONAS, ids=lambda c: c["code"])
def test_registry_matches_persona(client, company):
    response = request_source(client, "registry", company["inn"])
    assert response.status_code == 200
    result = response.json()
    assert set(result) == {*REGISTRY_FIELDS, "director"}
    assert {key: result[key] for key in REGISTRY_FIELDS} == {
        key: company[key] for key in REGISTRY_FIELDS
    }
    assert result["director"]["full_name"] == company["director"]["full_name"]
    assert set(result["director"]) == {"full_name", "inn"}
    assert valid_inn(result["inn"])
    assert valid_inn(result["director"]["inn"])
    if company["kind"] == "IP":
        assert result["director"]["inn"] == company["inn"]
    else:
        assert len(result["director"]["inn"]) == 12
    assert request_source(client, "registry", company["inn"]).json() == result


@pytest.mark.parametrize("company", PERSONAS, ids=lambda c: c["code"])
@pytest.mark.parametrize("kind", ["INFO", "FULL"])
def test_bki_matches_persona(client, company, kind):
    response = request_source(
        client, "bki", company["inn"], kind=kind, consent_id="demo-consent"
    )
    expected = {
        "inn": company["inn"],
        "kind": kind,
        "summary": company["bki"]["summary"],
    }
    if kind == "FULL":
        expected["loans"] = company["bki"]["loans"]
    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.parametrize("company", PERSONAS, ids=lambda c: c["code"])
def test_fns_matches_persona(client, company):
    response = request_source(client, "fns", company["inn"])
    assert response.status_code == 200
    assert response.json() == {"inn": company["inn"], **company["fns"]}


def test_alpha_trade_acceptance(client):
    response = client.get("/mock/v1/registry/7706123455")
    assert response.status_code == 200
    assert response.json()["name"] == "ООО «Альфа-Трейд»"


@pytest.mark.parametrize("consent", [None, "", "   "])
def test_full_requires_nonempty_consent(client, consent):
    response = request_source(
        client, "bki", PERSONAS[0]["inn"], kind="FULL", consent_id=consent
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_info_without_consent(client):
    response = request_source(client, "bki", PERSONAS[0]["inn"], kind="INFO")
    assert response.status_code == 200
    assert "loans" not in response.json()


@pytest.mark.parametrize("source", ["registry", "bki", "fns"])
@pytest.mark.parametrize(
    "inn",
    [
        "7706123456",
        "770112345690",
        "123",
        "abcdefghij",
        "７７０６１２３４５５",
        "0000000000",
        pytest.param("1" * 5000, id="too-long"),
    ],
)
def test_invalid_inn_not_found(client, source, inn):
    response = request_source(client, source, inn, kind="INFO")
    assert response.status_code == 404
    assert set(response.json()) == {"error"}
    assert set(response.json()["error"]) == {"code", "message", "details"}
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize("source", ["registry", "bki", "fns"])
@pytest.mark.parametrize("index", [0, 1])
def test_configured_failure_all_sources(monkeypatch, source, index):
    monkeypatch.setenv(
        "MOCK_FAILURE_INN",
        " , " + ", ".join(company["inn"] for company in PERSONAS[:2]),
    )
    with TestClient(app) as client:
        response = request_source(client, source, PERSONAS[index]["inn"], kind="FULL")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert client.get("/mock/v1/health").status_code == 200
        assert request_source(client, "registry", PERSONAS[2]["inn"]).status_code == 200


@pytest.mark.parametrize("inn", ["7707083893", "500100732259"])
def test_unknown_company_deterministic_across_startups(inn):
    assert valid_inn(inn)
    assert inn not in {c["inn"] for c in PERSONAS}
    snapshots = []
    for _ in range(2):
        with TestClient(app) as client:
            results = [
                request_source(client, source, inn, kind="FULL", consent_id="yes")
                for source in ["registry", "bki", "fns"]
            ]
            assert all(response.status_code == 200 for response in results)
            snapshots.append([response.json() for response in results])
    assert snapshots[0] == snapshots[1]
    registry, bki, fns = snapshots[0]
    assert registry["inn"] == inn
    assert valid_inn(registry["director"]["inn"])
    assert registry["status"] == "ACTIVE"
    assert registry["kind"] == ("OOO" if len(inn) == 10 else "IP")
    if len(inn) == 12:
        assert registry["director"]["inn"] == inn
    assert bki["summary"]["current_overdue_total"] == 0
    assert bki["summary"]["max_dpd_12m"] == 0
    assert bki["summary"]["monthly_payments_total"] == sum(
        loan["monthly_payment"] for loan in bki["loans"]
    )
    assert bki["summary"]["total_balance"] == sum(
        loan["balance"] for loan in bki["loans"]
    )
    assert fns["tax_debt"] == fns["enforcement_sum"] == 0
    assert fns["bankruptcy"] is False


def test_data_root_and_optional_background(monkeypatch, tmp_path):
    (tmp_path / "contracts").mkdir()
    source = tmp_path / "contracts/personas.json"
    source.write_text(json.dumps({"personas": [PERSONAS[0]]}), encoding="utf-8")
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    with TestClient(app) as client:
        assert (
            request_source(client, "registry", PERSONAS[0]["inn"]).json()["name"]
            == PERSONAS[0]["name"]
        )
    (tmp_path / "data").mkdir()
    company = {**PERSONAS[1], "name": "Фоновая компания из DATA_ROOT"}
    (tmp_path / "data/background.json").write_text(
        json.dumps({"companies": [company]}), encoding="utf-8"
    )
    with TestClient(app) as client:
        assert (
            request_source(client, "registry", company["inn"]).json()["name"]
            == company["name"]
        )
        assert request_source(client, "fns", company["inn"]).json() == {
            "inn": company["inn"],
            **company["fns"],
        }


def test_all_background_companies(client):
    companies = json.loads((ROOT / "data/background.json").read_text(encoding="utf-8"))[
        "companies"
    ]
    for company in companies:
        assert valid_inn(company["inn"])
        assert (
            request_source(client, "registry", company["inn"]).json()["name"]
            == company["name"]
        )
        assert request_source(client, "fns", company["inn"]).json() == {
            "inn": company["inn"],
            **company["fns"],
        }
        assert request_source(
            client, "bki", company["inn"], kind="FULL", consent_id="yes"
        ).json() == {"inn": company["inn"], "kind": "FULL", **company["bki"]}


@pytest.mark.parametrize("latency", [None, "60"])
@pytest.mark.parametrize("source", ["registry", "bki", "fns"])
def test_latency(monkeypatch, latency, source):
    if latency is None:
        monkeypatch.delenv("MOCK_LATENCY_MS")
    else:
        monkeypatch.setenv("MOCK_LATENCY_MS", latency)
    with TestClient(app) as client:
        start = time.perf_counter()
        response = request_source(client, source, PERSONAS[0]["inn"], kind="INFO")
        elapsed = time.perf_counter() - start
    assert response.status_code == 200
    assert elapsed >= (0.3 if latency is None else 0.06)


@pytest.mark.parametrize(
    "body",
    [
        {"inn": "7706123455", "kind": "OTHER"},
        {"inn": "7706123455", "kind": "INFO", "unexpected": True},
        {"kind": "INFO"},
    ],
)
def test_invalid_request_api_error(client, body):
    response = client.post("/mock/v1/bki/report", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "fields" in response.json()["error"]["details"]
