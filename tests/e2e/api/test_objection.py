"""S-10: предприниматель оспаривает автоотказ и получает предложение."""

from test_personas import find_persona, start_application


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
