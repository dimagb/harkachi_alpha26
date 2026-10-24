from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event

import pytest
from sqlalchemy import event, func, select

from app.errors import ApiErrorException
from app.models import Application, ApplicationEvent, InfoRequest, Offer


def overdue_offer(factory, identity):
    with factory.begin() as session:
        application = session.get(Application, identity)
        session.get(Offer, application.current_offer_id).expires_at = datetime.now(
            UTC
        ) - timedelta(days=1)


def test_expiry_skips_locked_application(pipeline_factory, run_persona, caplog):
    from app.expiry.service import expire_due

    caplog.set_level("DEBUG", logger="app.expiry.service")
    identity = run_persona("ip_good")
    overdue_offer(pipeline_factory, identity)
    with pipeline_factory.begin() as session:
        application = session.scalar(
            select(Application).where(Application.id == identity).with_for_update()
        )
        assert expire_due(pipeline_factory) == 0
        assert application.state == "OFFER_ISSUED"
    assert [record.getMessage() for record in caplog.records] == [
        "Expiry skipped locked applications: 1"
    ]
    caplog.clear()
    assert expire_due(pipeline_factory) == 1
    assert [record.getMessage() for record in caplog.records] == [
        "Expiry skipped locked applications: 0"
    ]


def test_failure_rolls_back_one_application_and_continues(
    pipeline_factory, run_persona, monkeypatch, caplog
):
    from app.expiry import service

    identities = sorted([run_persona("ip_good"), run_persona("ip_good")])
    for identity in identities:
        overdue_offer(pipeline_factory, identity)
    original = service.expire_application

    def fail_one(session, application):
        result = original(session, application)
        if application.id == identities[0]:
            session.flush()
            raise RuntimeError("secret SQL parameters")
        return result

    monkeypatch.setattr(service, "expire_application", fail_one)
    assert service.expire_due(pipeline_factory) == 1
    assert "RuntimeError" in caplog.text
    assert "secret SQL parameters" not in caplog.text
    with pipeline_factory() as session:
        assert session.get(Application, identities[0]).state == "OFFER_ISSUED"
        assert session.get(Application, identities[1]).state == "EXPIRED"
        assert (
            session.scalar(
                select(func.count())
                .select_from(ApplicationEvent)
                .where(
                    ApplicationEvent.application_id == identities[0],
                    ApplicationEvent.to_state == "EXPIRED",
                )
            )
            == 0
        )
        application = session.get(Application, identities[0])
        assert session.get(Offer, application.current_offer_id).status == "ACTIVE"


def test_shift_rechecks_state_after_waiting_for_lock(pipeline_factory, run_persona):
    from app.expiry.service import expire_application, time_shift

    identity = run_persona("ip_good")
    overdue_offer(pipeline_factory, identity)
    waiting = Event()
    engine = pipeline_factory.kw["bind"]

    def on_query(connection, cursor, statement, parameters, context, executemany):
        if "FOR UPDATE OF application" in statement:
            waiting.set()

    def shift():
        with pipeline_factory() as session:
            return time_shift(session, str(identity), 1)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with pipeline_factory.begin() as session:
            application = session.scalar(
                select(Application).where(Application.id == identity).with_for_update()
            )
            deadline = session.get(Offer, application.current_offer_id).expires_at
            event.listen(engine, "before_cursor_execute", on_query)
            try:
                future = pool.submit(shift)
                assert waiting.wait(5), "time-shift did not acquire application lock"
                assert expire_application(session, application)
            finally:
                event.remove(engine, "before_cursor_execute", on_query)
        with pytest.raises(ApiErrorException) as raised:
            future.result(timeout=5)
        assert raised.value.status == 409
    with pipeline_factory() as session:
        application = session.get(Application, identity)
        assert application.state == "EXPIRED"
        assert session.get(Offer, application.current_offer_id).expires_at == deadline


def test_closed_info_request_is_not_due(pipeline_factory, run_persona):
    from app.expiry.service import expire_due

    identity = run_persona("ooo_gap")
    with pipeline_factory.begin() as session:
        request = session.scalar(
            select(InfoRequest).where(InfoRequest.application_id == identity)
        )
        request.due_at = datetime.now(UTC) - timedelta(days=1)
        request.responded_at = datetime.now(UTC)
    assert expire_due(pipeline_factory) == 0


def test_deadline_equality_is_due(pipeline_factory, run_persona, monkeypatch):
    from app.expiry import service

    identity = run_persona("ip_good")
    deadline = datetime.now(UTC)
    with pipeline_factory.begin() as session:
        application = session.get(Application, identity)
        session.get(Offer, application.current_offer_id).expires_at = deadline

    class Clock:
        @staticmethod
        def now(zone):
            return deadline

    monkeypatch.setattr(service, "datetime", Clock)
    assert service.expire_due(pipeline_factory) == 1
