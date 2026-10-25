import json
import os
import subprocess
import sys
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app import seed as seed_module
from app.config import Settings, get_settings
from app.models import Application, Company, Job, Offer, Party, Signature, User


@pytest.fixture
def background_factory(migrated_database, monkeypatch):
    engine, _ = migrated_database
    schema = f"background_{uuid4().hex}"
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = engine.url.update_query_dict({"options": f"-csearch_path={schema}"})
    isolated = create_engine(url)
    environment = {**os.environ, "DATABASE_URL": url.render_as_string(False)}
    backend = Path(__file__).resolve().parents[2]
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend,
        env=environment,
        check=True,
        capture_output=True,
    )
    factory = sessionmaker(isolated, expire_on_commit=False)
    monkeypatch.setattr(get_settings(), "demo_background", True)
    for field in ("pipeline_step_delay_sec", "source_retry_pause_sec"):
        monkeypatch.setattr(get_settings(), field, getattr(get_settings(), field))
    with factory.begin() as session:
        seed_module.seed(session)
    try:
        yield factory, environment
    finally:
        isolated.dispose()
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def background_apps(session):
    return list(
        session.scalars(
            select(Application)
            .join(Company)
            .where(
                Company.inn.in_(
                    c["inn"]
                    for c in json.loads(
                        get_settings().background_path.read_text("utf-8")
                    )["companies"]
                )
            )
        )
    )


def test_default_seed_subprocess_has_no_background(migrated_database):
    assert Settings(_env_file=None).demo_background is False
    engine, run = migrated_database
    run("-m", "app.seed")
    with sessionmaker(engine)() as session:
        assert session.scalar(select(User.id).where(User.login == "bg_001")) is None


def test_real_pipeline_states_idempotency_and_no_worker_queue(
    background_factory, caplog
):
    from app.demo.background import run_background

    factory, _ = background_factory
    # A judge's pending job must not be consumed by the background drain.
    with factory.begin() as session:
        company = session.scalar(
            select(Company).where(
                ~Company.inn.in_(
                    c["inn"]
                    for c in json.loads(
                        get_settings().background_path.read_text("utf-8")
                    )["companies"]
                )
            )
        )
        user = session.scalar(select(User).where(User.login == "ip_good"))
        application = Application(
            company_id=company.id,
            created_by=user.id,
            product_code="EXPRESS",
            amount=500000,
            term_months=12,
            purpose="WORKING_CAPITAL",
            declared_revenue_year=6000000,
        )
        session.add(application)
        session.flush()
        job = Job(
            application_id=application.id,
            step="VALIDATION",
            status="PENDING",
            run_after=datetime.now(UTC),
        )
        session.add(job)
        session.flush()
        judge_job = job.id
    with caplog.at_level("INFO"):
        run_background(factory)
    with factory() as session:
        apps = background_apps(session)
        assert len(apps) == 60
        counts = Counter(a.state for a in apps)
        assert counts["MANUAL_REVIEW"] >= 3
        assert all(
            counts[s] > 0
            for s in (
                "OFFER_ISSUED",
                "DECLINED",
                "WITHDRAWN",
                "DRAFT",
                "INFO_REQUESTED",
            )
        )
        assert session.get(Job, judge_job).status == "PENDING"
        assert set(
            session.scalars(
                select(Job.status).where(Job.application_id.in_(a.id for a in apps))
            )
        ) == {"DONE"}
        before = {a.id for a in apps}
        assert session.scalar(select(func.count()).select_from(Company)) == 46
        assert (
            len(list(session.scalars(select(User).where(User.login.like("bg_%")))))
            == 40
        )
    run_background(factory)
    with factory() as session:
        assert {a.id for a in background_apps(session)} == before
    assert "Фоновые заявки: 60 создано" in caplog.text
    assert "не совпало:" in caplog.text
    assert get_settings().pipeline_step_delay_sec == 0
    assert get_settings().source_retry_pause_sec == 0


def test_one_failure_rolls_back_and_continues(background_factory, monkeypatch, caplog):
    from app.demo import background

    factory, _ = background_factory
    original = background.submit
    calls = 0

    def broken_once(session, *args):
        nonlocal calls
        calls += 1
        if calls == 1:
            session.execute(text("SELECT 1 / 0"))
        return original(session, *args)

    monkeypatch.setattr(background, "submit", broken_once)
    background.run_background(factory)
    with factory() as session:
        assert len(background_apps(session)) >= 59
        assert session.scalar(select(User.id).where(User.login == "ip_good"))
        assert "PENDING" not in set(session.scalars(select(Job.status)))
    assert calls > 1
    assert "SELECT 1 / 0" not in caplog.text


