"""Contract routes. Authentication and business logic belong to later tasks."""

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app.auth import service as auth_service
from app.catalog import calculator as calculator_service
from app.catalog.products import list_products
from app.companies import profile as profile_service
from app.db import get_session
from app.errors import ApiError, ApiErrorException, ErrorCode
from app.integrations.registry import RegistryProvider, get_registry_provider
from app.models import User
from app.schemas import api as s

bearer = HTTPBearer(auto_error=False, scheme_name="bearerAuth")
router = APIRouter(prefix="/api/v1", dependencies=[Depends(bearer)])
auth_router = APIRouter(prefix="/api/v1", tags=["Аутентификация"])


def authenticated_user(request: Request) -> User:
    # The common router dependency authenticates once, before any handler runs.
    return request.state.user


def client_user(user: Annotated[User, Depends(authenticated_user)]) -> User:
    from app.auth.deps import require_roles

    return require_roles("CLIENT")(user)


def underwriter_user(user: Annotated[User, Depends(authenticated_user)]) -> User:
    from app.auth.deps import require_roles

    return require_roles("UNDERWRITER")(user)


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
def login(body: s.LoginRequest, session: Annotated[Session, Depends(get_session)]):
    return auth_service.login(session, body.login, body.password)


@router.get(
    "/me",
    response_model=s.MeResponse,
    tags=["Аутентификация"],
    summary="Получить данные пользователя",
    responses=errors(401, 501),
)
def me(
    user: Annotated[User, Depends(authenticated_user)],
    session: Annotated[Session, Depends(get_session)],
):
    return auth_service.me(session, user)


@router.get(
    "/products",
    response_model=list[s.Product],
    tags=["Каталог и калькулятор"],
    summary="Получить кредитные продукты",
    responses=errors(401, 403, 501),
)
def products(
    user: Annotated[User, Depends(client_user)],
    session: Annotated[Session, Depends(get_session)],
):
    return list_products(session)


@router.post(
    "/calculator",
    response_model=s.CalculatorResponse,
    tags=["Каталог и калькулятор"],
    summary="Рассчитать условия кредита",
    responses=errors(401, 403, 422, 501),
)
def calculator(
    body: s.CalculatorRequest,
    user: Annotated[User, Depends(client_user)],
    session: Annotated[Session, Depends(get_session)],
):
    return calculator_service.calculate(session, body)


@router.get(
    "/companies/{id}/profile",
    response_model=s.CompanyProfile,
    tags=["Профиль компании"],
    summary="Получить профиль компании",
    responses=errors(401, 403, 404, 422, 501),
)
def company_profile(
    id: UUID,
    user: Annotated[User, Depends(client_user)],
    session: Annotated[Session, Depends(get_session)],
    registry: Annotated[RegistryProvider, Depends(get_registry_provider)],
):
    from app.auth.deps import member_company

    company, membership = member_company(id, user, session)
    return profile_service.company_profile(session, company, registry)


@router.post(
    "/applications",
    response_model=s.ApplicationClient,
    tags=["Заявки клиента"],
    summary="Создать заявку",
    responses=errors(401, 403, 404, 409, 422, 501),
)
def create_application(
    body: s.ApplicationCreate,
    user: Annotated[User, Depends(client_user)],
    session: Annotated[Session, Depends(get_session)],
):
    from app.applications import serializers, service

    return serializers.to_client(session, service.create(session, body, user), user)


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
    user: Annotated[User, Depends(client_user)],
    session: Annotated[Session, Depends(get_session)],
):
    from app.applications import serializers, service

    return serializers.to_client(
        session, service.patch(session, id, body, if_match, user), user
    )


@router.get(
    "/applications",
    response_model=list[s.ApplicationListItem],
    tags=["Заявки клиента"],
    summary="Получить заявки компании",
    responses=errors(401, 403, 404, 422, 501),
)
def applications(
    company_id: UUID,
    user: Annotated[User, Depends(client_user)],
    session: Annotated[Session, Depends(get_session)],
):
    from app.applications import serializers, service

    return [
        serializers.to_list_item(session, item, user)
        for item in service.list_applications(session, company_id, user)
    ]


@router.get(
    "/applications/{id}",
    response_model=s.ApplicationClient,
    tags=["Заявки клиента"],
    summary="Получить заявку",
    responses=errors(401, 403, 404, 422, 501),
)
def application(
    id: UUID,
    user: Annotated[User, Depends(client_user)],
    session: Annotated[Session, Depends(get_session)],
):
    from app.applications import serializers, service

    return serializers.to_client(session, service.get(session, id, user), user)


@router.post(
    "/applications/{id}/request-signature",
    response_model=s.ApplicationClient,
    tags=["Действия клиента"],
    summary="Запросить подпись",
    responses=errors(401, 403, 404, 409, 422, 501),
)
def request_signature(
    id: UUID,
    user: Annotated[User, Depends(client_user)],
    session: Annotated[Session, Depends(get_session)],
):
    from app.applications.serializers import to_client
    from app.signing.submit import request_signature

    return to_client(session, request_signature(session, id, user), user)


