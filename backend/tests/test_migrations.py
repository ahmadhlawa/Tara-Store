"""The Alembic revision, not create_all, is the schema of record."""

from __future__ import annotations

from pathlib import Path
from decimal import Decimal

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
    "admin_login_throttles",
    "analytics_events",
    "analytics_product_views",
    "analytics_sessions",
    "admin_users",
    "audit_logs",
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
    "product_option_value_images",
    "product_option_values",
    "product_options",
    "product_specifications",
    "product_variant_option_values",
    "product_variants",
    "products",
    "static_pages",
    "store_settings",
    "translations",
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
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        category_columns = {column["name"] for column in inspector.get_columns("categories")}
    finally:
        engine.dispose()

    assert EXPECTED_TABLES.issubset(tables)
    assert "alembic_version" in tables
    assert "banner_image_url" in category_columns


def test_models_and_expected_tables_agree() -> None:
    assert set(metadata_with_models().tables) == EXPECTED_TABLES


def test_stock_override_migration_preserves_data_and_other_checks_then_downgrades(tmp_path, monkeypatch):
    from sqlalchemy.orm import Session
    from app.models import ProductVariant
    from tests.conftest import make_product
    url = _disposable_url(tmp_path, monkeypatch)
    config = _alembic_config(url)
    command.upgrade(config, "0031_order_lifecycle")
    engine = build_engine(url)
    try:
        with Session(engine) as db:
            product = make_product(db, stock=7)
            db.add(ProductVariant(product_id=product.id, title="Large", stock_quantity=5))
            db.commit()
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO orders (id,order_number,public_token,status,customer_name,customer_phone,address,delivery_fee,subtotal,discount,total,payment_method,created_at,updated_at) VALUES (1,'B4','b4-token','completed','Customer','0591234567','Address',0,10,0,10,'cash_on_delivery','2026-01-01','2026-01-01')"))
            connection.execute(text("INSERT INTO order_status_history (order_id,old_status,new_status,created_at) VALUES (1,'ready','completed','2026-01-01')"))
            connection.execute(text("INSERT INTO order_activities (order_id,event_type,created_at) VALUES (1,'order_completed','2026-01-01')"))
            connection.execute(text("INSERT INTO order_items (order_id,product_id,variant_id,product_name,original_product_name,selected_option_value_ids,unit_price,quantity,line_total) VALUES (1,1,1,'Historical product','Historical product','[]',10,1,10)"))
            connection.execute(text("INSERT INTO invoices (id,invoice_number,order_id,status,active_invoice_marker,issued_at,order_number,source,payment_method,store_name,customer_name,customer_phone,delivery_address,currency_code,currency_symbol,subtotal,discount,delivery_fee,tax_enabled,tax_rate,prices_include_tax,tax_amount,grand_total,created_at,updated_at) VALUES (1,'INV-B4',1,'active','active','2026-01-01','B4','website','cash_on_delivery','Store','Customer','0591234567','Address','ILS','ILS',10,0,0,0,0,0,0,10,'2026-01-01','2026-01-01')"))
            connection.execute(text("INSERT INTO invoice_items (invoice_id,product_name,unit_price,quantity,line_total) VALUES (1,'Historical product',10,1,10)"))
            tables = ("products", "product_variants", "orders", "order_items", "order_status_history", "order_activities", "invoices", "invoice_items", "invoice_sequences")
            before = {table: connection.execute(text(f"SELECT * FROM {table}")).all() for table in tables}
        checks_before = {table: {c["name"] for c in inspect(engine).get_check_constraints(table)} for table in ("products", "product_variants", "order_items", "invoice_items", "package_items")}
        command.upgrade(config, "head")
        for table, removed in (("products", "ck_products_stock_non_negative"), ("product_variants", "ck_variants_stock_non_negative")):
            assert {c["name"] for c in inspect(engine).get_check_constraints(table)} == checks_before[table] - {removed}
        for table in ("order_items", "invoice_items", "package_items"):
            assert {c["name"] for c in inspect(engine).get_check_constraints(table)} == checks_before[table]
        with engine.begin() as connection:
            for table in tables:
                assert connection.execute(text(f"SELECT * FROM {table}")).all() == before[table]
            connection.execute(text("UPDATE products SET stock_quantity=-2"))
            connection.execute(text("UPDATE product_variants SET stock_quantity=-3"))
        for table in ("products", "product_variants"):
            with engine.begin() as connection:
                connection.execute(text(f"UPDATE {table} SET stock_quantity=4"))
        command.downgrade(config, "0031_order_lifecycle")
        with engine.connect() as connection:
            assert connection.execute(text("SELECT stock_quantity FROM product_variants")).scalar_one() == 4
            assert connection.execute(text("SELECT product_id,variant_id FROM order_items")).one() == (1, 1)
            for table in tables[2:]:
                assert connection.execute(text(f"SELECT * FROM {table}")).all() == before[table]
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
            assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        for table in ("products", "product_variants"):
            assert {c["name"] for c in inspect(engine).get_check_constraints(table)} == checks_before[table]
            with pytest.raises(IntegrityError), engine.begin() as connection:
                connection.execute(text(f"UPDATE {table} SET stock_quantity=-1"))
    finally:
        engine.dispose()


