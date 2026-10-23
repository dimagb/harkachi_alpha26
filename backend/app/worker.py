import logging
import signal
from pathlib import Path
from threading import Event

from app.config import get_settings
from app.logging import configure_logging

HEARTBEAT_PATH = Path("/tmp/worker-heartbeat")


def main() -> None:
    configure_logging(get_settings().log_level)
    stopped = Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.set())
    logger = logging.getLogger("app.worker")
    while not stopped.is_set():
        HEARTBEAT_PATH.touch()
        logger.info("worker heartbeat")
        stopped.wait(5)
    HEARTBEAT_PATH.unlink(missing_ok=True)
    logger.info("worker stopped")


if __name__ == "__main__":
    main()
