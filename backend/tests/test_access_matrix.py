import re
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_auth import PERSONAS, make_test_app

from app.models import Company

CASES = [
    ("GET", "/me", "anonymous", 401),
    ("GET", "/me", "client", 200),
    ("GET", "/me", "underwriter", 200),
    ("GET", "/products", "anonymous", 401),
    ("GET", "/products", "client", 200),
    ("GET", "/products", "underwriter", 403),
    ("POST", "/calculator", "anonymous", 401),
    ("POST", "/calculator", "client", 200),
    ("POST", "/calculator", "underwriter", 403),
    ("GET", "/companies/{own}/profile", "anonymous", 401),
    ("GET", "/companies/{own}/profile", "client", 200),
    ("GET", "/companies/{foreign}/profile", "client", 404),
    ("GET", "/companies/{own}/profile", "underwriter", 403),
    ("GET", "/companies/{missing}/profile", "anonymous", 401),
    ("GET", "/companies/{missing}/profile", "client", 404),
    ("GET", "/companies/{missing}/profile", "underwriter", 403),
]


@pytest.mark.parametrize("method,path,actor,expected", CASES)
def test_access_matrix(migrated_database, method, path, actor, expected):
    from app.integrations.registry import FakeRegistryProvider

    engine, _ = migrated_database
    with Session(engine) as session:
        provider = FakeRegistryProvider(
            {persona["inn"]: persona for persona in PERSONAS}
        )
        with TestClient(make_test_app(session, provider)) as client:
            own = session.scalar(
                select(Company).where(Company.inn == PERSONAS[0]["inn"])
            )
            foreign = session.scalar(select(Company).where(Company.id != own.id))
            path = path.format(own=own.id, foreign=foreign.id, missing=uuid4())
            if actor != "anonymous":
                login = "ip_good" if actor == "client" else "underwriter"
                token = client.post(
                    "/auth/login",
                    json={"login": login, "password": "b03-test-password"},
                ).json()["access_token"]
                client.headers["Authorization"] = f"Bearer {token}"
            kwargs = (
                {
                    "json": {
                        "product_code": "EXPRESS",
                        "amount": 1500000,
                        "term_months": 24,
                    }
                }
                if method == "POST"
                else {}
            )
            response = client.request(method, path, **kwargs)
            assert response.status_code == expected, response.text
            if expected >= 400:
                data = response.json()
                assert set(data) == {"error"}
                assert set(data["error"]) == {"code", "message", "details"}
                assert (
                    data["error"]["code"]
                    == {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND"}[
                        expected
                    ]
                )
                assert re.search("[А-Яа-яЁё]", data["error"]["message"])
                assert isinstance(data["error"]["details"], dict)
