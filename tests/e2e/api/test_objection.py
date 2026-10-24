"""S-10: предприниматель оспаривает автоотказ и получает предложение."""

import httpx
import pytest
from client import ApiClient
from test_personas import find_persona, start_application


@pytest.fixture(scope="module", autouse=True)
def stand_ready():
    with ApiClient() as api:
        try:
            ready = api.http.get("ready")
        except httpx.RequestError:
            ready = None
        if ready is None or ready.status_code != 200:
            # TODO(lead): объединить проверку с StandModule в общем conftest.py
            # после B-09a; общий conftest не входит в разрешённые файлы карточки.
            pytest.skip(f"Стенд недоступен: {api.http.base_url}")


def test_ip_objection_reviewed(client, bank, persona_data):
    persona = find_persona(persona_data, "ip_bad")
    application, _ = start_application(client, persona)
    assert application["state"] == "DECLINED"
    assert "OBJECT" in application["allowed_actions"]
    app_id = application["id"]
    pending = client.objection(
        app_id, "Прошу пересмотреть решение: задолженность погашена"
    )
    assert pending["state"] == "MANUAL_REVIEW"
    assert pending["client_reason"] is None
    assert pending["objection"]["status"] == "PENDING"
    assert bank.bank_application(app_id)["objection"]["status"] == "PENDING"
    bank.decide(
        app_id,
        {
            "outcome": "APPROVE",
            "amount": application["amount"],
            "term_months": application["term_months"],
            "comment": "Проверены подтверждающие сведения, решение пересмотрено",
        },
    )
    resolved = client.get_application(app_id)
    assert resolved["state"] == "OFFER_ISSUED"
    assert resolved["offer"]["status"] == "ACTIVE"
    assert resolved["objection"]["status"] == "RESOLVED"
    assert (
        resolved["objection"]["outcome_text"]
        == "Специалист банка пересмотрел решение — смотрите предложение ниже"
    )
