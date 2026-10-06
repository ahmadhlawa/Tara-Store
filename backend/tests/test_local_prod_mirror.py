from datetime import datetime
from io import BytesIO
from unittest.mock import Mock

import pytest
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    insert,
    select,
)

from app.db.base import metadata_with_models
from scripts import prepare_local_prod_mirror as mirror


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'mirror.db').as_posix()}")
    metadata = metadata_with_models()
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.exec_driver_sql("INSERT INTO alembic_version VALUES (?)", (mirror.HEADS[0],))
    yield engine
    engine.dispose()


@pytest.mark.parametrize("app_env,url", [
    ("production", "mysql+pymysql://user:secret@127.0.0.1:3307/tara_prod_mirror"),
    ("development", "sqlite:///tara_prod_mirror.db"),
    ("development", "mysql+pymysql://user:secret@prod.example:3307/tara_prod_mirror"),
    ("development", "mysql+pymysql://user:secret@127.0.0.1:3307/other"),
    ("development", "mysql+pymysql://user:secret@127.0.0.1/tara_prod_mirror"),
    ("development", "mysql+pymysql://user:secret@localhost/tara_prod_mirror"),
    ("development", "mysql+pymysql://user:secret@127.0.0.1:3306/tara_prod_mirror"),
    ("development", "mysql+pymysql://user:secret@localhost:3306/tara_prod_mirror"),
])
def test_target_guard_rejects_unsafe_targets(app_env, url):
    with pytest.raises(mirror.MirrorError):
        mirror.validate_target(app_env, url)


def test_target_guard_accepts_only_exact_local_mirror():
    url = mirror.validate_target(
        "development", "mysql+pymysql://user:secret@127.0.0.1:3307/tara_prod_mirror"
    )
    assert url.host == "127.0.0.1" and url.port == 3307 and url.database == "tara_prod_mirror"


def test_target_guard_accepts_localhost_on_isolated_port():
    url = mirror.validate_target(
        "development", "mysql+pymysql://user:secret@localhost:3307/tara_prod_mirror"
    )
    assert url.host == "localhost" and url.port == 3307


@pytest.mark.parametrize("execute,confirmed", [(True, False), (False, True)])
def test_destructive_mode_requires_both_flags(execute, confirmed):
    with pytest.raises(mirror.MirrorError, match="--execute"):
        mirror.require_confirmation(execute, confirmed)


def test_both_execution_flags_off_is_a_safe_dry_run():
    assert mirror.require_confirmation(False, False) is None


def test_sanitize_deletes_only_sensitive_rows_and_resets_coupon():
    metadata = MetaData()
    tables = {name: Table(name, metadata, Column("id", Integer, primary_key=True))
              for name in mirror.REMOVE_TABLES}
    tables["invoices"].append_column(Column("replacement_invoice_id", Integer, nullable=True))
    fixed_updated_at = datetime(2025, 1, 2, 3, 4, 5)
    automatic_updated_at = datetime(2026, 2, 3, 4, 5, 6)
    coupons = Table("coupons", metadata, Column("id", Integer, primary_key=True),
                    Column("code", String), Column("used_count", Integer),
                    Column("updated_at", DateTime, onupdate=lambda: automatic_updated_at))
    category = Table("categories", metadata, Column("id", Integer, primary_key=True),
                     Column("parent_id", Integer), Column("name", String),
                     Column("show_on_home", Integer))
    assets = Table("media_assets", metadata, Column("id", Integer, primary_key=True),
                   Column("uploaded_by_id", Integer), Column("stored_key", String))
    product = Table("products", metadata, Column("id", Integer, primary_key=True),
                    Column("category_id", Integer), Column("stock_quantity", Integer),
                    Column("show_on_home", Integer))
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    with engine.begin() as conn:
        for name in mirror.REMOVE_TABLES:
            conn.execute(insert(tables[name]).values(id=1, **(
                {"replacement_invoice_id": 1} if name == "invoices" else {}
            )))
        conn.execute(insert(coupons).values(
            id=1, code="SAFE-TEST", used_count=9, updated_at=fixed_updated_at,
        ))
        conn.execute(insert(category).values([
            {"id": 1, "parent_id": None, "name": "Parent", "show_on_home": 1},
            {"id": 2, "parent_id": 1, "name": "Child", "show_on_home": 0},
        ]))
        conn.execute(insert(product).values(
            id=1, category_id=2, stock_quantity=17, show_on_home=1,
        ))
        conn.execute(insert(assets).values(
            id=1, uploaded_by_id=42, stored_key="catalog/a.png",
        ))
        mirror.apply_sanitization(conn, {**tables, "coupons": coupons, "categories": category,
                                        "media_assets": assets})
    with engine.connect() as conn:
        assert all(conn.execute(select(tables[name])).first() is None for name in mirror.REMOVE_TABLES)
        coupon = conn.execute(select(coupons)).mappings().one()
        retained = conn.execute(select(category).order_by(category.c.id)).mappings().all()
        retained_product = conn.execute(select(product)).mappings().one()
        retained_asset = conn.execute(select(assets)).mappings().one()
    assert coupon["used_count"] == 0 and coupon["code"] == "SAFE-TEST"
    assert coupon["updated_at"] == fixed_updated_at
    assert [(row["parent_id"], row["name"], row["show_on_home"]) for row in retained] == [
        (None, "Parent", 1), (1, "Child", 0),
    ]
    assert (retained_product["stock_quantity"], retained_product["show_on_home"]) == (17, 1)
    assert retained_asset["stored_key"] == "catalog/a.png" and retained_asset["uploaded_by_id"] is None
    engine.dispose()


