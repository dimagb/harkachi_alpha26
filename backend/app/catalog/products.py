from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.errors import ApiErrorException
from app.models import DecisionConfig
from app.models import Product as ProductRow

ProductCode = Literal["EXPRESS", "WORKING_CAPITAL", "OVERDRAFT"]
Purpose = Literal["WORKING_CAPITAL", "CASH_GAP", "EQUIPMENT", "OTHER"]
PRODUCT_CATALOG: dict[ProductCode, tuple[list[Purpose], bool]] = {
    "EXPRESS": (["WORKING_CAPITAL", "CASH_GAP", "EQUIPMENT", "OTHER"], True),
    "WORKING_CAPITAL": (["WORKING_CAPITAL", "CASH_GAP"], True),
    "OVERDRAFT": (["CASH_GAP", "WORKING_CAPITAL"], True),
}


class Product(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: ProductCode
    name: str
    description: str
    purposes: list[Purpose]
    min_amount: int
    max_amount: int
    min_term_months: int
    max_term_months: int
    rate_from: float
    requires_guarantor_ooo: bool
    key_rate: float
    key_rate_date: str


def active_config(session: Session) -> DecisionConfig:
    config = session.scalar(
        select(DecisionConfig).where(DecisionConfig.active.is_(True))
    )
    if config is None:
        raise ApiErrorException(
            503, "SERVICE_UNAVAILABLE", "Каталог временно недоступен"
        )
    return config


def rate_from(product: ProductRow, config: DecisionConfig) -> Decimal:
    return (config.key_rate + Decimal(str(product.params["spread"]["A"]))).quantize(
        Decimal("0.01")
    )


def list_products(session: Session) -> list[Product]:
    config = active_config(session)
    rows = {product.code: product for product in session.scalars(select(ProductRow))}
    products = []
    for code, (purposes, guarantor) in PRODUCT_CATALOG.items():
        product = rows.get(code)
        if product is None:
            raise ApiErrorException(
                503, "SERVICE_UNAVAILABLE", "Каталог временно недоступен"
            )
        products.append(
            Product(
                code=code,
                name=product.name,
                description=product.description,
                purposes=purposes,
                min_amount=product.params["min"],
                max_amount=product.params["max"],
                min_term_months=product.params["tmin"],
                max_term_months=product.params["tmax"],
                rate_from=rate_from(product, config),
                requires_guarantor_ooo=guarantor,
                key_rate=config.key_rate,
                key_rate_date=config.key_rate_date.isoformat(),
            )
        )
    return products
