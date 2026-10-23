import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import User

settings = Settings()

PERSONAS = json.loads(
    (Path(__file__).resolve().parents[2] / "contracts/personas.json").read_text(
        encoding="utf-8"
    )
)["personas"]
LOGINS = [user["login"] for persona in PERSONAS for user in persona["users"]]


@contextmanager
def api_client(session, provider=None):
    """Exercise the real API with a migrated DB and an isolated registry provider."""
    from app.db import get_session
    from app.integrations.registry import FakeRegistryProvider, get_registry_provider
    from app.main import app

    def override_session():
        yield session

    if provider is None:
        provider = FakeRegistryProvider(
            {persona["inn"]: persona for persona in PERSONAS}
        )
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_registry_provider] = lambda: provider
    try:
        with TestClient(app, base_url="http://testserver/api/v1/") as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.fixture
def auth_session(migrated_database):
    engine, _ = migrated_database
    with Session(engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def auth_client(auth_session):
    with api_client(auth_session) as client:
        yield client


def test_token_claims():
    from app.auth.tokens import create_access_token

    user = User(id=uuid4(), role="CLIENT", login="t", full_name="Тест")
    before = int(datetime.now(UTC).timestamp())
    token = create_access_token(user)
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    assert jwt.get_unverified_header(token)["alg"] == "HS256"
    assert payload["sub"] == str(user.id)
    assert payload["role"] == "CLIENT"
    assert before <= payload["iat"] <= int(datetime.now(UTC).timestamp())
    assert payload["exp"] - payload["iat"] == settings.jwt_ttl_hours * 3600


def test_shared_current_user_dependency(auth_session):
    from app.auth.deps import current_user
    from app.main import app

    user = auth_session.scalar(select(User).where(User.login == "ip_good"))
    with api_client(auth_session) as client:
        app.dependency_overrides[current_user] = lambda: user
        response = client.get("/me")
        assert response.status_code == 200, response.text
        assert response.json()["user"]["id"] == str(user.id)


@pytest.mark.parametrize("login_name", [*LOGINS, "underwriter"])
def test_demo_login(auth_client, auth_session, login_name):
    response = auth_client.post(
        "/auth/login", json={"login": login_name, "password": "b03-test-password"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 28800
    user = auth_session.scalar(select(User).where(User.login == login_name))
    assert data["user"] == {
        "id": str(user.id),
        "role": user.role,
        "full_name": user.full_name,
    }
    assert jwt.decode(data["access_token"], settings.jwt_secret, algorithms=["HS256"])[
        "sub"
    ] == str(user.id)


def test_login_does_not_reveal_unknown_user(auth_client):
    responses = [
        auth_client.post("/auth/login", json={"login": login, "password": "wrong"})
        for login in ("ip_good", "no-such-login")
    ]
    assert [response.status_code for response in responses] == [401, 401]
    assert (
        responses[0].json()
        == responses[1].json()
        == {
            "error": {
                "code": "UNAUTHORIZED",
                "message": "Неверный логин или пароль",
                "details": {},
            }
        }
    )


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "expired",
        "wrong_key",
        "none",
        "broken",
        "no_bearer",
        "no_exp",
        "no_iat",
        "no_sub",
        "unknown_user",
        "invalid_sub",
        "hs384",
    ],
)
def test_invalid_tokens(auth_client, auth_session, case):
    user = auth_session.scalar(select(User).where(User.login == "ip_good"))
    now = datetime.now(UTC)
    claims = {
        "sub": str(user.id),
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    key, algorithm = settings.jwt_secret, "HS256"
    if case == "expired":
        claims["exp"] = now - timedelta(seconds=1)
    elif case == "wrong_key":
        key = "foreign-secret-with-at-least-thirty-two-bytes"
    elif case == "none":
        key, algorithm = None, "none"
    elif case.startswith("no_") and case != "no_bearer":
        del claims[case.removeprefix("no_")]
    elif case == "unknown_user":
        claims["sub"] = str(uuid4())
    elif case == "invalid_sub":
        claims["sub"] = "not-a-uuid"
    elif case == "hs384":
        algorithm = "HS384"
    token = jwt.encode(claims, key, algorithm=algorithm)
    header = f"Bearer {token}"
    if case == "broken":
        header = "Bearer damaged.token"
    elif case == "no_bearer":
        header = token
    response = auth_client.get(
        "/me", headers={} if case == "missing" else {"Authorization": header}
    )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json() == {
        "error": {"code": "UNAUTHORIZED", "message": "Требуется вход", "details": {}}
    }


@pytest.mark.parametrize("login_name", ["ooo_load_accountant", "underwriter"])
def test_memberships(auth_client, login_name):
    token = auth_client.post(
        "/auth/login", json={"login": login_name, "password": "b03-test-password"}
    ).json()["access_token"]
    response = auth_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    memberships = response.json()["companies"]
    if login_name == "underwriter":
        assert memberships == []
    else:
        assert len(memberships) == 1
        assert memberships[0]["can_sign"] is False
