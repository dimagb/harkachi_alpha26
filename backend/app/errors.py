import logging
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    CONFLICT_VERSION = "CONFLICT_VERSION"
    OFFER_EXPIRED = "OFFER_EXPIRED"
    SIGN_NOT_ALLOWED = "SIGN_NOT_ALLOWED"
    OTP_INVALID = "OTP_INVALID"
    OBJECTION_NOT_ALLOWED = "OBJECTION_NOT_ALLOWED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: ErrorCode
    message: str
    details: dict[str, Any]


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: ErrorBody


def error_response(
    status: int,
    code: ErrorCode,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ApiError(
            error=ErrorBody(code=code, message=message, details=details or {})
        ).model_dump(mode="json"),
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        codes = {
            401: ErrorCode.UNAUTHORIZED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            405: ErrorCode.NOT_FOUND,
            409: ErrorCode.INVALID_TRANSITION,
            422: ErrorCode.VALIDATION_ERROR,
            503: ErrorCode.SERVICE_UNAVAILABLE,
        }
        code = codes.get(
            exc.status_code,
            ErrorCode.INTERNAL_ERROR if exc.status_code >= 500 else ErrorCode.NOT_FOUND,
        )
        message = (
            "Internal server error"
            if exc.status_code >= 500 and exc.status_code != 503
            else str(exc.detail)
        )
        return error_response(exc.status_code, code, message, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = {
            ".".join(str(part) for part in item["loc"][1:]) or "request": item["msg"]
            for item in exc.errors()
        }
        return error_response(
            422, ErrorCode.VALIDATION_ERROR, "Validation failed", {"fields": fields}
        )

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("app.errors").error("Unhandled request exception")
        return error_response(500, ErrorCode.INTERNAL_ERROR, "Internal server error")
