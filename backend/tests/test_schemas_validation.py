from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fixtures_bodies import BODIES, ID

from app.auth.deps import current_user
from app.main import app
from app.models import User

CREATE = "/api/v1/applications"
DECIDE = f"/api/v1/underwriting/{ID}/decision"
INFO = f"/api/v1/applications/{ID}/info-response"


@pytest.fixture(autouse=True)
def validation_user():
    app.dependency_overrides[current_user] = lambda: User(
        id=uuid4(), role="CLIENT", login="t", full_name="t", password_hash=""
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(current_user, None)


@pytest.mark.parametrize(
    "path,model,changes,field",
    [
        (CREATE, "ApplicationCreate", {"purpose_text": "x" * 9}, "purpose_text"),
        (CREATE, "ApplicationCreate", {"purpose_text": "x" * 501}, "purpose_text"),
        (
            CREATE,
            "ApplicationCreate",
            {"declared_revenue_year": 0},
            "declared_revenue_year",
        ),
        (CREATE, "ApplicationCreate", {"amount": 0}, "amount"),
        (CREATE, "ApplicationCreate", {"term_months": 0}, "term_months"),
        ("/api/v1/calculator", "CalculatorRequest", {"amount": -1}, "amount"),
        ("/api/v1/calculator", "CalculatorRequest", {"term_months": 0}, "term_months"),
        (
            INFO,
            "InfoResponseRequest",
            {"answers": [{"item_code": "PURPOSE_DETAILS", "comment": "xx"}]},
            "answers.0.comment",
        ),
        (
            INFO,
            "InfoResponseRequest",
            {"answers": [{"item_code": "PURPOSE_DETAILS", "comment": "x" * 1001}]},
            "answers.0.comment",
        ),
        (
            f"/api/v1/applications/{ID}/objection",
            "ObjectionRequest",
            {"text": "x" * 9},
            "text",
        ),
        (
            f"/api/v1/applications/{ID}/objection",
            "ObjectionRequest",
            {"text": "x" * 2001},
            "text",
        ),
        (
            DECIDE,
            "UnderwriterDecisionRequest",
            {"info_questions": []},
            "info_questions",
        ),
        (
            DECIDE,
            "UnderwriterDecisionRequest",
            {"info_questions": ["Вопрос"] * 6},
            "info_questions",
        ),
        (DECIDE, "UnderwriterDecisionRequest", {"comment": "xxxx"}, "comment"),
        (DECIDE, "UnderwriterDecisionRequest", {"comment": "x" * 2001}, "comment"),
        ("/api/v1/demo/time-shift", "TimeShiftRequest", {"days": 0}, "days"),
        ("/api/v1/demo/time-shift", "TimeShiftRequest", {"days": 401}, "days"),
        (CREATE, "ApplicationCreate", {"purpose": "INVALID"}, "purpose"),
        (CREATE, "ApplicationCreate", {"surprise": True}, "surprise"),
        (CREATE, "ApplicationCreate", {"amount": "invalid"}, "amount"),
    ],
)
def test_invalid_bodies(path, model, changes, field):
    body = deepcopy(BODIES[model])
    body.update(changes)
    assert_validation(TestClient(app).post(path, json=body), field)


def assert_validation(response, field):
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Проверьте заполнение полей"
    assert field in error["details"]["fields"]
    assert all(
        any("а" <= char.lower() <= "я" for char in text)
        for text in error["details"]["fields"].values()
    )


def test_missing_required_field():
    body = {
        key: value
        for key, value in BODIES["ApplicationCreate"].items()
        if key != "amount"
    }
    assert_validation(TestClient(app).post(CREATE, json=body), "amount")


def test_size_limit():
    assert_validation(TestClient(app).get("/api/v1/bank/applications?size=101"), "size")


def test_invalid_path_uuid():
    assert_validation(TestClient(app).get("/api/v1/applications/invalid"), "id")


@pytest.mark.parametrize("field", ["pdn", "bki"])
def test_required_consents_are_true(field):
    body = deepcopy(BODIES["SubmitRequest"])
    body["consents"][field] = False
    assert_validation(
        TestClient(app).post(f"/api/v1/applications/{ID}/submit", json=body),
        f"consents.{field}",
    )


def test_nullable_response_fields_remain_required():
    schema = app.openapi()["components"]["schemas"]
    assert "ApplicationClient" in schema
    client = schema["ApplicationClient"]
    assert set(client["properties"]) == set(client["required"])
    assert "risk_flags" not in client["properties"]


@pytest.mark.parametrize(
    "outcome,remove",
    [
        ("APPROVE", "amount"),
        ("APPROVE", "term_months"),
        ("COUNTER", "amount"),
        ("COUNTER", "term_months"),
        ("DECLINE", "client_reason_category"),
        ("REQUEST_INFO", "info_questions"),
    ],
)
def test_decision_conditional_required_fields(outcome, remove):
    body = deepcopy(BODIES["UnderwriterDecisionRequest"])
    body["outcome"] = outcome
    body.pop(remove, None)
    assert_validation(TestClient(app).post(DECIDE, json=body), "request")


@pytest.mark.parametrize("model", list(BODIES))
def test_all_request_schemas_forbid_extra_fields(model):
    from pydantic import ValidationError

    from app.schemas import api

    body = deepcopy(BODIES[model])
    body["unexpected"] = "field"
    with pytest.raises(ValidationError) as raised:
        getattr(api, model).model_validate(body)
    assert any(error["type"] == "extra_forbidden" for error in raised.value.errors())
