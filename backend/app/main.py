from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import auth_router, router
from app.config import get_settings
from app.db import engine
from app.errors import ApiError, register_error_handlers
from app.logging import CorrelationMiddleware, configure_logging

configure_logging(get_settings().log_level)


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"] = "ok"


app = FastAPI(
    title="Credit core",
    version="0.1.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
    redoc_url=None,
    swagger_ui_oauth2_redirect_url="/api/v1/docs/oauth2-redirect",
    separate_input_output_schemas=False,
)
register_error_handlers(app)
app.add_middleware(CorrelationMiddleware)
app.include_router(auth_router)
app.include_router(router)


@app.get("/api/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get(
    "/api/v1/ready",
    response_model=HealthResponse,
    responses={503: {"model": ApiError}},
)
def ready() -> HealthResponse:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable") from None
    return HealthResponse()
