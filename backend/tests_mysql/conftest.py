"""MySQL integration bootstrap.

Deliberately a **separate directory**. `pyproject.toml` sets `testpaths = ["tests"]`,
so nothing here is collected by a normal `pytest` run and the SQLite suite is untouched.
CI runs it explicitly:

    pytest tests_mysql

Every test needs a real, disposable MySQL 8 server. There is exactly one place that
provides it — the ephemeral service container in
`.github/workflows/mysql-compatibility.yml`. Nothing here may point at a developer
machine, a VPS or a production database, and the whole module refuses to run against
anything that is not MySQL.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

import app.api.v1.endpoints.admin_media as admin_media
from app.core.config import settings
from app.db.session import build_engine, get_db
from app.main import app as fastapi_app
from app.storage.local import LocalStorageProvider

BACKEND_ROOT = Path(__file__).resolve().parents[1]

ON_MYSQL = settings.DATABASE_URL.startswith("mysql")

# Nothing here is collected unless a MySQL URL is configured, so running the whole
# directory by hand on a developer machine reports "no tests" instead of failing.
collect_ignore_glob = [] if ON_MYSQL else ["test_*.py"]

if not ON_MYSQL:  # pragma: no cover - the fixtures below are never reached
    print(
        "tests_mysql skipped: DATABASE_URL is "
        f"{settings.DATABASE_URL.split('://')[0]!r}, not an ephemeral MySQL 8 service."
    )


def env_url(name: str) -> str:
    value = os.environ.get(name, "")
    if not value.startswith("mysql"):
        pytest.skip(f"{name} is not set to a MySQL URL")
    return value


@pytest.fixture(scope="session")
def engine():
    engine = build_engine(settings.sqlalchemy_url())
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def session_factory(engine) -> sessionmaker:
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


@pytest.fixture()
def db(session_factory: sessionmaker) -> Iterator[Session]:
    with session_factory() as session:
        yield session


@pytest.fixture()
def client(session_factory: sessionmaker, tmp_path: Path) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db

    media_root = tmp_path / "uploads"
    media_root.mkdir(parents=True, exist_ok=True)
    provider = LocalStorageProvider(media_root, "/media")
    original = admin_media.get_storage
    admin_media.get_storage = lambda: provider

    with TestClient(fastapi_app) as test_client:
        yield test_client

    admin_media.get_storage = original
    fastapi_app.dependency_overrides.clear()


@pytest.fixture(scope="session", autouse=True)
def confirm_server_is_mysql(engine) -> None:
    """Fail loudly rather than silently exercising the wrong engine."""
    with engine.connect() as connection:
        assert connection.dialect.name == "mysql", connection.dialect.name
        version = connection.execute(text("SELECT VERSION()")).scalar_one()
    assert str(version).startswith("8."), f"expected MySQL 8, got {version}"
