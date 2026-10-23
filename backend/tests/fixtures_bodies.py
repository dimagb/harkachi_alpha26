"""Valid contract examples, shared by stub and validation tests."""

from uuid import uuid4

ID = str(uuid4())
BODIES = {
    "LoginRequest": {"login": "client", "password": "demo"},
    "CalculatorRequest": {
        "product_code": "EXPRESS",
        "amount": 500_000,
        "term_months": 12,
    },
    "ApplicationCreate": {
        "company_id": ID,
        "product_code": "EXPRESS",
        "amount": 500_000,
        "term_months": 12,
        "purpose": "WORKING_CAPITAL",
        "declared_revenue_year": 6_000_000,
    },
    "ApplicationPatch": {"amount": 600_000},
    "OtpRequest": {"purpose": "CONSENTS", "party_id": ID},
    "SubmitRequest": {
        "otp_id": ID,
        "code": "123456",
        "consents": {"pdn": True, "bki": True, "auto_decision": False},
    },
    "InfoResponseRequest": {
        "answers": [
            {"item_code": "PURPOSE_DETAILS", "comment": "Закупка оборудования"}
        ],
    },
    "AcceptOfferRequest": {"offer_version": 1},
    "SignRequest": {"otp_id": ID, "code": "123456", "party_id": ID},
    "ObjectionRequest": {"text": "Прошу повторно рассмотреть заявку"},
    "UnderwriterDecisionRequest": {
        "outcome": "APPROVE",
        "amount": 500_000,
        "term_months": 12,
        "comment": "Решение по заявке принято",
    },
    "TimeShiftRequest": {"application_id": ID, "days": 1},
}
