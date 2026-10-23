from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.products import active_config, rate_from
from app.errors import ApiErrorException
from app.models import Product
from app.schemas.api import CalculatorRequest, CalculatorResponse


def annuity(amount: int, rate: Decimal, term_months: int) -> int:
    # TODO(lead): заменить на функцию B-02.
    monthly_rate = rate / Decimal(1200)
    payment = (
        Decimal(amount) / term_months
        if monthly_rate == 0
        else Decimal(amount) * monthly_rate / (1 - (1 + monthly_rate) ** -term_months)
    )
    return int(payment.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def validate_terms(
    session: Session, product_code: str, amount: int, term_months: int
) -> Product:
    product = session.scalar(select(Product).where(Product.code == product_code))
    if product is None:
        raise ApiErrorException(
            503, "SERVICE_UNAVAILABLE", "Продукт временно недоступен"
        )
    params = product.params
    fields = {}
    if not params["min"] <= amount <= params["max"]:
        minimum = f"{params['min']:,}".replace(",", " ")
        maximum = f"{params['max']:,}".replace(",", " ")
        fields["amount"] = f"Сумма от {minimum} до {maximum} ₽"
    if not params["tmin"] <= term_months <= params["tmax"]:
        fields["term_months"] = f"Срок от {params['tmin']} до {params['tmax']} мес."
    if fields:
        raise ApiErrorException(
            422, "VALIDATION_ERROR", "Проверьте параметры кредита", {"fields": fields}
        )
    return product


def calculate(session: Session, request: CalculatorRequest) -> CalculatorResponse:
    product = validate_terms(
        session, request.product_code, request.amount, request.term_months
    )
    rate = rate_from(product, active_config(session))
    payment = (
        None
        if request.product_code == "OVERDRAFT"
        else annuity(request.amount, rate, request.term_months)
    )
    return CalculatorResponse(rate_estimate=rate, monthly_payment=payment)
