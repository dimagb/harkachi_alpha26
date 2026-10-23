from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiErrorException
from app.integrations.registry import ProviderUnavailable, RegistryProvider
from app.models import AccountTurnover, Company
from app.schemas.api import CompanyProfile


def company_profile(
    session: Session, company: Company, registry: RegistryProvider
) -> CompanyProfile:
    try:
        record = registry.get(company.inn)
    except ProviderUnavailable as error:
        raise ApiErrorException(
            503, "SERVICE_UNAVAILABLE", "Реестр временно недоступен, попробуйте позже"
        ) from error
    if record is None:
        raise ApiErrorException(404, "NOT_FOUND", "Компания не найдена")
    average = session.scalar(
        select(func.avg(AccountTurnover.credit_turnover)).where(
            AccountTurnover.company_id == company.id
        )
    )
    turnover = int(Decimal(average or 0).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    source = "ЕГРЮЛ" if company.kind == "OOO" else "ЕГРИП"
    # TODO(lead): заменить на демо-часы B-10.
    today = date.today()
    return CompanyProfile(
        id=str(company.id),
        inn=company.inn,
        ogrn=company.ogrn,
        kind=company.kind,
        name=company.name,
        status=record.status,
        reg_date=company.reg_date.isoformat(),
        okved_main=company.okved_main,
        address=company.address,
        director_full_name=record.director.full_name,
        founders=[founder.model_dump() for founder in record.founders],
        avg_monthly_turnover=turnover,
        source_note=f"Данные из {source} на {today:%d.%m.%Y}",
    )
