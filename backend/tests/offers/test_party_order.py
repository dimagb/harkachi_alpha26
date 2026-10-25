"""The client signs the loan before the guarantee regardless of random UUIDs."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pipeline.test_pipeline import drain, providers_for
from sqlalchemy import event, select
from test_application_offer_view import client_for, completed

from app.models import Application, Party


@pytest.mark.parametrize("borrower_first_by_id", [False, True])
@pytest.mark.parametrize("borrower_created_later", [False, True])
def test_ooo_load_signs_loan_before_guarantee(
    actions_factory, persona_data, borrower_first_by_id, borrower_created_later
):
    earlier_id = UUID("00000000-0000-0000-0000-000000000001")
    later_id = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    created_at = datetime(2026, 10, 25, tzinfo=UTC)

    def fixed_sort_keys(mapper, connection, party):
        is_borrower = party.role == "BORROWER_SIGNATORY"
        party.id = earlier_id if is_borrower == borrower_first_by_id else later_id
        party.created_at = created_at + timedelta(
            seconds=int(is_borrower and borrower_created_later)
        )

    event.listen(Party, "before_insert", fixed_sort_keys)
    try:
        app_id, _ = completed(actions_factory, persona_data, "ooo_load")
    finally:
        event.remove(Party, "before_insert", fixed_sort_keys)

    with client_for(actions_factory, "ooo_load") as client:
        response = client.post(
            f"/api/v1/applications/{app_id}/offer/accept",
            json={"offer_version": 1},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert [p["role"] for p in data["parties"]] == [
            "BORROWER_SIGNATORY",
            "GUARANTOR",
        ]
        for role, purpose, state in (
            ("BORROWER_SIGNATORY", "OFFER", "SIGNING"),
            ("GUARANTOR", "GUARANTEE", "SIGNED"),
        ):
            party = next(p for p in data["parties"] if p["is_me"] and not p["signed"])
            assert party["role"] == role
            response = client.post(
                f"/api/v1/applications/{app_id}/otp",
                json={"purpose": purpose, "party_id": party["id"]},
            )
            assert response.status_code == 200, response.text
            issued = response.json()
            response = client.post(
                f"/api/v1/applications/{app_id}/sign",
                json={
                    "party_id": party["id"],
                    "otp_id": issued["otp_id"],
                    "code": issued["demo_code"],
                },
            )
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["state"] == state

    drain(actions_factory, providers_for(persona_data), persona_data)
    with actions_factory() as session:
        assert session.get(Application, app_id).state == "DISBURSED"


def test_client_and_bank_order_parties_by_role_then_created_at_and_id(
    actions_factory, persona_data
):
    app_id, _ = completed(actions_factory, persona_data, "ooo_load")
    created_at = datetime(2026, 10, 25, tzinfo=UTC)
    expected_ids = []
    with actions_factory.begin() as session:
        for role, first_id in (("BORROWER_SIGNATORY", 1), ("GUARANTOR", 3)):
            original = session.scalar(
                select(Party).where(Party.application_id == app_id, Party.role == role)
            )
            original.created_at = created_at + timedelta(seconds=1)
            # Insert the UUID tie in reverse order; original has a later date.
            for number in (first_id + 1, first_id):
                session.add(
                    Party(
                        id=UUID(int=number),
                        application_id=app_id,
                        role=role,
                        user_id=original.user_id,
                        full_name=original.full_name,
                        created_at=created_at,
                    )
                )
            expected_ids.extend(
                [str(UUID(int=first_id)), str(UUID(int=first_id + 1)), str(original.id)]
            )

    for login, path in (
        ("ooo_load", f"/api/v1/applications/{app_id}"),
        ("bank_b09a", f"/api/v1/underwriting/applications/{app_id}"),
    ):
        with client_for(actions_factory, login) as client:
            response = client.get(path)
        assert response.status_code == 200, response.text
        assert [p["id"] for p in response.json()["parties"]] == expected_ids
