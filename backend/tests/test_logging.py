import logging

import pytest

from app.logging import configure_logging


@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
@pytest.mark.parametrize("name", ["httpx", "httpcore"])
def test_transport_logs_hide_request_urls(level, name, monkeypatch, capsys):
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", root.handlers[:])
    monkeypatch.setattr(root, "level", root.level)
    for logger_name in (
        "httpx",
        "httpcore",
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
    ):
        logger = logging.getLogger(logger_name)
        monkeypatch.setattr(logger, "handlers", logger.handlers[:])
        monkeypatch.setattr(logger, "propagate", logger.propagate)
        monkeypatch.setattr(logger, "level", logging.DEBUG)

    configure_logging(level)
    logger = logging.getLogger(name)
    assert logger.level >= logging.WARNING
    assert root.level == logging.getLevelName(level)
    logger.info("HTTP Request: GET http://mocks:8001/mock/v1/registry/private")
    logger.warning("Transport warning")
    output = capsys.readouterr().err
    assert "mock/v1/registry" not in output
    assert "Transport warning" in output
