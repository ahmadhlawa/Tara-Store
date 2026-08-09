"""The instance CLI surface, the demo seed separation, and the offline MySQL check."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.template_version import template_version
from app.models import Coupon, InstanceMetadata, Order, Product
from scripts import instance_cli, mysql_compat

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_PROFILE = REPO_ROOT / "instance" / "demo-profile.yaml"


@pytest.fixture()
def cli_env(session_factory: sessionmaker, monkeypatch):
    """Point the CLI's session helper at the per-test database."""
    monkeypatch.setattr(instance_cli, "_session", lambda: session_factory())
    return session_factory


@pytest.fixture()
def profile_path(tmp_path: Path) -> Path:
    document = {
        "profile_schema_version": 1,
        "template_version": template_version(),
        "client_slug": "cli-store",
        "store": {"name": "CLI Store"},
        "home_sections": [{"key": "categories", "type": "categories", "sort_order": 1}],
        "static_pages": [{"slug": "about", "title": "About"}],
    }
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")
    return path


# ── validate ─────────────────────────────────────────────────────────────────
def test_validate_accepts_a_good_profile(profile_path: Path, capsys) -> None:
    assert instance_cli.main(["validate", "--profile", str(profile_path)]) == 0
    assert "cli-store" in capsys.readouterr().out


def test_validate_rejects_a_bad_profile(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("profile_schema_version: 1\nclient_slug: 'BAD SLUG'\n", encoding="utf-8")

    assert instance_cli.main(["validate", "--profile", str(bad)]) == instance_cli.EXIT_INVALID
    assert "Invalid profile" in capsys.readouterr().err


def test_validate_needs_no_database(profile_path: Path, monkeypatch) -> None:
    """A profile check must work before DATABASE_URL points anywhere useful."""

    def explode():
        raise AssertionError("validate must not open a database session")

    monkeypatch.setattr(instance_cli, "_session", explode)
    assert instance_cli.main(["validate", "--profile", str(profile_path)]) == 0


# ── plan / apply / manifest ──────────────────────────────────────────────────
def test_plan_reports_actions_and_writes_nothing(cli_env, profile_path: Path, capsys) -> None:
    assert instance_cli.main(["plan", "--profile", str(profile_path)]) == 0
    out = capsys.readouterr().out
    assert "create" in out and "instance_metadata" in out

    with cli_env() as db:
        assert db.execute(select(InstanceMetadata)).scalars().all() == []


def test_apply_then_manifest(cli_env, profile_path: Path, capsys) -> None:
    assert instance_cli.main(["apply", "--profile", str(profile_path)]) == 0
    capsys.readouterr()

    assert instance_cli.main(["manifest"]) == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["instance_slug"] == "cli-store"
    assert manifest["initialized"] is True
    assert manifest["template_version"]


def test_manifest_can_be_written_to_a_file(cli_env, profile_path: Path, tmp_path: Path) -> None:
    instance_cli.main(["apply", "--profile", str(profile_path)])
    target = tmp_path / "manifest.json"

    assert instance_cli.main(["manifest", "--output", str(target)]) == 0
    manifest = json.loads(target.read_text(encoding="utf-8"))
    assert manifest["instance_slug"] == "cli-store"


def test_apply_refuses_a_conflicting_slug(cli_env, profile_path: Path, tmp_path: Path, capsys) -> None:
    instance_cli.main(["apply", "--profile", str(profile_path)])
    capsys.readouterr()

    document = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    document["client_slug"] = "someone-else"
    other = tmp_path / "other.yaml"
    other.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")

    code = instance_cli.main(["apply", "--profile", str(other)])
    assert code == instance_cli.EXIT_CONFLICT
    assert "Conflict" in capsys.readouterr().err

    with cli_env() as db:
        assert db.execute(select(InstanceMetadata)).scalar_one().instance_slug == "cli-store"


def test_plan_reports_a_conflict_without_writing(cli_env, profile_path: Path, tmp_path: Path) -> None:
    instance_cli.main(["apply", "--profile", str(profile_path)])

    document = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    document["client_slug"] = "someone-else"
    other = tmp_path / "other.yaml"
    other.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")

    assert instance_cli.main(["plan", "--profile", str(other)]) == instance_cli.EXIT_CONFLICT


def test_the_shipped_demo_profile_applies(cli_env, capsys) -> None:
    assert instance_cli.main(["apply", "--profile", str(DEMO_PROFILE)]) == 0
    capsys.readouterr()

    with cli_env() as db:
        assert db.execute(select(InstanceMetadata)).scalar_one().instance_slug == "demo-store"
        # Identity only — the catalogue is the separate demo seed.
        assert db.execute(select(Product)).scalars().all() == []
        assert db.execute(select(Order)).scalars().all() == []
        assert db.execute(select(Coupon)).scalars().all() == []


# ── demo seed remains a separate, idempotent workflow ────────────────────────
def test_demo_seed_is_idempotent_and_distinct_from_bootstrap(db: Session) -> None:
    from scripts.seed import seed

    def snapshot() -> dict[str, int]:
        return {
            "products": len(db.execute(select(Product)).scalars().all()),
            "orders": len(db.execute(select(Order)).scalars().all()),
            "coupons": len(db.execute(select(Coupon)).scalars().all()),
        }

    seed(db, admin_email="", admin_password="", admin_name="Owner")
    first = snapshot()
    seed(db, admin_email="", admin_password="", admin_name="Owner")
    second = snapshot()

    assert first == second
    # The demo seed is exactly what bootstrap must never do.
    assert first["products"] > 0
    assert first["orders"] > 0
    assert first["coupons"] > 0


# ── offline MySQL compatibility ──────────────────────────────────────────────
def test_offline_mysql_compatibility_check_passes(capsys) -> None:
    assert mysql_compat.main([]) == 0
    out = capsys.readouterr().out
    assert "no server was contacted" in out
    assert "0 failure(s)" in out


def test_mysql_check_covers_the_documented_areas() -> None:
    checks = {finding.check for finding in mysql_compat.run_checks()}
    assert {
        "table-compilation",
        "money-columns",
        "json-columns",
        "index-key-length",
        "foreign-keys",
        "unique-constraints",
        "enum-like",
        "alembic",
    } <= checks


def test_mysql_check_finds_no_failures() -> None:
    failures = [f for f in mysql_compat.run_checks() if f.level == "fail"]
    assert not failures, [f"{f.check}: {f.message}" for f in failures]