@router.post(
    "/applications/{id}/otp",
    response_model=s.OtpResponse,
    tags=["Действия клиента"],
    summary="Запросить код подтверждения",
    responses=errors(401, 403, 404, 409, 422, 501),
)
def otp(
    id: UUID,
    body: s.OtpRequest,
    user: Annotated[User, Depends(client_user)],
    session: Annotated[Session, Depends(get_session)],
):
    from app.signing.otp import issue

    return issue(session, id, body, user)


@router.post(
    "/applications/{id}/submit",
    response_model=s.ApplicationClient,
    tags=["Действия клиента"],
    summary="Подать заявку",
    responses=errors(401, 403, 404, 409, 422, 501),
)
def submit(
    id: UUID,
    body: s.SubmitRequest,
    user: Annotated[User, Depends(client_user)],
    session: Annotated[Session, Depends(get_session)],
):
    from app.applications.serializers import to_client
    from app.signing.submit import submit

    return to_client(session, submit(session, id, body, user), user)


@router.post(
    "/applications/{id}/info-response",
    response_model=s.ApplicationClient,
    tags=["Действия клиента"],
    summary="Ответить на запрос сведений",
    responses=errors(401, 403, 404, 409, 422, 501),
)
def info_response(
    id: UUID,
    body: s.InfoResponseRequest,
    user: Annotated[User, Depends(client_user)],
    session: Annotated[Session, Depends(get_session)],
):
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.applications.serializers import to_client
    from app.applications.state_machine import transition
    from app.models import InfoRequest, Job
    from app.signing.otp import locked_application, require_state

    application = locked_application(session, id, user)
    require_state(application, "INFO_REQUESTED")
    info = session.scalar(
        select(InfoRequest)
        .where(
            InfoRequest.application_id == application.id,
            InfoRequest.responded_at.is_(None),
        )
        .order_by(InfoRequest.created_at.desc(), InfoRequest.id.desc())
        .limit(1)
        .with_for_update()
    )
    codes = [answer.item_code for answer in body.answers]
    if (
        info is None
        or len(codes) != len(info.items)
        or codes != [item["item_code"] for item in info.items]
    ):
        raise ApiErrorException(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Ответьте на все вопросы банка",
            {"fields": {"answers": "Нужен один ответ на каждый пункт запроса"}},
        )
    for answer in body.answers:
        if answer.item_code == "REVENUE_CONFIRM":
            if answer.value is None or answer.value <= 0:
                raise ApiErrorException(
                    422,
                    ErrorCode.VALIDATION_ERROR,
                    "Укажите выручку больше нуля",
                    {"fields": {"value": "Выручка должна быть больше нуля"}},
                )
            application.declared_revenue_year = answer.value
    now = datetime.now(UTC)
    info.response = body.model_dump(mode="json", exclude_unset=True)["answers"]
    info.responded_at = now
    transition(
        session,
        application,
        "VALIDATION" if info.source == "SYSTEM" else "MANUAL_REVIEW",
        actor_type="CLIENT",
        actor_id=user.id,
        payload=None if info.source == "SYSTEM" else {"route_reason": "INFO_RESPONSE"},
    )
    if info.source == "SYSTEM":
        session.add(
            Job(
                application_id=application.id,
                step="VALIDATION",
                status="PENDING",
                attempts=0,
                run_after=now,
            )
        )
    session.commit()
    return to_client(session, application, user)


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
def underwriting_queue(
    user: Annotated[User, Depends(underwriter_user)],
    session: Annotated[Session, Depends(get_session)],
):
    from app.underwriting.queue import get_queue

    return get_queue(session)


@router.get(
    "/underwriting/applications/{id}",
    response_model=s.ApplicationBank,
    tags=["Андеррайтер и банк"],
    summary="Получить данные заявки для банка",
    responses=errors(401, 403, 404, 422, 501),
)
def underwriting_application(
    id: UUID,
    user: Annotated[User, Depends(underwriter_user)],
    session: Annotated[Session, Depends(get_session)],
):
    from app.underwriting.card import get_application, to_bank

    return to_bank(session, get_application(session, id), user)


@router.post(
    "/underwriting/{id}/decision",
    response_model=s.ApplicationBank,
    tags=["Андеррайтер и банк"],
    summary="Принять решение по заявке",
    responses=errors(401, 403, 404, 409, 422, 501),
)
def underwriting_decision(
    id: UUID,
    body: s.UnderwriterDecisionRequest,
    user: Annotated[User, Depends(underwriter_user)],
    session: Annotated[Session, Depends(get_session)],
):
    from app.underwriting.decide import make_decision

    return make_decision(session, id, body, user)


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
