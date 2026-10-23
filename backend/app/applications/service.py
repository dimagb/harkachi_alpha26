"""Application ownership, draft validation and optimistic concurrency."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.auth.deps import member_company
from app.catalog.calculator import validate_terms
from app.catalog.products import PRODUCT_CATALOG
from app.errors import ApiErrorException
from app.models import Application, ApplicationEvent, CompanyMember, User
from app.schemas.api import ApplicationCreate, ApplicationPatch

VERSION_MESSAGE = "Заявку изменили в другом окне — обновите страницу"


def _company_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as error:
        raise ApiErrorException(404, "NOT_FOUND", "Компания не найдена") from error


def _validate(session: Session, body: ApplicationCreate) -> None:
    validate_terms(session, body.product_code, body.amount, body.term_months)
    if body.purpose not in PRODUCT_CATALOG[body.product_code][0]:
        raise ApiErrorException(
            422,
            "VALIDATION_ERROR",
            "Проверьте заполнение полей",
            {"fields": {"purpose": "Эта цель недоступна для выбранного продукта"}},
        )
    if body.purpose == "OTHER" and body.purpose_text is None:
        raise ApiErrorException(
            422,
            "VALIDATION_ERROR",
            "Проверьте заполнение полей",
            {"fields": {"purpose_text": "Укажите цель кредита"}},
        )


def create(session: Session, body: ApplicationCreate, user: User) -> Application:
    company_id = _company_id(body.company_id)
    member_company(company_id, user, session)
    _validate(session, body)
    # The model default initializes DRAFT; all subsequent state writes use transition.
    application = Application(
        **{**body.model_dump(), "company_id": company_id}, created_by=user.id
    )
    session.add(application)
    session.flush()
    session.add(
        ApplicationEvent(
            application_id=application.id,
            event_type="STATE_CHANGED",
            from_state=None,
            to_state="DRAFT",
            actor_type="CLIENT",
            actor_id=user.id,
            payload={},
            created_at=datetime.now(UTC),
        )
    )
    session.commit()
    return application


def get(session: Session, application_id: UUID, user: User) -> Application:
    application = session.scalar(
        select(Application)
        .join(CompanyMember, CompanyMember.company_id == Application.company_id)
        .where(Application.id == application_id, CompanyMember.user_id == user.id)
    )
    if application is None:
        raise ApiErrorException(404, "NOT_FOUND", "Заявка не найдена")
    return application


def patch(
    session: Session,
    application_id: UUID,
    body: ApplicationPatch,
    version: int,
    user: User,
) -> Application:
    application = get(session, application_id, user)
    if version != application.version:
        raise ApiErrorException(409, "CONFLICT_VERSION", VERSION_MESSAGE)
    if application.state != "DRAFT":
        raise ApiErrorException(
            409, "INVALID_TRANSITION", "Действие недоступно в текущем состоянии заявки"
        )
    editable = (
        "product_code",
        "amount",
        "term_months",
        "purpose",
        "purpose_text",
        "declared_revenue_year",
    )
    values = {field: getattr(application, field) for field in editable}
    values.update(body.model_dump(exclude_unset=True, include=set(editable)))
    if application.purpose == "OTHER" and values["purpose"] != "OTHER":
        values["purpose_text"] = None
    try:
        merged = ApplicationCreate(company_id=str(application.company_id), **values)
    except ValidationError as error:
        fields = {
            ".".join(map(str, item["loc"])): "Проверьте значение поля"
            for item in error.errors()
        }
        raise ApiErrorException(
            422, "VALIDATION_ERROR", "Проверьте заполнение полей", {"fields": fields}
        ) from error
    _validate(session, merged)
    for field, value in values.items():
        setattr(application, field, value)
    application.version += 1
    try:
        session.flush()
    except StaleDataError as error:
        session.rollback()
        raise ApiErrorException(409, "CONFLICT_VERSION", VERSION_MESSAGE) from error
    session.commit()
    return application


def list_applications(
    session: Session, company_id: UUID, user: User
) -> list[Application]:
    member_company(company_id, user, session)
    return list(
        session.scalars(
            select(Application)
            .where(Application.company_id == company_id)
            .order_by(Application.created_at.desc(), Application.number.desc())
        )
    )
