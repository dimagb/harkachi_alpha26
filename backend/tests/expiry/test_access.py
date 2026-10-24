from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth.deps import current_user
from app.config import get_settings
from app.main import app
from app.models import User


@pytest.fixture
def bank_user():
    app.dependency_overrides[current_user] = lambda: User(
        id=uuid4(), role="UNDERWRITER", login="bank", full_name="Банк", password_hash=""
    )
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_shift_is_hidden_outside_demo(bank_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    response = bank_user.post(
        "/api/v1/demo/time-shift", json={"application_id": str(uuid4()), "days": 1}
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_client_cannot_shift_time():
    app.dependency_overrides[current_user] = lambda: User(
        id=uuid4(), role="CLIENT", login="client", full_name="Клиент", password_hash=""
    )
    try:
        response = TestClient(app).post(
            "/api/v1/demo/time-shift", json={"application_id": "abc", "days": 1}
        )
        assert response.status_code == 403, response.text
    finally:
        app.dependency_overrides.pop(current_user, None)