@pytest.mark.parametrize("negative_table", ["products", "product_variants"])
def test_stock_override_downgrade_preflights_all_tables_without_clamping(tmp_path, monkeypatch, negative_table):
    from sqlalchemy.orm import Session
    from app.models import ProductVariant
    from tests.conftest import make_product
    url = _disposable_url(tmp_path, monkeypatch)
    config = _alembic_config(url)
    command.upgrade(config, "0032_admin_stock_override")
    engine = build_engine(url)
    try:
        with Session(engine) as db:
            product = make_product(db, stock=1)
            db.add(ProductVariant(product_id=product.id, title="Large", stock_quantity=1))
            db.commit()
        with engine.begin() as connection:
            connection.execute(text(f"UPDATE {negative_table} SET stock_quantity=-3"))
        with pytest.raises(RuntimeError, match="negative stock"):
            command.downgrade(config, "0031_order_lifecycle")
        with engine.connect() as connection:
            assert connection.execute(text(f"SELECT stock_quantity FROM {negative_table}")).scalar_one() == -3
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0032_admin_stock_override"
        for table, name in (("products", "ck_products_stock_non_negative"), ("product_variants", "ck_variants_stock_non_negative")):
            assert name not in {c["name"] for c in inspect(engine).get_check_constraints(table)}
    finally:
        engine.dispose()


