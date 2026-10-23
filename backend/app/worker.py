import logging
import signal
from datetime import date
from pathlib import Path
from threading import Event

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.integrations.bureau import get_bureau_provider
from app.integrations.registry import get_registry_provider
from app.integrations.tax import get_tax_provider
from app.logging import configure_logging
from app.pipeline.queue import recover_stale, run_once
from app.pipeline.steps import Providers

HEARTBEAT_PATH = Path("/tmp/worker-heartbeat")


def heartbeat() -> None:
    HEARTBEAT_PATH.touch()


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    stopped = Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.set())
    logger = logging.getLogger("app.worker")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    factory = sessionmaker(engine)
    providers = Providers(
        get_registry_provider(), get_bureau_provider(), get_tax_provider(), heartbeat
    )
    # TODO(lead): демо-часы B-10.
    today = date.today
    try:
        heartbeat()
        recover_stale(factory)
        while not stopped.is_set():
            heartbeat()
            try:
                processed = run_once(factory, providers, today)
            except Exception as error:
                logger.error("Worker iteration failed: %s", type(error).__name__)
                processed = False
            if not processed:
                stopped.wait(0.5)
    finally:
        HEARTBEAT_PATH.unlink(missing_ok=True)
        engine.dispose()
    logger.info("worker stopped")


if __name__ == "__main__":
    main()
