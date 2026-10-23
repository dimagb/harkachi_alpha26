from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.errors import register_error_handlers
from app.logging import CorrelationMiddleware
from app.main import app

client = TestClient(app)


def test_health_without_database(monkeypatch):
    connect = MagicMock(side_effect=AssertionError("health must not access DB"))
    monkeypatch.setattr("app.main.engine.connect", connect)
    response = client.get("/api/v1/health", headers={"X-Correlation-ID": "test-id"})
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Correlation-ID"] == "test-id"
    connect.assert_not_called()


def test_ready_success(monkeypatch):
    connect = MagicMock()
    monkeypatch.setattr("app.main.engine.connect", connect)
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    query = connect.return_value.__enter__.return_value.execute.call_args.args[0]
    assert str(query) == "SELECT 1"


def test_ready_unavailable(monkeypatch):
    monkeypatch.setattr(
        "app.main.engine.connect",
        MagicMock(side_effect=OperationalError("private DSN", {}, Exception("secret"))),
    )
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "SERVICE_UNAVAILABLE",
            "message": "Сервис временно недоступен",
            "details": {},
        }
    }
    assert response.headers["X-Correlation-ID"]


@pytest.mark.parametrize("method,status", [("get", 404), ("post", 405)])
def test_framework_errors(method, status):
    path = "/api/v1/nope" if status == 404 else "/api/v1/health"
    response = getattr(client, method)(path)
    assert response.status_code == status
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.headers["X-Correlation-ID"]


def test_validation_and_unhandled_error():
    # Test-only routes: the production API still has only health and ready.
    test_app = FastAPI()
    register_error_handlers(test_app)
    test_app.add_middleware(CorrelationMiddleware)

    @test_app.get("/validation")
    def validation(count: int):
        return {"count": count}

    @test_app.get("/failure")
    def failure():
        raise RuntimeError("private credentials")

    with TestClient(test_app) as test_client:
        invalid = test_client.get("/validation?count=no")
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
        assert "count" in invalid.json()["error"]["details"]["fields"]
        failed = test_client.get("/failure")
        assert failed.status_code == 500
        assert failed.json() == {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Внутренняя ошибка сервера",
                "details": {},
            }
        }
        assert failed.headers["X-Correlation-ID"]


def test_docs_and_schema():
    assert client.get("/api/v1/docs").status_code == 200
    schema = client.get("/api/v1/openapi.json").json()
    assert {"/api/v1/health", "/api/v1/ready"} <= set(schema["paths"])