def test_order_lifecycle_migration_changes_only_current_status_and_lock(tmp_path, monkeypatch) -> None:
    url = _disposable_url(tmp_path, monkeypatch)
    config = _alembic_config(url)
    command.upgrade(config, "0030_order_packaging")
    engine = build_engine(url)
    try:
        with engine.begin() as connection:
            for index, status in enumerate(("confirmed", "delivered", "new", "ready", "completed", "cancelled", "pending"), 1):
                connection.execute(text(
                    "INSERT INTO orders (id,order_number,public_token,status,is_locked,customer_name,customer_phone,"
                    "address,delivery_fee,subtotal,discount,total,payment_method,created_at,updated_at) VALUES "
                    "(:id,:number,:token,:status,1,'Customer','0591234567','Address',0,10,0,10,"
                    "'cash_on_delivery','2026-01-01','2026-01-01')"
                ), {"id": index, "number": f"LEGACY-{index}", "token": f"token-{index}", "status": status})
            connection.execute(text(
                "INSERT INTO order_status_history (order_id,old_status,new_status,created_at) "
                "VALUES (1,'pending','confirmed','2026-01-01'),(2,'confirmed','delivered','2026-01-01')"
            ))
            connection.execute(text(
                "INSERT INTO order_activities (order_id,event_type,before_data,after_data,created_at) "
                "VALUES (2,'order_status_changed','{\"status\":\"confirmed\"}','{\"status\":\"delivered\"}','2026-01-01')"
            ))
            connection.execute(text(
                "INSERT INTO invoices (id,invoice_number,order_id,status,issued_at,order_number,source,"
                "payment_method,store_name,customer_name,customer_phone,delivery_address,currency_code,"
                "currency_symbol,subtotal,discount,delivery_fee,tax_enabled,tax_rate,prices_include_tax,"
                "tax_amount,grand_total,created_at,updated_at) VALUES "
                "(1,'INV-LEGACY-2',2,'active','2026-01-01','LEGACY-2','website','cash_on_delivery',"
                "'Store','Customer','0591234567','Address','ILS','ILS',10,0,0,0,0,0,0,10,'2026-01-01','2026-01-01')"
            ))
            preserved = {table: connection.execute(text(f"SELECT * FROM {table}")).all()
                         for table in ("order_status_history", "order_activities", "invoices", "invoice_sequences")}
            orders_before = connection.execute(text("SELECT id,order_number,public_token,total,created_at,updated_at FROM orders ORDER BY id")).all()
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert connection.execute(text("SELECT status FROM orders ORDER BY id")).scalars().all() == [
                "ready", "completed", "new", "ready", "completed", "cancelled", "pending"
            ]
            assert not any(connection.execute(text("SELECT is_locked FROM orders")).scalars())
            assert connection.execute(text("SELECT id,order_number,public_token,total,created_at,updated_at FROM orders ORDER BY id")).all() == orders_before
            for table, rows in preserved.items():
                assert connection.execute(text(f"SELECT * FROM {table}")).all() == rows
    finally:
        engine.dispose()


def test_packaging_migration_defaults_historical_orders_and_invoices(tmp_path, monkeypatch) -> None:
    url = _disposable_url(tmp_path, monkeypatch)
    config = _alembic_config(url)
    command.upgrade(config, "0029_storefront_analytics")
    engine = build_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO orders (id,order_number,public_token,status,customer_name,customer_phone,"
                "address,delivery_fee,subtotal,discount,total,payment_method,created_at,updated_at) VALUES "
                "(1,'LEGACY-1','legacy-token','completed','Legacy Customer','0591234567',"
                "'Legacy Address',20,200,10,210,'cash_on_delivery','2026-01-01','2026-01-01')"
            ))
            connection.execute(text(
                "INSERT INTO invoices (id,invoice_number,order_id,status,issued_at,order_number,source,"
                "payment_method,store_name,customer_name,customer_phone,delivery_address,currency_code,"
                "currency_symbol,subtotal,discount,delivery_fee,tax_enabled,tax_rate,prices_include_tax,"
                "tax_amount,grand_total,created_at,updated_at) VALUES "
                "(1,'INV-LEGACY-1',1,'active','2026-01-01','LEGACY-1','website','cash_on_delivery',"
                "'Legacy Store','Legacy Customer','0591234567','Legacy Address','ILS','ILS',"
                "200,10,20,0,0,0,0,210,'2026-01-01','2026-01-01')"
            ))
        command.upgrade(config, "head")
        inspector = inspect(engine)
        for table, total_column in (("orders", "total"), ("invoices", "grand_total")):
            columns = {column["name"]: column for column in inspector.get_columns(table)}
            assert "packaging_type" in columns, f"{table} must persist packaging"
            assert "packaging_fee" in columns, f"{table} must persist packaging fee"
            assert columns["packaging_type"]["nullable"] is False
            assert columns["packaging_fee"]["nullable"] is False
            assert columns["packaging_type"]["default"] is not None
            assert columns["packaging_fee"]["default"] is not None
            with engine.connect() as connection:
                row = connection.execute(text(
                    f"SELECT packaging_type,packaging_fee,{total_column} FROM {table} WHERE id=1"
                )).one()
            assert row[0] == "normal"
            assert Decimal(str(row[1])) == Decimal("0.00")
            assert Decimal(str(row[2])) == Decimal("210.00")
    finally:
        engine.dispose()


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


