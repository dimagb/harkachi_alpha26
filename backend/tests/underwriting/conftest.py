import pytest
from fastapi.testclient import TestClient
from pipeline.conftest import persona_data as persona_data
from pipeline.conftest import pipeline_factory as pipeline_factory
from pipeline.test_pipeline import drain, providers_for, submit_persona
from sqlalchemy import select

from app.auth.deps import current_user
from app.db import get_session
from app.decision import DEFAULT_CONFIG
from app.main import app
from app.models import Product, ReasonCatalog, User


@pytest.fixture
def bank_context(pipeline_factory, persona_data):
    with pipeline_factory.begin() as session:
        user = User(
            login="underwriter_b08",
            password_hash="unused",
            role="UNDERWRITER",
            full_name="Специалист Банка",
        )
        session.add(user)
        session.flush()
        user_id = user.id
        for product in session.scalars(select(Product)):
            cfg = DEFAULT_CONFIG.products[product.code]
            product.params = {
                "min": cfg.min_amount,
                "max": cfg.max_amount,
                "tmin": cfg.min_term,
                "tmax": cfg.max_term,
                "spreads": dict(cfg.spreads),
            }
        reason = session.scalar(
            select(ReasonCatalog).where(ReasonCatalog.code == "UNDERWRITER_DECLINE")
        )
        reason.client_text = "Заявку рассмотрел специалист банка и не смог её одобрить"
        reason.client_action = None
        reason.client_category = None

    def session_dependency():
        with pipeline_factory() as session:
            yield session

    def user_dependency():
        with pipeline_factory() as session:
            return session.get(User, user_id)

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[current_user] = user_dependency
    with TestClient(app) as client:
        yield client, user_id
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(current_user, None)


@pytest.fixture
def run_persona(pipeline_factory, persona_data):
    def run(code="ooo_border", **providers):
        persona = next(p for p in persona_data["personas"] if p["code"] == code)
        application_id = submit_persona(pipeline_factory, persona)
        drain(pipeline_factory, providers_for(persona_data, **providers), persona_data)
        return application_id

    return run
