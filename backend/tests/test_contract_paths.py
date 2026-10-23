"""The published route table is the independent source of expectations."""

import re
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fixtures_bodies import BODIES, ID

from app.auth.deps import current_user
from app.main import app
from app.models import User


def contract_rows():
    rows = []
    document = Path(__file__).resolve().parents[2] / "contracts/api.md"
    for line in document.read_text(encoding="utf-8").splitlines():
        columns = [part.strip() for part in line.split("|")[1:-1]]
        if not columns or columns[0] not in {"GET", "POST", "PATCH"}:
            continue
        method, paths, role, models, transition = columns
        for path in re.findall(r"`([^`]+)`", paths):
            path = path.split("?")[0]
            if path == "/preview":
                continue
            request = models.split("→")[0].strip(" `")
            rows.append((method.lower(), "/api/v1" + path, role, request, transition))
    return rows


ROWS = contract_rows()
STUBS = [row for row in ROWS if row[1] not in {"/api/v1/health", "/api/v1/ready"}]
IMPLEMENTED = {
    ("POST", "/api/v1/auth/login"),
    ("GET", "/api/v1/me"),
    ("GET", "/api/v1/products"),
    ("POST", "/api/v1/calculator"),
    ("GET", "/api/v1/companies/{id}/profile"),
    ("POST", "/api/v1/applications"),
    ("PATCH", "/api/v1/applications/{id}"),
    ("GET", "/api/v1/applications"),
    ("GET", "/api/v1/applications/{id}"),
    ("POST", "/api/v1/applications/{id}/otp"),
    ("POST", "/api/v1/applications/{id}/submit"),
    ("POST", "/api/v1/applications/{id}/request-signature"),
}
assert len(IMPLEMENTED) == 12


@pytest.fixture
def stub_user():
    app.dependency_overrides[current_user] = lambda: User(
        id=uuid4(), role="CLIENT", login="t", full_name="t", password_hash=""
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_contract_paths_exact():
    expected = {(method, path) for method, path, *_ in ROWS}
    actual = {
        (method, path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    assert actual == expected


@pytest.mark.parametrize(
    "method,path,role,body_type,transition",
    [row for row in STUBS if (row[0].upper(), row[1]) not in IMPLEMENTED],
)
def test_valid_requests_reach_stub(
    method, path, role, body_type, transition, stub_user
):
    response = TestClient(app).request(
        method,
        path.replace("{id}", ID),
        params={"company_id": ID} if path == "/api/v1/applications" else {},
        headers={"If-Match": "1"},
        json=BODIES.get(body_type),
    )
    assert response.status_code == 501, response.text
    assert response.json() == {
        "error": {
            "code": "NOT_IMPLEMENTED",
            "message": "Эндпоинт ещё не реализован",
            "details": {},
        }
    }


@pytest.mark.parametrize("method,path,role,body_type,transition", STUBS)
def test_operation_metadata(method, path, role, body_type, transition):
    operation = app.openapi()["paths"][path][method]
    codes = {501}
    if path != "/api/v1/auth/login":
        codes.add(401)
        assert operation["security"] == [{"bearerAuth": []}]
    else:
        assert "security" not in operation
    if role != "все":
        codes.add(403)
    if "{id}" in path:
        codes.add(404)
    if transition != "—":
        codes.add(409)
    if (
        body_type in BODIES
        or path in {"/api/v1/applications", "/api/v1/bank/applications"}
        and method == "get"
    ):
        codes.add(422)
    for code in codes:
        assert operation["responses"][str(code)]["content"]["application/json"][
            "schema"
        ] == {
            "$ref": "#/components/schemas/ApiError",
        }
    for status, response in operation["responses"].items():
        if int(status) >= 400:
            assert response["content"]["application/json"]["schema"] == {
                "$ref": "#/components/schemas/ApiError",
            }
    assert operation["tags"]
    assert re.search("[А-Яа-я]", operation["summary"])
    assert "200" in operation["responses"]
    if body_type in BODIES:
        assert operation["requestBody"]["required"] is True


def test_if_match_header():
    parameters = app.openapi()["paths"]["/api/v1/applications/{id}"]["patch"][
        "parameters"
    ]
    assert any(p["name"] == "If-Match" and p["in"] == "header" for p in parameters)
