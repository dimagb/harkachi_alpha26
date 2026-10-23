"""PostgreSQL queue: atomic claims, committed steps, crash recovery."""

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.models import Job
from app.pipeline.steps import Providers, process_step

logger = logging.getLogger(__name__)


def recover_stale(session_factory: sessionmaker[Session]) -> int:
    with session_factory.begin() as session:
        recovered = list(
            session.scalars(
                update(Job)
                .where(
                    Job.status == "RUNNING",
                    Job.updated_at < datetime.now(UTC) - timedelta(seconds=60),
                )
                .values(status="PENDING")
                .returning(Job.id)
            )
        )
        return len(recovered)


def run_once(
    session_factory: sessionmaker[Session],
    providers: Providers,
    today: Callable[[], date],
) -> bool:
    with session_factory.begin() as session:
        job = session.scalar(
            select(Job)
            .where(Job.status == "PENDING", Job.run_after <= func.now())
            .order_by(Job.run_after)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return False
        job.status = "RUNNING"
        job.attempts += 1
        job.updated_at = datetime.now(UTC)
        job_id, application_id, step = job.id, job.application_id, job.step
    try:
        process_step(session_factory, application_id, step, providers, today)
    except Exception as error:
        # Exception messages (HTTP URLs, SQL parameters) can contain secrets.
        message = f"{type(error).__name__}: ошибка выполнения шага {step}"
        logger.error("Job %s failed: %s", job_id, message)
        with session_factory.begin() as session:
            job = session.get(Job, job_id)
            job.status, job.last_error = "FAILED", message
    else:
        with session_factory.begin() as session:
            job = session.get(Job, job_id)
            job.status, job.last_error = "DONE", None
    return True
