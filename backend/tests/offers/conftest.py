import pytest
from pipeline.conftest import persona_data as persona_data
from pipeline.conftest import pipeline_factory as pipeline_factory
from sqlalchemy import select

from app.decision import DEFAULT_CONFIG
from app.models import Product, ReasonCatalog, User


@pytest.fixture
def actions_factory(pipeline_factory):
    with pipeline_factory.begin() as session:
        for product in session.scalars(select(Product)):
            cfg = DEFAULT_CONFIG.products[product.code]
            product.params = {
                "min": cfg.min_amount,
                "max": cfg.max_amount,
                "tmin": cfg.min_term,
                "tmax": cfg.max_term,
                "spread": dict(cfg.spreads),
            }
        for code, text in (
            ("CLIENT_WITHDREW", "Вы отозвали заявку"),
            ("CLIENT_REJECTED_OFFER", "Вы отказались от предложения банка"),
        ):
            reason = session.scalar(
                select(ReasonCatalog).where(ReasonCatalog.code == code)
            )
            reason.client_text = text
            reason.client_action = "Можно подать новую заявку"
        session.add(
            User(
                login="bank_b09a",
                password_hash="unused",
                role="UNDERWRITER",
                full_name="Специалист Банка",
            )
        )
    return pipeline_factory
