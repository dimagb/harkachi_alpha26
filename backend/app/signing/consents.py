"""Canonical consent documents, signatures and audit records."""

import calendar
import hashlib
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    Application,
    ApplicationEvent,
    Company,
    Consent,
    Party,
    Signature,
    User,
)


def sign_consents(
    session: Session,
    application: Application,
    company: Company,
    party: Party,
    user: User,
    auto_decision: bool,
    verified_at: datetime,
    signed_at: datetime,
) -> None:
    types = {"PDN": True, "BKI": True}
    if company.kind == "IP":
        types["AUTO_DECISION"] = auto_decision
    year = signed_at.year + 1
    expires_at = signed_at.replace(
        year=year, day=min(signed_at.day, calendar.monthrange(year, signed_at.month)[1])
    )
    for consent_type, granted in types.items():
        document = {
            "type": consent_type,
            "application_id": str(application.id),
            "number": application.number,
            "company_inn": company.inn,
            "user_id": str(user.id),
            "granted": granted,
            "signed_at": signed_at.isoformat(),
        }
        doc_hash = hashlib.sha256(
            json.dumps(document, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        consent = Consent(
            application_id=application.id,
            party_id=party.id,
            type=consent_type,
            granted=granted,
            signed_at=signed_at,
            expires_at=None if consent_type == "AUTO_DECISION" else expires_at,
            doc_hash=doc_hash,
        )
        session.add(consent)
        session.flush()
        session.add(
            Signature(
                application_id=application.id,
                party_id=party.id,
                object_type="CONSENT",
                object_id=consent.id,
                doc_hash=doc_hash,
                otp_verified_at=verified_at,
            )
        )
        session.add(
            ApplicationEvent(
                application_id=application.id,
                event_type="CONSENT_SIGNED",
                actor_type="CLIENT",
                actor_id=user.id,
                reason_code=None,
                payload={"type": consent_type, "granted": granted},
                created_at=signed_at,
            )
        )