def test_translation_migration_compiles_for_mysql_without_backfill():
    import io
    import runpy
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    buffer = io.StringIO()
    context = MigrationContext.configure(dialect_name="mysql", opts={"as_sql": True, "output_buffer": buffer})
    with Operations.context(context):
        runpy.run_path(str(BACKEND_ROOT / "alembic/versions/0025_translations.py"))["upgrade"]()
    sql = buffer.getvalue()
    assert "CREATE TABLE translations" in sql and "AUTO_INCREMENT" in sql
    assert "UNIQUE" in sql and "CREATE INDEX ix_translations_status" in sql
    assert "INSERT INTO" not in sql


def test_packaging_migration_compiles_for_mysql():
    import io
    import runpy
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    script = ScriptDirectory.from_config(_alembic_config("sqlite://"))
    revisions = [revision for revision in script.walk_revisions()
                 if revision.down_revision == "0029_storefront_analytics"]
    assert len(revisions) == 1, "packaging needs a migration after the current schema"
    migration = runpy.run_path(revisions[0].path)
    buffer = io.StringIO()
    context = MigrationContext.configure(dialect_name="mysql", opts={"as_sql": True, "output_buffer": buffer})
    with Operations.context(context):
        migration["upgrade"]()
    sql = buffer.getvalue()
    for table in ("orders", "invoices"):
        assert f"ALTER TABLE {table} ADD COLUMN packaging_type" in sql
        assert f"ALTER TABLE {table} ADD COLUMN packaging_fee" in sql
    assert "NOT NULL DEFAULT 'normal'" in sql
    assert "NUMERIC(12, 2)" in sql


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


def test_category_order_backfill_uses_created_at_then_id_per_parent(tmp_path, monkeypatch) -> None:
    url = _disposable_url(tmp_path, monkeypatch)
    config = _alembic_config(url)
    command.upgrade(config, "0022_option_value_presentation")
    engine = build_engine(url)
    try:
        with engine.begin() as connection:
            base = "(id,parent_id,name,slug,is_active,is_featured,show_on_home,sort_order,created_at,updated_at)"
            connection.execute(text(
                f"INSERT INTO categories {base} VALUES "
                "(1,NULL,'Root','root',1,0,0,9,'2026-01-01','2026-01-01'),"
                "(2,1,'Later','later',1,0,0,9,'2026-01-03','2026-01-03'),"
                "(3,1,'Earlier','earlier',1,0,0,9,'2026-01-02','2026-01-02')"
            ))
        command.upgrade(config, "head")
        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT id, sort_order FROM categories WHERE parent_id=1 ORDER BY sort_order")
            ).all()
        assert rows == [(3, 0), (2, 1)]
    finally:
        engine.dispose()


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


