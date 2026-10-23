"""Contract routes. Authentication and business logic belong to later tasks."""

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.security import HTTPBearer

from app.errors import ApiError, ApiErrorException, ErrorCode
from app.schemas import api as s

bearer = HTTPBearer(auto_error=False, scheme_name="bearerAuth")
router = APIRouter(prefix="/api/v1", dependencies=[Depends(bearer)])
auth_router = APIRouter(prefix="/api/v1", tags=["Аутентификация"])


def errors(*codes: int) -> dict:
    return {code: {"model": ApiError} for code in codes}


def not_implemented() -> NoReturn:
    raise ApiErrorException(
        501, ErrorCode.NOT_IMPLEMENTED, "Эндпоинт ещё не реализован"
    )


@auth_router.post(
    "/auth/login",
    response_model=s.LoginResponse,
    summary="Войти в кабинет",
    responses=errors(422, 501),
)
def login(body: s.LoginRequest):
    not_implemented()


@router.get(
    "/me",
    response_model=s.MeResponse,
    tags=["Аутентификация"],
    summary="Получить данные пользователя",
    responses=errors(401, 501),
)
def me():
    not_implemented()


@router.get(
    "/products",
    response_model=list[s.Product],
    tags=["Каталог и калькулятор"],
    summary="Получить кредитные продукты",
    responses=errors(401, 403, 501),
)
def products():
    not_implemented()


@router.post(
    "/calculator",
    response_model=s.CalculatorResponse,
    tags=["Каталог и калькулятор"],
    summary="Рассчитать условия кредита",
    responses=errors(401, 403, 422, 501),
)
def calculator(body: s.CalculatorRequest):
    not_implemented()


@router.get(
    "/companies/{id}/profile",
    response_model=s.CompanyProfile,
    tags=["Профиль компании"],
    summary="Получить профиль компании",
    responses=errors(401, 403, 404, 422, 501),
)
def company_profile(id: UUID):
    not_implemented()


@router.post(
    "/applications",
    response_model=s.ApplicationClient,
    tags=["Заявки клиента"],
    summary="Создать заявку",
    responses=errors(401, 403, 409, 422, 501),
)
def create_application(body: s.ApplicationCreate):
    not_implemented()


@router.patch(
    "/applications/{id}",
    response_model=s.ApplicationClient,
    tags=["Заявки клиента"],
    summary="Изменить черновик заявки",
    responses=errors(401, 403, 404, 409, 422, 501),
)
def patch_application(
    id: UUID,
    body: s.ApplicationPatch,
    if_match: Annotated[int, Header(alias="If-Match")],
):
    not_implemented()


@router.get(
    "/applications",
    response_model=list[s.ApplicationListItem],
    tags=["Заявки клиента"],
    summary="Получить заявки компании",
    responses=errors(401, 403, 422, 501),
)
def applications(company_id: UUID):
    not_implemented()


@router.get(
    "/applications/{id}",
    response_model=s.ApplicationClient,
    tags=["Заявки клиента"],
    summary="Получить заявку",
    responses=errors(401, 403, 404, 422, 501),
)
def application(id: UUID):
    not_implemented()


@router.post(
    "/applications/{id}/request-signature",
    response_model=s.ApplicationClient,
    tags=["Действия клиента"],
    summary="Запросить подпись",
    responses=errors(401, 403, 404, 409, 422, 501),
)
def request_signature(id: UUID):
    not_implemented()


@router.post(
    "/applications/{id}/otp",
    response_model=s.OtpResponse,
    tags=["Действия клиента"],
    summary="Запросить код подтверждения",
    responses=errors(401, 403, 404, 422, 501),
)
def otp(id: UUID, body: s.OtpRequest):
    not_implemented()


@router.post(
    "/applications/{id}/submit",
    response_model=s.ApplicationClient,
    tags=["Действия клиента"],
    summary="Подать заявку",
    responses=errors(401, 403, 404, 409, 422, 501),
)
def submit(id: UUID, body: s.SubmitRequest):
    not_implemented()


@router.post(
    "/applications/{id}/info-response",
    response_model=s.ApplicationClient,
    tags=["Действия клиента"],
    summary="Ответить на запрос сведений",
    responses=errors(401, 403, 404, 409, 422, 501),
)
def info_response(id: UUID, body: s.InfoResponseRequest):
    not_implemented()


@router.post(
    "/applications/{id}/offer/accept",
    response_model=s.ApplicationClient,
    tags=["Действия клиента"],
    summary="Принять предложение",
    responses=errors(401, 403, 404, 409, 422, 501),
)
def accept_offer(id: UUID, body: s.AcceptOfferRequest):
    not_implemented()


@router.post(
    "/applications/{id}/offer/reject",
    response_model=s.ApplicationClient,
    tags=["Действия клиента"],
    summary="Отклонить предложение",
    responses=errors(401, 403, 404, 409, 422, 501),
)
def reject_offer(id: UUID):
    not_implemented()


@router.post(
    "/applications/{id}/sign",
    response_model=s.ApplicationClient,
    tags=["Действия клиента"],
    summary="Подписать документы",
    responses=errors(401, 403, 404, 409, 422, 501),
)
def sign(id: UUID, body: s.SignRequest):
    not_implemented()


@router.post(
    "/applications/{id}/withdraw",
    response_model=s.ApplicationClient,
    tags=["Действия клиента"],
    summary="Отозвать заявку",
    responses=errors(401, 403, 404, 409, 422, 501),
)
def withdraw(id: UUID):
    not_implemented()


@router.post(
    "/applications/{id}/objection",
    response_model=s.ApplicationClient,
    tags=["Действия клиента"],
    summary="Подать возражение",
    responses=errors(401, 403, 404, 409, 422, 501),
)
def objection(id: UUID, body: s.ObjectionRequest):
    not_implemented()


@router.get(
    "/underwriting/queue",
    response_model=list[s.QueueItem],
    tags=["Андеррайтер и банк"],
    summary="Получить очередь заявок",
    responses=errors(401, 403, 501),
)
def underwriting_queue():
    not_implemented()


@router.get(
    "/underwriting/applications/{id}",
    response_model=s.ApplicationBank,
    tags=["Андеррайтер и банк"],
    summary="Получить данные заявки для банка",
    responses=errors(401, 403, 404, 422, 501),
)
def underwriting_application(id: UUID):
    not_implemented()


@router.post(
    "/underwriting/{id}/decision",
    response_model=s.ApplicationBank,
    tags=["Андеррайтер и банк"],
    summary="Принять решение по заявке",
    responses=errors(401, 403, 404, 409, 422, 501),
)
def underwriting_decision(id: UUID, body: s.UnderwriterDecisionRequest):
    not_implemented()


@router.get(
    "/bank/applications",
    response_model=s.Page[s.BankListItem],
    tags=["Андеррайтер и банк"],
    summary="Получить список заявок банка",
    responses=errors(401, 403, 422, 501),
)
def bank_applications(
    state: s.ApplicationState | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    not_implemented()


@router.post(
    "/demo/time-shift",
    response_model=s.TimeShiftResponse,
    tags=["Служебное"],
    summary="Сдвинуть сроки заявки для демонстрации",
    responses=errors(401, 403, 409, 422, 501),
)
def time_shift(body: s.TimeShiftRequest):
    not_implemented()
