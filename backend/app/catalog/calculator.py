from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, StrictInt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.errors import ApiErrorException
from app.catalog.products import ProductCode, active_config, rate_from
from app.models import Product


class CalculatorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_code: ProductCode
    amount: StrictInt
    term_months: StrictInt


class CalculatorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rate_estimate: float
    monthly_payment: int | None


def annuity(amount: int, rate: Decimal, term_months: int) -> int:
    # TODO(lead): заменить на функцию B-02.
    monthly_rate = rate / Decimal(1200)
    payment = (
        Decimal(amount) / term_months
        if monthly_rate == 0
        else Decimal(amount) * monthly_rate / (1 - (1 + monthly_rate) ** -term_months)
    )
    return int(payment.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def calculate(session: Session, request: CalculatorRequest) -> CalculatorResponse:
    product = session.scalar(
        select(Product).where(Product.code == request.product_code)
    )
    if product is None:
        raise ApiErrorException(
            503, "SERVICE_UNAVAILABLE", "Продукт временно недоступен"
        )
    params = product.params
    fields = {}
    if not params["min"] <= request.amount <= params["max"]:
        minimum = f"{params['min']:,}".replace(",", " ")
        maximum = f"{params['max']:,}".replace(",", " ")
        fields["amount"] = f"Сумма от {minimum} до {maximum} ₽"
    if not params["tmin"] <= request.term_months <= params["tmax"]:
        fields["term_months"] = f"Срок от {params['tmin']} до {params['tmax']} мес."
    if fields:
        raise ApiErrorException(
            422, "VALIDATION_ERROR", "Проверьте параметры кредита", {"fields": fields}
        )
    rate = rate_from(product, active_config(session))
    payment = (
        None
        if request.product_code == "OVERDRAFT"
        else annuity(request.amount, rate, request.term_months)
    )
    return CalculatorResponse(rate_estimate=rate, monthly_payment=payment)
