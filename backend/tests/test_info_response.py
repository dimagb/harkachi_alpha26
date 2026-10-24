from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from pipeline.test_pipeline import assert_expected, drain, providers_for
from sqlalchemy import select
from test_application_offer_view import client_for, completed
from test_application_offer_view import persona_data as persona_data
from test_application_offer_view import pipeline_factory as pipeline_factory

from app.models import Application, ApplicationEvent, InfoRequest, Job


def test_gap_response_restarts_pipeline(pipeline_factory, persona_data):
    application_id, persona = completed(pipeline_factory, persona_data, "ooo_gap")
    body = {"answers": persona["demo"]["info_response"]}
    with client_for(pipeline_factory, "ooo_gap") as client:
        response = client.post(
            f"/api/v1/applications/{application_id}/info-response", json=body
        )
        assert response.status_code == 200, response.text
        assert response.json()["state"] == "VALIDATION"
        assert response.json()["info_request"] is None
        assert (
            client.post(
                f"/api/v1/applications/{application_id}/info-response", json=body
            ).status_code
            == 409
        )
    with pipeline_factory() as session:
        request = session.scalar(
            select(InfoRequest).where(InfoRequest.application_id == application_id)
        )
        assert request.response == body["answers"]
        assert request.responded_at is not None
        application = session.get(Application, application_id)
        assert application.declared_revenue_year == body["answers"][0]["value"]
        job = session.scalar(
            select(Job).where(
                Job.application_id == application_id, Job.status == "PENDING"
            )
        )
        assert job.step == "VALIDATION"
        event = session.scalar(
            select(ApplicationEvent).where(
                ApplicationEvent.application_id == application_id,
                ApplicationEvent.from_state == "INFO_REQUESTED",
            )
        )
        assert event.actor_type == "CLIENT"
        assert event.actor_id == application.created_by
    drain(pipeline_factory, providers_for(persona_data), persona_data)
    with client_for(pipeline_factory, "ooo_gap") as client:
        assert (
            client.get(f"/api/v1/applications/{application_id}").json()["info_request"]
            is None
        )
    with pipeline_factory() as session:
        assert_expected(
            session,
            application_id,
            persona["demo"]["expected"]["after_info"],
            persona_data["_meta"]["as_of"],
        )


@pytest.mark.parametrize(
    "invalid,field",
    [
        ("missing", "answers"),
        ("too_many", "answers"),
        ("extra", "answers"),
        ("no_value", "value"),
        ("zero", "value"),
        ("negative", "value"),
        ("no_comment", "comment"),
        ("short_comment", "comment"),
    ],
)
def test_invalid_answers_are_atomic(pipeline_factory, persona_data, invalid, field):
    application_id, persona = completed(pipeline_factory, persona_data, "ooo_gap")
    body = {"answers": deepcopy(persona["demo"]["info_response"])}
    if invalid == "missing":
        body["answers"] = []
    elif invalid == "too_many":
        # Two answers for one item are invalid; repeated item codes themselves
        # are permitted when the request contains two matching questions.
        body["answers"] *= 2
    elif invalid == "extra":
        body["answers"].append({"item_code": "PURPOSE_DETAILS", "comment": "Пояснение"})
    elif invalid == "no_value":
        body["answers"][0].pop("value")
    elif invalid in {"zero", "negative"}:
        body["answers"][0]["value"] = 0 if invalid == "zero" else -1
    elif invalid == "no_comment":
        body["answers"][0].pop("comment")
    else:
        body["answers"][0]["comment"] = "ab"
    with client_for(pipeline_factory, "ooo_gap") as client:
        response = client.post(
            f"/api/v1/applications/{application_id}/info-response", json=body
        )
    assert response.status_code == 422, response.text
    fields = response.json()["error"]["details"]["fields"]
    assert any(key == field or key.endswith(f".{field}") for key in fields)
    with pipeline_factory() as session:
        assert session.get(Application, application_id).state == "INFO_REQUESTED"
        request = session.scalar(
            select(InfoRequest).where(InfoRequest.application_id == application_id)
        )
        assert request.response is None and request.responded_at is None
        assert not session.scalars(
            select(Job).where(
                Job.application_id == application_id, Job.status == "PENDING"
            )
        ).all()


