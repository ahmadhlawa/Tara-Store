"""The Alembic revision, not create_all, is the schema of record."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.db.base import metadata_with_models
from app.db.session import build_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_TABLES = {
    "admin_users",
    "articles",
    "audit_logs",
    "banners",
    "categories",
    "coupons",
    "delivery_areas",
    "hero_slides",
    "home_sections",
    "import_batch_records",
    "import_batches",
    "instance_metadata",
    "invoice_items",
    "invoice_sequences",
    "invoices",
    "media_assets",
    "order_items",
    "order_item_package_components",
    "order_activities",
    "order_status_history",
    "orders",
    "package_items",
    "product_images",
    "product_option_values",
    "product_options",
    "product_specifications",
    "product_variant_option_values",
    "product_variants",
    "products",
    "static_pages",
    "store_settings",
}


def _alembic_config(db_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", db_url)
    return config


def _disposable_url(tmp_path, monkeypatch) -> str:
    """A throwaway SQLite file the migrations may build from scratch."""
    db_path = tmp_path / "migrated.db"
    url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)

    # alembic/env.py reads the URL from the application settings.
    from app.core import config as config_module

    monkeypatch.setattr(config_module.settings, "DATABASE_URL", url)
    return url


def test_alembic_upgrade_builds_the_whole_schema(tmp_path, monkeypatch) -> None:
    url = _disposable_url(tmp_path, monkeypatch)

    command.upgrade(_alembic_config(url), "head")

    engine = build_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert EXPECTED_TABLES.issubset(tables)
    assert "alembic_version" in tables


def test_models_and_expected_tables_agree() -> None:
    assert set(metadata_with_models().tables) == EXPECTED_TABLES


# Alembic creates alembic_version.version_num as VARCHAR(32). SQLite ignores that
# length and stores whatever it is given, so an over-long revision id is invisible
# there and only fails on MySQL, at the moment Alembic records the revision:
#
#   (1406, "Data too long for column 'version_num' at row 1")
#
# by which point the migration's DDL has already been applied and cannot be rolled
# back, because MySQL does not do transactional DDL.
VERSION_NUM_LENGTH = 32


def test_every_revision_id_fits_the_alembic_version_column() -> None:
    script = ScriptDirectory.from_config(_alembic_config("sqlite://"))
    too_long = {
        revision.revision: len(revision.revision)
        for revision in script.walk_revisions()
        if len(revision.revision) > VERSION_NUM_LENGTH
    }
    assert not too_long, (
        "revision ids must fit alembic_version.version_num "
        f"(VARCHAR({VERSION_NUM_LENGTH})); MySQL rejects these: {too_long}"
    )


def test_the_revision_chain_is_linear_and_reaches_one_head() -> None:
    """A branched chain would make `upgrade head` ambiguous on a client instance."""
    script = ScriptDirectory.from_config(_alembic_config("sqlite://"))
    heads = script.get_heads()
    assert len(heads) == 1, f"expected exactly one head, found {heads}"
    revisions = list(script.walk_revisions())
    for revision in revisions:
        assert not isinstance(revision.down_revision, tuple), (
            f"{revision.revision} is a merge point; the chain must stay linear"
        )
    assert len(revisions) == len({r.revision for r in revisions})


# ── media_assets.original_filename uniqueness ────────────────────────────────
BEFORE_UNIQUE_FILENAMES = "0009_invoice_issuer_snapshot"
UNIQUE_FILENAME_INDEX = "ix_media_assets_original_filename"

_INSERT_MEDIA = text(
    "INSERT INTO media_assets "
    "(original_filename, stored_key, content_type, size_bytes, url, storage_provider,"
    " created_at) "
    "VALUES (:name, :key, 'image/png', 1, :url, 'local', '2026-01-01 00:00:00')"
)


def _insert_media(connection, name: str, key: str) -> None:
    connection.execute(_INSERT_MEDIA, {"name": name, "key": key, "url": f"/media/{key}"})


def _media_filename_indexes(engine) -> list[dict]:
    return [
        index
        for index in inspect(engine).get_indexes("media_assets")
        if index["column_names"] == ["original_filename"]
    ]


def test_the_migrated_schema_refuses_two_assets_with_one_filename(tmp_path, monkeypatch) -> None:
    url = _disposable_url(tmp_path, monkeypatch)
    command.upgrade(_alembic_config(url), "head")

    engine = build_engine(url)
    try:
        indexes = _media_filename_indexes(engine)
        assert [index["unique"] for index in indexes] == [True], indexes

        with engine.begin() as connection:
            _insert_media(connection, "photo.png", "a.png")
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                _insert_media(connection, "photo.png", "b.png")
    finally:
        engine.dispose()


def test_downgrade_drops_only_the_filename_uniqueness(tmp_path, monkeypatch) -> None:
    url = _disposable_url(tmp_path, monkeypatch)
    config = _alembic_config(url)
    command.upgrade(config, "head")

    engine = build_engine(url)
    try:
        with engine.begin() as connection:
            _insert_media(connection, "photo.png", "a.png")

        command.downgrade(config, BEFORE_UNIQUE_FILENAMES)

        assert _media_filename_indexes(engine) == []
        with engine.begin() as connection:
            # The rows survive, and the name may be reused again.
            _insert_media(connection, "photo.png", "b.png")
            assert connection.execute(text("SELECT COUNT(*) FROM media_assets")).scalar() == 2
    finally:
        engine.dispose()


def test_upgrade_refuses_a_database_with_duplicate_media_filenames(tmp_path, monkeypatch) -> None:
    """Duplicates are the owner's data; the migration reports them, it never picks one."""
    url = _disposable_url(tmp_path, monkeypatch)
    config = _alembic_config(url)
    command.upgrade(config, BEFORE_UNIQUE_FILENAMES)

    engine = build_engine(url)
    try:
        with engine.begin() as connection:
            _insert_media(connection, "photo.png", "a.png")
            _insert_media(connection, "photo.png", "b.png")
            _insert_media(connection, "other.png", "c.png")

        with pytest.raises(Exception) as failure:
            command.upgrade(config, "head")
        message = str(failure.value)
        assert "photo.png" in message
        assert "other.png" not in message

        # Nothing deleted, nothing renamed, and no half-applied uniqueness left behind.
        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT original_filename, stored_key FROM media_assets ORDER BY id")
            ).all()
        assert rows == [("photo.png", "a.png"), ("photo.png", "b.png"), ("other.png", "c.png")]
        assert _media_filename_indexes(engine) == []

        with engine.connect() as connection:
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
        assert version == BEFORE_UNIQUE_FILENAMES
    finally:
        engine.dispose()