@pytest.mark.parametrize("key", ["../escape.jpg", "/absolute.jpg", "C:/escape.jpg",
                                 "a\\b.jpg", "a?b.jpg", "a%2f..%2fescape.jpg"])
def test_unsafe_media_keys_rejected(key, tmp_path):
    with pytest.raises(mirror.MirrorError):
        mirror.media_path(tmp_path, key)


def test_url_mapping_rewrites_only_known_media_asset_references(db):
    metadata = metadata_with_models()
    old = "https://media.example.test/assets/a.png"
    new = "/media/assets/a.png"
    with db.begin() as conn:
        conn.execute(insert(metadata.tables["media_assets"]).values(
            original_filename="a.png", stored_key="assets/a.png", content_type="image/png",
            size_bytes=1, url=old, storage_provider="r2",
        ))
        conn.execute(insert(metadata.tables["categories"]).values(
            name="A", slug="a", image_url=old, banner_image_url="https://elsewhere.test/x",
        ))
        conn.execute(insert(metadata.tables["hero_slides"]).values(title="slide", image_url=old))
    with db.begin() as conn:
        mirror.rewrite_media_references(conn, {old: new})
    with db.connect() as conn:
        category = conn.execute(select(metadata.tables["categories"])).mappings().one()
        slide = conn.execute(select(metadata.tables["hero_slides"])).mappings().one()
    assert category["image_url"] == new
    assert category["banner_image_url"] == "https://elsewhere.test/x"
    assert slide["image_url"] == new


def test_download_file_sends_explicit_user_agent_without_redirects(tmp_path, monkeypatch):
    opener = Mock()
    opener.open.return_value = BytesIO(b"image bytes")
    build_opener = Mock(return_value=opener)
    monkeypatch.setattr(mirror.urllib.request, "build_opener", build_opener)
    url = "https://media.example.test/assets/a.jpg"
    destination = tmp_path / "a.jpg"

    mirror.download_file(url, destination)

    build_opener.assert_called_once()
    assert isinstance(build_opener.call_args.args[0], mirror._NoRedirect)
    opener.open.assert_called_once()
    request = opener.open.call_args.args[0]
    assert isinstance(request, mirror.urllib.request.Request)
    assert request.full_url == url
    assert request.get_header("User-agent") == "Mozilla/5.0 (compatible; TaraLocalMirror/1.0)"
    assert opener.open.call_args.kwargs == {"timeout": 30}
    assert destination.read_bytes() == b"image bytes"


def test_failed_media_download_does_not_rewrite_database(db, tmp_path, monkeypatch):
    metadata = metadata_with_models()
    old = "https://media.example.test/assets/a.png"
    with db.begin() as conn:
        conn.execute(insert(metadata.tables["media_assets"]).values(
            original_filename="a.png", stored_key="assets/a.png", content_type="image/png",
            size_bytes=1, url=old, storage_provider="r2",
        ))

    def fail_download(*args, **kwargs):
        raise OSError("private detail must not be reported")

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr(mirror, "validate_target", lambda *args: None)
    monkeypatch.setattr(mirror, "download_file", fail_download)
    with pytest.raises(mirror.MirrorError):
        mirror.mirror_media(db, "https://media.example.test", tmp_path,
                            execute=True, confirmed=True)
    with db.connect() as conn:
        row = conn.execute(select(metadata.tables["media_assets"])).mappings().one()
    assert row["storage_provider"] == "r2" and row["url"] == old


def test_reports_contain_counts_only_and_no_sensitive_values():
    sensitive = "Customer Name 0590000000 customer@example.test super-secret-hash"
    report = mirror.safe_report({"customer": sensitive, "token": sensitive})
    assert sensitive not in str(report)
    assert report["sensitive_values_omitted"] is True
