"""Migration DDL ordering, verified against a real MySQL 8 server.

MySQL requires every foreign key to be backed by an index, and refuses to drop
the last index a constraint can use:

    ERROR 1553: Cannot drop index 'uq_invoices_order_id':
                needed in a foreign key constraint

Revision 0003 creates `invoices` with a foreign key on `order_id` and a unique
constraint on the same column in one CREATE TABLE. InnoDB satisfies the foreign
key with that unique index and creates no second one, so the unique index is the
only thing holding the constraint up. Revision 0005 then replaces the unique
constraint with a plain index, because an order may have more than one invoice
once replacements exist — and the order in which it does that decides whether
MySQL accepts the migration at all.

SQLite never sees this: `batch_alter_table` rebuilds the table instead of issuing
DROP INDEX, and SQLite does not require an index behind a foreign key. So the
whole SQLite suite can pass while MySQL cannot migrate at all, which is exactly
what happened.

These tests walk the revisions one at a time rather than jumping to head, so a
failure names the boundary that broke.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from sqlalchemy import text

from app.db.session import build_engine

from .conftest import BACKEND_ROOT, env_url


@pytest.fixture(scope="module")
def migration_url() -> str:
    return env_url("MYSQL_MIGRATION_URL")


def alembic(url: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_ROOT),
        env={**os.environ, "DATABASE_URL": url, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def run_ok(url: str, *args: str) -> subprocess.CompletedProcess:
    result = alembic(url, *args)
    assert result.returncode == 0, (
        f"alembic {' '.join(args)} failed with exit {result.returncode}\n"
        f"{result.stdout}\n{result.stderr}"
    )
    return result


def reset(url: str) -> None:
    """Drop everything so each test starts from a genuinely empty schema.

    This is the most destructive helper in the test suite: it removes every table
    and trigger in whatever schema the URL resolves to. `env_url` only checks that
    the value looks like a MySQL URL, so a mistyped MYSQL_MIGRATION_URL would
    otherwise erase a real database. The schema name is therefore checked against
    the server before anything is dropped.
    """
    engine = build_engine(url)
    try:
        with engine.begin() as connection:
            schema = connection.execute(text("SELECT DATABASE()")).scalar_one()
            assert schema and schema.endswith(("_migration", "_migr_audit")), (
                f"reset() drops every table and refuses to run against {schema!r}; "
                "point MYSQL_MIGRATION_URL at a disposable schema whose name ends "
                "in _migration"
            )
            triggers = connection.execute(
                text(
                    "SELECT TRIGGER_NAME FROM information_schema.TRIGGERS "
                    "WHERE TRIGGER_SCHEMA = :schema"
                ),
                {"schema": schema},
            ).scalars().all()
            for name in triggers:
                connection.execute(text(f"DROP TRIGGER IF EXISTS `{name}`"))
            tables = connection.execute(text("SHOW TABLES")).scalars().all()
            if tables:
                connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
                for table in tables:
                    connection.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
                connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    finally:
        engine.dispose()


def indexes_on(url: str, table: str, column: str) -> list[str]:
    engine = build_engine(url)
    try:
        with engine.connect() as connection:
            return connection.execute(
                text(
                    "SELECT DISTINCT INDEX_NAME FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table "
                    "AND COLUMN_NAME = :column AND SEQ_IN_INDEX = 1"
                ),
                {"table": table, "column": column},
            ).scalars().all()
    finally:
        engine.dispose()


def foreign_keys_on(url: str, table: str, column: str) -> list[str]:
    engine = build_engine(url)
    try:
        with engine.connect() as connection:
            return connection.execute(
                text(
                    "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table "
                    "AND COLUMN_NAME = :column AND REFERENCED_TABLE_NAME IS NOT NULL"
                ),
                {"table": table, "column": column},
            ).scalars().all()
    finally:
        engine.dispose()


def revision(url: str) -> str:
    engine = build_engine(url)
    try:
        with engine.connect() as connection:
            return connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
    finally:
        engine.dispose()


def test_0003_backs_the_invoice_order_foreign_key_with_only_the_unique_index(
    migration_url: str,
) -> None:
    """Establish the precondition, so a later MySQL change cannot make this vacuous."""
    reset(migration_url)
    run_ok(migration_url, "upgrade", "0003_invoices")

    assert foreign_keys_on(migration_url, "invoices", "order_id"), (
        "0003 is expected to put a foreign key on invoices.order_id"
    )
    assert indexes_on(migration_url, "invoices", "order_id") == ["uq_invoices_order_id"], (
        "the unique constraint is expected to be the only index on invoices.order_id; "
        "if MySQL starts creating a second one this test guards nothing"
    )


def test_0004_to_0005_applies_on_mysql(migration_url: str) -> None:
    """The regression itself: this raised MySQL errno 1553 before the ordering fix."""
    reset(migration_url)
    run_ok(migration_url, "upgrade", "0004_import_batches")

    result = alembic(migration_url, "upgrade", "0005_order_invoice_workflow")
    assert result.returncode == 0, (
        "0004 -> 0005 must apply on MySQL. Before the fix this failed with\n"
        "  (1553, \"Cannot drop index 'uq_invoices_order_id': needed in a foreign "
        "key constraint\")\n"
        "because the replacement index was created after the unique one was "
        f"dropped.\n{result.stdout}\n{result.stderr}"
    )
    assert revision(migration_url) == "0005_order_invoice_workflow"


def test_0005_leaves_the_order_foreign_key_indexed_and_no_longer_unique(
    migration_url: str,
) -> None:
    """The point of the change: many invoices per order, foreign key still supported."""
    reset(migration_url)
    run_ok(migration_url, "upgrade", "0005_order_invoice_workflow")

    names = indexes_on(migration_url, "invoices", "order_id")
    assert "ix_invoices_order_id" in names, names
    assert "uq_invoices_order_id" not in names, (
        "the one-invoice-per-order unique constraint must be gone, or replacement "
        f"invoices cannot exist: {names}"
    )
    assert foreign_keys_on(migration_url, "invoices", "order_id"), (
        "the foreign key must survive the index swap"
    )


def test_0005_leaves_order_activities_foreign_keys_on_the_explicit_indexes(
    migration_url: str,
) -> None:
    """Pin the behaviour that makes dropping those indexes individually unsafe.

    `order_activities` is created with three foreign keys and no covering
    indexes, so InnoDB builds one per key, and the migration then adds explicit
    ix_* indexes for two of the three columns. The downgrade drops the table
    rather than the indexes because those explicit indexes end up being the ones
    the constraints rely on. That is an observation about InnoDB rather than
    something the migration states, so it is asserted instead of assumed.
    """
    reset(migration_url)
    run_ok(migration_url, "upgrade", "0005_order_invoice_workflow")

    for column, expected in (
        ("order_id", "ix_order_activities_order_id"),
        ("invoice_id", "ix_order_activities_invoice_id"),
    ):
        names = indexes_on(migration_url, "order_activities", column)
        assert names == [expected], (
            f"expected the explicit index to be the only one on {column}, got {names}"
        )
        assert foreign_keys_on(migration_url, "order_activities", column)

    # actor_admin_id never got an explicit index, so InnoDB's own survives. The
    # contrast is the evidence that the other two were replaced rather than
    # duplicated.
    actor = indexes_on(migration_url, "order_activities", "actor_admin_id")
    assert actor and not any(name.startswith("ix_") for name in actor), actor


def test_every_revision_applies_one_at_a_time_up_to_head(migration_url: str) -> None:
    """Walk the chain so a failure identifies the exact boundary that broke."""
    reset(migration_url)
    for target in (
        "0003_invoices",
        "0004_import_batches",
        "0005_order_invoice_workflow",
        "0006_active_invoice_marker",
        "0007_active_marker_null_safe",
        "0008_order_activity_triggers",
        "0009_invoice_issuer_snapshot",
        "0010_unique_media_filename",
    ):
        result = alembic(migration_url, "upgrade", target)
        assert result.returncode == 0, (
            f"upgrade to {target} failed on MySQL\n{result.stdout}\n{result.stderr}"
        )
        assert revision(migration_url) == target

    engine = build_engine(migration_url)
    try:
        with engine.connect() as connection:
            triggers = connection.execute(
                text(
                    "SELECT TRIGGER_NAME FROM information_schema.TRIGGERS "
                    "WHERE TRIGGER_SCHEMA = DATABASE() ORDER BY TRIGGER_NAME"
                )
            ).scalars().all()
    finally:
        engine.dispose()
    # 0008 installs these; MySQL needs the TRIGGER privilege to create them, so a
    # missing pair usually means a grant problem rather than a migration problem.
    assert triggers == [
        "trg_order_activities_no_delete",
        "trg_order_activities_no_update",
    ], triggers


def test_the_new_chain_downgrades_and_re_upgrades_on_mysql(migration_url: str) -> None:
    """Dropping the columns has the same index/constraint ordering hazard in reverse."""
    reset(migration_url)
    run_ok(migration_url, "upgrade", "0010_unique_media_filename")

    for target in (
        "0009_invoice_issuer_snapshot",
        "0008_order_activity_triggers",
        "0007_active_marker_null_safe",
        "0006_active_invoice_marker",
        "0005_order_invoice_workflow",
        "0004_import_batches",
    ):
        result = alembic(migration_url, "downgrade", target)
        assert result.returncode == 0, (
            f"downgrade to {target} failed on MySQL\n{result.stdout}\n{result.stderr}"
        )
        assert revision(migration_url) == target

    # Back at 0004 the single-invoice rule is in force again, so the unique
    # constraint has to have been restored rather than silently dropped.
    names = indexes_on(migration_url, "invoices", "order_id")
    assert "uq_invoices_order_id" in names, names
    assert foreign_keys_on(migration_url, "invoices", "order_id")

    run_ok(migration_url, "upgrade", "head")
    current = revision(migration_url)
    heads = run_ok(migration_url, "heads").stdout
    assert current in heads, f"database at {current}, heads: {heads}"


# ── 0010: unique media_assets.original_filename ──────────────────────────────
UNIQUE_FILENAME_INDEX = "ix_media_assets_original_filename"

_INSERT_MEDIA = (
    "INSERT INTO media_assets "
    "(original_filename, stored_key, content_type, size_bytes, url, storage_provider,"
    " created_at) "
    "VALUES (:name, :key, 'image/png', 1, :url, 'local', '2026-01-01 00:00:00')"
)


def insert_media(url: str, rows: list[tuple[str, str]]) -> None:
    engine = build_engine(url)
    try:
        with engine.begin() as connection:
            for name, key in rows:
                connection.execute(
                    text(_INSERT_MEDIA), {"name": name, "key": key, "url": f"/media/{key}"}
                )
    finally:
        engine.dispose()


def media_filenames(url: str) -> list[str]:
    engine = build_engine(url)
    try:
        with engine.connect() as connection:
            return connection.execute(
                text("SELECT original_filename FROM media_assets ORDER BY id")
            ).scalars().all()
    finally:
        engine.dispose()


def test_0010_refuses_duplicates_the_way_mysql_will_compare_them(migration_url: str) -> None:
    """MySQL's default collation is case-insensitive, so the preflight must be too.

    A preflight comparing filenames in Python would let `Photo.png` and `photo.png`
    through, and CREATE UNIQUE INDEX would then fail on a schema MySQL cannot roll
    back. Grouping in the database uses the column's own collation, so the check and
    the index agree.
    """
    reset(migration_url)
    run_ok(migration_url, "upgrade", "0009_invoice_issuer_snapshot")
    insert_media(migration_url, [("Photo.png", "a.png"), ("photo.png", "b.png")])

    result = alembic(migration_url, "upgrade", "0010_unique_media_filename")
    assert result.returncode != 0, result.stdout
    assert "photo.png" in (result.stdout + result.stderr).lower()

    # Nothing removed or renamed, and the schema is untouched.
    assert media_filenames(migration_url) == ["Photo.png", "photo.png"]
    assert UNIQUE_FILENAME_INDEX not in indexes_on(
        migration_url, "media_assets", "original_filename"
    )
    assert revision(migration_url) == "0009_invoice_issuer_snapshot"

    # Once the owner resolves the collision by hand, the migration applies.
    engine = build_engine(migration_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM media_assets WHERE stored_key = 'b.png'"))
    finally:
        engine.dispose()

    run_ok(migration_url, "upgrade", "0010_unique_media_filename")
    assert UNIQUE_FILENAME_INDEX in indexes_on(migration_url, "media_assets", "original_filename")

    run_ok(migration_url, "downgrade", "0009_invoice_issuer_snapshot")
    assert UNIQUE_FILENAME_INDEX not in indexes_on(
        migration_url, "media_assets", "original_filename"
    )
    assert media_filenames(migration_url) == ["Photo.png"]