def test_funnel_migration_adds_only_anonymous_events_and_preserves_history(tmp_path, monkeypatch):
    url = _disposable_url(tmp_path, monkeypatch)
    config = _alembic_config(url)
    command.upgrade(config, "0032_admin_stock_override")
    engine = build_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO analytics_sessions (id,session_token_hash,visitor_hash,started_at,last_activity_at,location_label) "
                "VALUES (1,:token,:visitor,'2026-01-01','2026-01-01','Unknown')"
            ), {"token": "a" * 64, "visitor": "b" * 64})
            connection.execute(text(
                "INSERT INTO analytics_product_views (session_id,product_id,product_slug_snapshot,product_name_snapshot,viewed_at) "
                "VALUES (1,999,'deleted-product','Historical product','2026-01-01')"
            ))
            # Snapshot every existing table, including Batch A/B business history.
            tables = inspect(connection).get_table_names()
            before = {table: connection.execute(text(f"SELECT * FROM {table}")).all()
                      for table in tables if table != "alembic_version"}
        command.upgrade(config, "head")
        inspector = inspect(engine)
        assert "analytics_events" in inspector.get_table_names()
        columns = {column["name"]: column for column in inspector.get_columns("analytics_events")}
        assert set(columns) == {"id", "session_id", "event_type", "occurred_at", "dedupe_key"}
        assert columns["dedupe_key"]["nullable"] is True
        assert all(columns[name]["nullable"] is False for name in ("session_id", "event_type", "occurred_at"))
        indexes = {tuple(index["column_names"]) for index in inspector.get_indexes("analytics_events")}
        assert ("event_type", "occurred_at") in indexes
        assert ("session_id", "occurred_at") in indexes
        assert any(constraint["column_names"] == ["dedupe_key"]
                   for constraint in inspector.get_unique_constraints("analytics_events"))
        fks = inspector.get_foreign_keys("analytics_events")
        assert len(fks) == 1
        assert fks[0]["referred_table"] == "analytics_sessions"
        assert fks[0]["options"]["ondelete"] == "CASCADE"
        with engine.begin() as connection:
            assert connection.execute(text("SELECT COUNT(*) FROM analytics_events")).scalar_one() == 0
            for table, rows in before.items():
                assert connection.execute(text(f"SELECT * FROM {table}")).all() == rows
            for event_type in ("add_to_cart", "checkout_reached", "order_completed"):
                connection.execute(text(
                    "INSERT INTO analytics_events (session_id,event_type,occurred_at,dedupe_key) "
                    "VALUES (1,:event_type,'2026-01-01',NULL)"
                ), {"event_type": event_type})
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO analytics_events (session_id,event_type,occurred_at) VALUES (1,'unsupported','2026-01-01')"
            ))
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO analytics_events (session_id,event_type,occurred_at,dedupe_key) "
                "VALUES (1,'order_completed','2026-01-01',:key)"
            ), {"key": "c" * 64})
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO analytics_events (session_id,event_type,occurred_at,dedupe_key) "
                "VALUES (1,'order_completed','2026-01-01',:key)"
            ), {"key": "c" * 64})
        command.downgrade(config, "0032_admin_stock_override")
        assert "analytics_events" not in inspect(engine).get_table_names()
        with engine.connect() as connection:
            for table, rows in before.items():
                assert connection.execute(text(f"SELECT * FROM {table}")).all() == rows
            assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        command.upgrade(config, "head")
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO analytics_events (session_id,event_type,occurred_at) VALUES (1,'add_to_cart','2026-01-01')"
            ))
            connection.execute(text("DELETE FROM analytics_sessions WHERE id=1"))
            assert connection.execute(text("SELECT COUNT(*) FROM analytics_events")).scalar_one() == 0
            assert connection.execute(text("SELECT COUNT(*) FROM analytics_product_views")).scalar_one() == 0
    finally:
        engine.dispose()


def test_funnel_migration_compiles_upgrade_and_downgrade_for_mysql():
    import io
    import runpy
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    script = ScriptDirectory.from_config(_alembic_config("sqlite://"))
    revisions = [revision for revision in script.walk_revisions()
                 if revision.down_revision == "0032_admin_stock_override"]
    assert len(revisions) == 1, "funnel needs the next migration after actual head 0032"
    migration = runpy.run_path(revisions[0].path)
    buffer = io.StringIO()
    context = MigrationContext.configure(dialect_name="mysql", opts={"as_sql": True, "output_buffer": buffer})
    with Operations.context(context):
        migration["upgrade"]()
        migration["downgrade"]()
    sql = buffer.getvalue()
    assert "CREATE TABLE analytics_events" in sql and "AUTO_INCREMENT" in sql
    assert "UNIQUE (dedupe_key)" in sql
    assert "FOREIGN KEY(session_id) REFERENCES analytics_sessions (id) ON DELETE CASCADE" in sql
    assert "CHECK (event_type IN ('add_to_cart', 'checkout_reached', 'order_completed'))" in sql
    assert "(event_type, occurred_at)" in sql and "(session_id, occurred_at)" in sql
    assert "DROP TABLE analytics_events" in sql
    assert "INSERT INTO" not in sql and "UPDATE " not in sql