def test_seed_survives_background_failure_after_commit(
    background_factory, monkeypatch, caplog
):
    from app.demo import background

    factory, _ = background_factory
    monkeypatch.setattr(seed_module, "SessionLocal", factory)

    def broken(_):
        with factory() as session:
            assert session.scalar(select(User.id).where(User.login == "bg_001"))
        raise RuntimeError("sensitive-background-error")

    monkeypatch.setattr(background, "run_background", broken)
    seed_module.main()
    assert "sensitive-background-error" not in caplog.text


def test_seed_subprocess_missing_background_exits_zero(background_factory):
    _, environment = background_factory
    result = subprocess.run(
        [sys.executable, "-m", "app.seed"],
        cwd=Path(__file__).resolve().parents[2],
        env={
            **environment,
            "DEMO_BACKGROUND": "true",
            "BACKGROUND_PATH": "/missing/background.json",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_time_budget_stops_before_next_application(
    background_factory, monkeypatch, caplog
):
    from app.demo import background

    factory, _ = background_factory
    ticks = iter([0, 46])
    monkeypatch.setattr(background.time, "monotonic", lambda: next(ticks))
    background.run_background(factory)
    with factory() as session:
        assert background_apps(session) == []
    assert "45" in caplog.text


def test_stage_two_disburses_with_both_signatures_and_expires(background_factory):
    from app.demo.background import run_background

    factory, _ = background_factory
    run_background(factory)
    with factory() as session:
        apps = background_apps(session)
        counts = Counter(a.state for a in apps)
        assert counts["DISBURSED"] >= 3
        assert counts["EXPIRED"] >= 3
        both_signatures = False
        for application in apps:
            if application.state == "EXPIRED":
                assert (
                    session.get(Offer, application.current_offer_id).status == "EXPIRED"
                )
            if application.state != "DISBURSED":
                continue
            parties = list(
                session.scalars(
                    select(Party).where(Party.application_id == application.id)
                )
            )
            assert all(p.status == "SIGNED" for p in parties)
            signatures = list(
                session.scalars(
                    select(Signature).where(
                        Signature.application_id == application.id,
                        Signature.object_type.in_(("OFFER", "GUARANTEE")),
                    )
                )
            )
            assert len(signatures) == len(parties)
            if session.get(Company, application.company_id).kind == "OOO":
                assert {p.role for p in parties} == {"BORROWER_SIGNATORY", "GUARANTOR"}
                assert {s.object_type for s in signatures} == {"OFFER", "GUARANTEE"}
                both_signatures = True
        assert both_signatures
        assert set(session.scalars(select(Job.status))) == {"DONE"}
        before = {a.id for a in apps}
    run_background(factory)
    with factory() as session:
        assert {a.id for a in background_apps(session)} == before


def test_unexpected_pipeline_state_is_not_forced_to_target(
    background_factory, monkeypatch, tmp_path, caplog
):
    from app.demo import background
    from app.integrations.registry import ProviderUnavailable

    factory, _ = background_factory
    data = json.loads(get_settings().background_path.read_text("utf-8"))
    company, item = next(
        (company, item)
        for company in data["companies"]
        for item in company["demo"]["apps"]
        if item["target_state"] == "EXPIRED"
    )
    company["demo"]["apps"] = [item]
    data["companies"] = [company]
    path = tmp_path / "background.json"
    path.write_text(json.dumps(data), "utf-8")
    monkeypatch.setattr(get_settings(), "background_path", path)
    normal_providers = background.providers_for([company])

    class UnavailableBureau:
        def get(self, inn, consent_id):
            raise ProviderUnavailable("sensitive-source-error")

    monkeypatch.setattr(
        background,
        "providers_for",
        lambda _: replace(normal_providers, bureau=UnavailableBureau()),
    )
    with caplog.at_level("INFO"):
        background.run_background(factory)
    with factory() as session:
        assert [a.state for a in background_apps(session)] == ["MANUAL_REVIEW"]
        assert session.scalar(select(func.count()).select_from(Offer)) == 0
    assert "не совпало: 1" in caplog.text
    assert "sensitive-source-error" not in caplog.text
