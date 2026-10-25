"""Best-effort, offline demo applications, isolated from the worker queue."""

import json
import logging
import time
from collections import Counter
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.integrations.bureau import FakeBureauProvider
from app.integrations.registry import FakeRegistryProvider
from app.integrations.tax import FakeTaxProvider
from app.models import Application, Company, Job, User
from app.offers.actions import withdraw
from app.pipeline.steps import Providers, process_step
from app.schemas.api import OtpRequest, SubmitRequest
from app.signing import otp
from app.signing.submit import submit

logger = logging.getLogger(__name__)


def providers_for(companies: list[dict]) -> Providers:
    return Providers(
        registry=FakeRegistryProvider(
            {
                p["inn"]: {
                    key: p[key]
                    for key in (
                        "inn",
                        "ogrn",
                        "kind",
                        "name",
                        "status",
                        "reg_date",
                        "okved_main",
                        "address",
                        "director",
                        "founders",
                    )
                }
                for p in companies
            }
        ),
        bureau=FakeBureauProvider(
            {p["inn"]: {"inn": p["inn"], "kind": "FULL", **p["bki"]} for p in companies}
        ),
        tax=FakeTaxProvider(
            {p["inn"]: {"inn": p["inn"], **p["fns"]} for p in companies}
        ),
    )


def drain(
    factory: sessionmaker[Session],
    application_id: UUID,
    providers: Providers,
    as_of: date,
    deadline: float,
) -> None:
    """Claim only this application's jobs; never consume another client's job."""
    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError
        with factory.begin() as session:
            job = session.scalar(
                select(Job)
                .where(
                    Job.application_id == application_id,
                    Job.status == "PENDING",
                )
                .order_by(Job.run_after)
                .with_for_update()
                .limit(1)
            )
            if job is None:
                return
            job.status = "RUNNING"
            job.attempts += 1
            identity, step = job.id, job.step
        process_step(factory, application_id, step, providers, lambda: as_of)
        with factory.begin() as session:
            session.get(Job, identity).status = "DONE"


def run_background(session_factory: sessionmaker[Session]) -> None:
    settings = get_settings()
    settings.pipeline_step_delay_sec = 0
    settings.source_retry_pause_sec = 0
    deadline = time.monotonic() + 45
    data = json.loads(settings.background_path.read_text("utf-8"))
    companies = data["companies"]
    providers = providers_for(companies)
    as_of = date.fromisoformat(data["_meta"]["as_of"])
    with session_factory() as session:
        existing = session.scalar(
            select(Application.id)
            .join(Company)
            .where(Company.inn.in_(p["inn"] for p in companies))
            .limit(1)
        )
        if existing is not None:
            logger.info("Фоновые заявки уже загружены")
            return
    created = mismatched = 0
    states = Counter()
    for company_data in companies:
        for item in company_data["demo"]["apps"]:
            if time.monotonic() >= deadline:
                logger.warning("Фоновые заявки: лимит 45 с")
                logger.info(
                    "Фоновые заявки: %s создано, %s по состояниям; не совпало: %s",
                    created,
                    dict(states),
                    mismatched,
                )
                return
            application_id = None
            with session_factory() as session:
                try:
                    company = session.scalars(
                        select(Company).where(Company.inn == company_data["inn"])
                    ).one()
                    user = session.scalars(
                        select(User).where(
                            User.login == company_data["users"][0]["login"]
                        )
                    ).one()
                    params = item["app"]
                    application = Application(
                        company_id=company.id,
                        created_by=user.id,
                        product_code=params["product"],
                        amount=params["amount"],
                        term_months=params["term"],
                        purpose=params["purpose"],
                        purpose_text=params.get("purpose_text"),
                        declared_revenue_year=params["declared_revenue_year"],
                    )
                    session.add(application)
                    session.commit()
                    application_id = application.id
                    created += 1
                    target = item["target_state"]
                    if target == "WITHDRAWN":
                        withdraw(session, application_id, user)
                    elif target != "DRAFT":
                        code = otp.issue(
                            session,
                            application_id,
                            OtpRequest(purpose="CONSENTS"),
                            user,
                        )
                        submit(
                            session,
                            application_id,
                            SubmitRequest(
                                otp_id=code.otp_id,
                                code=code.demo_code,
                                consents=item["consents"],
                            ),
                            user,
                        )
                        drain(
                            session_factory, application_id, providers, as_of, deadline
                        )
                    session.expire_all()
                    state = session.get(Application, application_id).state
                    states[state] += 1
                    mismatched += state != target
                except Exception:
                    session.rollback()
                    logger.warning("Фоновая заявка не проведена")
                    if application_id is not None:
                        # Failed work must not be picked up by the worker after migrate.
                        with session_factory.begin() as cleanup:
                            for job in cleanup.scalars(
                                select(Job).where(
                                    Job.application_id == application_id,
                                    Job.status.in_(("PENDING", "RUNNING")),
                                )
                            ):
                                job.status = "FAILED"
                                job.last_error = "Ошибка проведения фоновой заявки"
    logger.info(
        "Фоновые заявки: %s создано, %s по состояниям; не совпало: %s",
        created,
        dict(states),
        mismatched,
    )
