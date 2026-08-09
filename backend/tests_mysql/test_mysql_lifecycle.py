"""The client lifecycle, run for real against MySQL 8.

Everything here shells out to the same commands an operator runs, so a green result
means the documented lifecycle works on MySQL — not that a mock did.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from app.db.base import metadata_with_models
from app.db.session import build_engine

from .conftest import BACKEND_ROOT, env_url

REPO_ROOT = BACKEND_ROOT.parent
EXAMPLE_PROFILE = REPO_ROOT / "instance" / "client-profile.example.yaml"
DEMO_PROFILE = REPO_ROOT / "instance" / "demo-profile.yaml"

ADMIN_EMAIL = "ci-owner@example.com"
ADMIN_PASSWORD = "CiOnlyPassw0rd!42"


def run(args: list[str], *, url: str | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    if url:
        env["DATABASE_URL"] = url
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(BACKEND_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def ok(result: subprocess.CompletedProcess) -> subprocess.CompletedProcess:
    assert result.returncode == 0, f"exit {result.returncode}\n{result.stdout}\n{result.stderr}"
    return result


@pytest.fixture(scope="module")
def lifecycle_url() -> str:
    return env_url("MYSQL_LIFECYCLE_URL")


@pytest.fixture(scope="module")
def seed_url() -> str:
    return env_url("MYSQL_SEED_URL")


# ── schema ───────────────────────────────────────────────────────────────────
def test_alembic_upgraded_a_new_empty_database_to_head(engine) -> None:
    with engine.connect() as connection:
        stamped = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    head = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        text=True,
    ).stdout
    assert stamped in head, f"database at {stamped}, heads: {head}"


def test_the_migrated_schema_matches_the_models(engine) -> None:
    present = set(inspect(engine).get_table_names()) - {"alembic_version"}
    expected = set(metadata_with_models().tables)
    assert present == expected, f"missing={expected - present} unexpected={present - expected}"


def test_tables_are_innodb_utf8mb4(engine) -> None:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT table_name, engine, table_collation FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name <> 'alembic_version'"
            )
        ).all()
    assert rows, "no tables found"
    wrong = [
        (name, eng, collation)
        for name, eng, collation in rows
        if eng != "InnoDB" or not str(collation).startswith("utf8mb4")
    ]
    assert not wrong, wrong


# ── profile, bootstrap, idempotency, metadata ────────────────────────────────
def test_the_full_client_lifecycle_on_mysql(lifecycle_url: str) -> None:
    ok(run(["-m", "alembic", "upgrade", "head"], url=lifecycle_url))

    validated = ok(run(["-m", "scripts.instance_cli", "validate", "--profile", str(EXAMPLE_PROFILE)]))
    assert "Profile OK" in validated.stdout

    planned = ok(run(["-m", "scripts.instance_cli", "plan", "--profile", str(EXAMPLE_PROFILE)], url=lifecycle_url))
    assert "[create" in planned.stdout

    applied = ok(run(["-m", "scripts.instance_cli", "apply", "--profile", str(EXAMPLE_PROFILE)], url=lifecycle_url))
    assert "[create  ] instance_metadata" in applied.stdout

    # Repeated apply must be idempotent: nothing new, nothing overwritten.
    again = ok(run(["-m", "scripts.instance_cli", "apply", "--profile", str(EXAMPLE_PROFILE)], url=lifecycle_url))
    assert "[create" not in again.stdout, again.stdout
    assert again.stdout.count("[skip") >= 1

    counts_before = _row_counts(lifecycle_url, ["store_settings", "home_sections", "static_pages"])
    ok(run(["-m", "scripts.instance_cli", "apply", "--profile", str(EXAMPLE_PROFILE)], url=lifecycle_url))
    assert _row_counts(lifecycle_url, ["store_settings", "home_sections", "static_pages"]) == counts_before


def test_instance_metadata_is_recorded_and_manifest_has_no_secrets(lifecycle_url: str) -> None:
    ok(run(["-m", "alembic", "upgrade", "head"], url=lifecycle_url))
    ok(run(["-m", "scripts.instance_cli", "apply", "--profile", str(EXAMPLE_PROFILE)], url=lifecycle_url))

    manifest = json.loads(ok(run(["-m", "scripts.instance_cli", "manifest"], url=lifecycle_url)).stdout)
    assert manifest["initialized"] is True
    assert manifest["instance_slug"] == "example-client"
    assert manifest["profile_schema_version"] == 1
    assert manifest["alembic_revision"] == manifest["alembic_head"]
    assert manifest["enabled_features"]
    assert manifest["initialized_at"] and manifest["last_bootstrap_at"]

    document = json.dumps(manifest).lower()
    for forbidden in ("password", "secret", "token", "mysql://", "mysql+pymysql", "database_url"):
        assert forbidden not in document, f"{forbidden!r} leaked into the manifest"
    assert os.environ["MYSQL_LIFECYCLE_URL"].lower() not in document


def test_a_conflicting_instance_slug_is_refused(lifecycle_url: str, tmp_path: Path) -> None:
    conflicting = tmp_path / "other-profile.yaml"
    conflicting.write_text(
        EXAMPLE_PROFILE.read_text(encoding="utf-8").replace(
            'client_slug: "example-client"', 'client_slug: "different-client"'
        ),
        encoding="utf-8",
    )
    refused = run(["-m", "scripts.instance_cli", "apply", "--profile", str(conflicting)], url=lifecycle_url)
    assert refused.returncode == 3, refused.stdout
    assert "Nothing was written" in refused.stderr

    manifest = json.loads(ok(run(["-m", "scripts.instance_cli", "manifest"], url=lifecycle_url)).stdout)
    assert manifest["instance_slug"] == "example-client"


# ── demo seed ────────────────────────────────────────────────────────────────
def test_the_demo_seed_is_idempotent_on_mysql(seed_url: str) -> None:
    ok(run(["-m", "alembic", "upgrade", "head"], url=seed_url))
    ok(run(["-m", "scripts.seed"], url=seed_url))
    tables = sorted(metadata_with_models().tables)
    after_first = _row_counts(seed_url, tables)

    ok(run(["-m", "scripts.seed"], url=seed_url))
    after_second = _row_counts(seed_url, tables)

    differing = {
        name: (after_first[name], after_second[name])
        for name in tables
        if after_first[name] != after_second[name]
    }
    assert not differing, f"the second seed changed row counts: {differing}"
    assert after_first["products"] > 0 and after_first["categories"] > 0


# ── admin creation ───────────────────────────────────────────────────────────
def test_the_initial_admin_command_works_on_mysql(client) -> None:
    ok(
        run(
            [
                "-m",
                "app.initial_data",
                "--email",
                ADMIN_EMAIL,
                "--password",
                ADMIN_PASSWORD,
                "--name",
                "CI Owner",
                "--role",
                "super_admin",
            ]
        )
    )
    response = client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, response.text
    assert response.json()["access_token"]


def _row_counts(url: str, tables: list[str]) -> dict[str, int]:
    engine = build_engine(url)
    try:
        with engine.connect() as connection:
            return {
                name: connection.execute(text(f"SELECT COUNT(*) FROM `{name}`")).scalar_one()
                for name in tables
            }
    finally:
        engine.dispose()
