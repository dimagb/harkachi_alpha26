import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.fixture(scope="session")
def migrated_database():
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        # TODO(lead): optional local run only; CI provides TEST_DATABASE_URL.
        pytest.skip("Для тестов БД задайте TEST_DATABASE_URL (PostgreSQL)")
    admin_engine = create_engine(database_url)
    schema = f"b03_test_{uuid4().hex}"
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = make_url(database_url).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    )
    isolated_url = url.render_as_string(hide_password=False)
    environment = {
        **os.environ,
        "DATABASE_URL": isolated_url,
        "DEMO_PASSWORD": "b03-test-password",
    }
    backend = Path(__file__).resolve().parents[1]

    def run(*args):
        subprocess.run(
            [sys.executable, *args], cwd=backend, env=environment, check=True
        )

    engine = create_engine(url)
    try:
        run("-m", "alembic", "upgrade", "head")
        run("-m", "alembic", "downgrade", "base")
        run("-m", "alembic", "upgrade", "head")
        run("-m", "app.seed")
        run("-m", "app.seed")
        yield engine, run
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()
