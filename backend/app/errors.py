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
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: ErrorCode
    message: str
    details: dict[str, Any]


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: ErrorBody


class ApiErrorException(Exception):
    def __init__(
        self,
        status: int,
        code: ErrorCode,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def validation_message(item: dict) -> str:
    context = item.get("ctx", {})
    messages = {
        "missing": "Заполните обязательное поле",
        "string_too_short": f"Введите не менее {context.get('min_length')} символов",
        "string_too_long": f"Введите не более {context.get('max_length')} символов",
        "greater_than": f"Укажите значение больше {context.get('gt')}",
        "greater_than_equal": f"Укажите значение не меньше {context.get('ge')}",
        "less_than_equal": f"Укажите значение не больше {context.get('le')}",
        "literal_error": "Выберите допустимое значение",
        "extra_forbidden": "Неизвестное поле",
        "uuid_parsing": "Укажите корректный идентификатор",
        "int_parsing": "Укажите целое число",
        "int_from_float": "Укажите целое число",
        "too_short": f"Укажите не менее {context.get('min_length')} элементов",
        "too_long": f"Укажите не более {context.get('max_length')} элементов",
    }
    if item["type"] == "value_error":
        return str(context.get("error", "Проверьте значение поля"))
    return messages.get(item["type"], "Проверьте значение поля")


def error_response(
    status: int,
    code: ErrorCode,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    if code == ErrorCode.INTERNAL_ERROR:
        message = "Внутренняя ошибка сервера"
    return JSONResponse(
        status_code=status,
        content=ApiError(
            error=ErrorBody(code=code, message=message, details=details or {})
        ).model_dump(mode="json"),
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiErrorException)
    async def api_error(request: Request, exc: ApiErrorException) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message, exc.details)

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
        messages = {
            401: "Войдите в кабинет",
            403: "Недостаточно прав",
            404: "Запрошенные данные не найдены",
            405: "Действие не найдено",
            409: "Действие недоступно в текущем состоянии",
            422: "Проверьте заполнение полей",
            503: "Сервис временно недоступен",
        }
        message = messages.get(exc.status_code, "Внутренняя ошибка сервера")
        return error_response(exc.status_code, code, message, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = {
            ".".join(str(part) for part in item["loc"][1:])
            or "request": validation_message(item)
            for item in exc.errors()
        }
        return error_response(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Проверьте заполнение полей",
            {"fields": fields},
        )

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("app.errors").error("Unhandled request exception")
        return error_response(
            500, ErrorCode.INTERNAL_ERROR, "Внутренняя ошибка сервера"
        )