def test_underwriter_response_routes_to_review(pipeline_factory, persona_data):
    application_id, _ = completed(pipeline_factory, persona_data, "ooo_border")
    from app.applications.state_machine import transition

    with pipeline_factory.begin() as session:
        application = session.get(Application, application_id)
        transition(
            session,
            application,
            "INFO_REQUESTED",
            actor_type="UNDERWRITER",
            actor_id=None,
        )
        session.add(
            InfoRequest(
                application_id=application_id,
                source="UNDERWRITER",
                items=[
                    {
                        "item_code": "UNDERWRITER_QUESTION",
                        "question": "На что нужны деньги?",
                        "requires_value": False,
                    },
                    {
                        "item_code": "UNDERWRITER_QUESTION",
                        "question": "Как будете возвращать кредит?",
                        "requires_value": False,
                    },
                ],
                due_at=datetime.now(UTC) + timedelta(days=2),
            )
        )
    body = {
        "answers": [
            {"item_code": "UNDERWRITER_QUESTION", "comment": "На закупку товара"},
            {
                "item_code": "UNDERWRITER_QUESTION",
                "comment": "Из поступлений от продаж",
            },
        ]
    }
    with client_for(pipeline_factory, "ooo_border") as client:
        response = client.post(
            f"/api/v1/applications/{application_id}/info-response", json=body
        )
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "MANUAL_REVIEW"
    assert response.json()["info_request"] is None
    with pipeline_factory() as session:
        request = session.scalar(
            select(InfoRequest).where(InfoRequest.application_id == application_id)
        )
        assert request.response == body["answers"]
        event = session.scalar(
            select(ApplicationEvent).where(
                ApplicationEvent.application_id == application_id,
                ApplicationEvent.from_state == "INFO_REQUESTED",
            )
        )
        assert event.payload == {"route_reason": "INFO_RESPONSE"}
        assert event.reason_code is None and event.actor_type == "CLIENT"
        assert not session.scalars(
            select(Job).where(
                Job.application_id == application_id, Job.status == "PENDING"
            )
        ).all()


@pytest.mark.parametrize(
    "state",
    [
        "DRAFT",
        "SUBMITTED",
        "VALIDATION",
        "ENRICHMENT",
        "ASSESSMENT",
        "MANUAL_REVIEW",
        "OFFER_ISSUED",
        "DECLINED",
        "SIGNING",
        "SIGNED",
        "DISBURSED",
        "WITHDRAWN",
        "EXPIRED",
    ],
)
def test_open_request_is_hidden_outside_info_requested(
    pipeline_factory, persona_data, state
):
    application_id, _ = completed(pipeline_factory, persona_data, "ooo_gap")
    with pipeline_factory.begin() as session:
        # Preserve an unanswered request to exercise the state guard itself.
        session.get(Application, application_id).state = state
    with client_for(pipeline_factory, "ooo_gap") as client:
        response = client.get(f"/api/v1/applications/{application_id}")
    assert response.status_code == 200, response.text
    assert response.json()["info_request"] is None


def test_wrong_state_and_access(pipeline_factory, persona_data):
    application_id, _ = completed(pipeline_factory, persona_data, "ip_good")
    body = {"answers": []}
    with client_for(pipeline_factory, "ip_good") as client:
        assert (
            client.post(
                f"/api/v1/applications/{application_id}/info-response", json=body
            ).status_code
            == 409
        )
    with client_for(pipeline_factory, "ip_bad") as client:
        # Both operations conceal applications belonging to another company.
        assert client.get(f"/api/v1/applications/{application_id}").status_code == 404
        assert (
            client.post(
                f"/api/v1/applications/{application_id}/info-response", json=body
            ).status_code
            == 404
        )
