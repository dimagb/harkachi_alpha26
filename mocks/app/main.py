import asyncio
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.data import Company, generate_company, load_companies, valid_inn
from app.schemas import (
    ApiError,
    BkiFullResponse,
    BkiInfoResponse,
    BkiRequest,
    ErrorDetail,
    FnsResponse,
    HealthResponse,
    RegistryResponse,
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    root = Path(os.environ.get("DATA_ROOT", Path(__file__).resolve().parents[2]))
    application.state.companies = load_companies(root)
    application.state.failure_inns = {
        value.strip()
        for value in os.getenv("MOCK_FAILURE_INN", "").split(",")
        if value.strip()
    }
    application.state.latency = max(0, int(os.getenv("MOCK_LATENCY_MS", "300"))) / 1000
    yield


app = FastAPI(
    title="External mocks",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    codes = {403: "FORBIDDEN", 503: "SERVICE_UNAVAILABLE"}
    messages = {
        403: "Для полного кредитного отчёта требуется согласие.",
        503: "Источник временно недоступен. Повторите запрос позже.",
    }
    error = ApiError(
        error=ErrorDetail(
            code=codes.get(exc.status_code, "NOT_FOUND"),
            message=messages.get(exc.status_code, "Сведения не найдены."),
            details={},
        )
    )
    return JSONResponse(status_code=exc.status_code, content=error.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    fields = {
        ".".join(str(part) for part in item["loc"][1:]): "Проверьте значение поля."
        for item in exc.errors()
    }
    error = ApiError(
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message="Проверьте данные запроса.",
            details={"fields": fields},
        )
    )
    return JSONResponse(status_code=422, content=error.model_dump())


async def company_for(request: Request, inn: str) -> Company:
    # На Windows asyncio может проснуться раньше из-за дискретности часов.
    deadline = time.perf_counter() + request.app.state.latency
    while (remaining := deadline - time.perf_counter()) > 0:
        await asyncio.sleep(remaining)
    if inn in request.app.state.failure_inns:
        raise HTTPException(status_code=503)
    if not valid_inn(inn):
        raise HTTPException(status_code=404)
    company = request.app.state.companies.get(inn)
    return company if company is not None else generate_company(inn)


@app.get("/mock/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/mock/v1/registry/{inn}", response_model=RegistryResponse)
async def registry(inn: str, request: Request) -> RegistryResponse:
    return (await company_for(request, inn)).registry


@app.post("/mock/v1/bki/report", response_model=BkiInfoResponse | BkiFullResponse)
async def bki_report(body: BkiRequest, request: Request):
    company = await company_for(request, body.inn)
    if body.kind == "FULL":
        if not body.consent_id or not body.consent_id.strip():
            raise HTTPException(status_code=403)
        return company.bki
    return BkiInfoResponse(inn=body.inn, summary=company.bki.summary)


@app.get("/mock/v1/fns/check/{inn}", response_model=FnsResponse)
async def fns_check(inn: str, request: Request) -> FnsResponse:
    return (await company_for(request, inn)).fns
