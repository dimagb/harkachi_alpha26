import json
import logging
import time
from contextvars import ContextVar
from datetime import UTC, datetime
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "ts": datetime.now(UTC).isoformat(),
                "level": record.levelname,
                "msg": record.getMessage(),
                "correlation_id": getattr(
                    record, "correlation_id", correlation_id.get()
                ),
                "path": getattr(record, "path", None),
                "status": getattr(record, "status", None),
                "duration_ms": getattr(record, "duration_ms", None),
            },
            ensure_ascii=False,
        )


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True


class CorrelationMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        request_id = headers.get(b"x-correlation-id", b"").decode("latin-1") or str(
            uuid4()
        )
        token = correlation_id.set(request_id)
        started = time.perf_counter()
        status = 500
        response_started = False

        async def send_with_id(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                message["headers"] = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-correlation-id"
                ] + [(b"x-correlation-id", request_id.encode("latin-1"))]
            await send(message)

        try:
            try:
                await self.app(scope, receive, send_with_id)
            except Exception:
                if response_started:
                    raise
                from app.errors import ErrorCode, error_response

                logging.getLogger("app.http").error("Unhandled request exception")
                response = error_response(
                    500, ErrorCode.INTERNAL_ERROR, "Internal server error"
                )
                await response(scope, receive, send_with_id)
        finally:
            logging.getLogger("app.http").info(
                "request completed",
                extra={
                    "path": scope["path"],
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            correlation_id.reset(token)
