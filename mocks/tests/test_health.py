from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/mock/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert {route.path for route in app.routes} == {"/mock/v1/health"}
