"""Safely inspect and prepare an already imported local Production mirror."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import case, delete, func, inspect, select, text, update
from sqlalchemy.engine import make_url

from app.db.base import metadata_with_models

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MEDIA_ROOT = BACKEND_ROOT / "data" / "tara_prod_mirror_uploads"
ALEMBIC_CONFIG = Config(str(BACKEND_ROOT / "alembic.ini"))
ALEMBIC_CONFIG.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
HEADS = tuple(ScriptDirectory.from_config(ALEMBIC_CONFIG).get_heads())

REMOVE_TABLES = (
    "order_activities", "invoice_items", "order_item_package_components",
    "order_status_history", "order_items", "invoices", "orders",
    "invoice_sequences", "audit_logs", "analytics_events",
    "analytics_product_views", "analytics_sessions", "admin_login_throttles",
    "admin_users",
)
SENSITIVE_TABLES = REMOVE_TABLES
CATALOG_TABLES = (
    "categories", "products", "product_images", "product_specifications",
    "product_options", "product_option_values", "product_option_value_images",
    "product_variant_option_values", "product_variants", "package_items",
    "home_sections", "static_pages", "hero_slides", "delivery_areas", "coupons",
    "store_settings", "media_assets", "translations", "instance_metadata",
    "import_batches", "import_batch_records",
)
MEDIA_COLUMNS = {
    "categories": ("image_url", "banner_image_url"),
    "hero_slides": ("image_url",),
    "product_images": ("url",),
    "product_option_value_images": ("url",),
    "store_settings": ("logo_url", "favicon_url"),
}


class MirrorError(RuntimeError):
    """A safe, user-displayable refusal without connection or row contents."""


def validate_target(app_env: str | None, database_url: str | None):
    if app_env != "development":
        raise MirrorError("APP_ENV must be development")
    if not database_url:
        raise MirrorError("DATABASE_URL must point to the local mirror")
    try:
        url = make_url(database_url)
    except Exception:
        raise MirrorError("DATABASE_URL is invalid") from None
    if url.get_backend_name() != "mysql":
        raise MirrorError("DATABASE_URL must use MySQL")
    if url.host not in {"127.0.0.1", "localhost"}:
        raise MirrorError("Database host must be 127.0.0.1 or localhost")
    if url.port != 3307:
        raise MirrorError("Database port must be 3307")
    if url.database != "tara_prod_mirror":
        raise MirrorError("Database name must be tara_prod_mirror")
    return url


def require_confirmation(execute: bool, confirmed: bool) -> None:
    if execute != confirmed:
        raise MirrorError("Destructive mode requires --execute and --confirm-local-mirror")


def assert_at_head(connection) -> tuple[str, ...]:
    current = tuple(sorted(MigrationContext.configure(connection).get_current_heads()))
    heads = tuple(sorted(ScriptDirectory.from_config(ALEMBIC_CONFIG).get_heads()))
    if current != heads:
        raise MirrorError("Local mirror database is not at the current Alembic head")
    return current


def _metadata_and_schema(connection):
    expected = metadata_with_models()
    names = set(inspect(connection).get_table_names())
    missing = (set(expected.tables) | {"alembic_version"}) - names
    if missing:
        raise MirrorError("Local mirror schema is incomplete")
    if connection.dialect.name == "mysql":
        engines = connection.execute(text(
            "SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()"
        )).scalars().all()
        if any(str(engine).upper() != "INNODB" for engine in engines):
            raise MirrorError("All local mirror tables must use transactional InnoDB")
        if not connection.execute(text("SELECT @@FOREIGN_KEY_CHECKS")).scalar_one():
            raise MirrorError("MySQL foreign key checks must be enabled")
    return expected


def _table_counts(connection, metadata):
    return {name: int(connection.execute(select(func.count()).select_from(metadata.tables[name])).scalar_one())
            for name in sorted(metadata.tables)}


def _preserved_fingerprints(connection, metadata):
    result = {}
    for name, table in sorted(metadata.tables.items()):
        if name in REMOVE_TABLES:
            continue
        columns = [column for column in table.c if not (
            (name == "coupons" and column.name == "used_count")
            or (name == "media_assets" and column.name == "uploaded_by_id")
        )]
        digest = hashlib.sha256()
        ordering = list(table.primary_key.columns)
        for row in connection.execute(select(*columns).order_by(*ordering)):
            digest.update(json.dumps(list(row), default=str, ensure_ascii=False).encode())
            digest.update(b"\n")
        result[name] = digest.digest()
    return result


def apply_sanitization(connection, metadata) -> None:
    tables = metadata.tables if hasattr(metadata, "tables") else metadata
    if "media_assets" in tables and "uploaded_by_id" in tables["media_assets"].c:
        connection.execute(update(tables["media_assets"]).values(uploaded_by_id=None))
    invoices = tables["invoices"]
    if "replacement_invoice_id" in invoices.c:
        connection.execute(update(invoices).values(replacement_invoice_id=None))
    for name in REMOVE_TABLES:
        connection.execute(delete(tables[name]))
    connection.execute(update(tables["coupons"]).values(used_count=0))


@contextmanager
def _activity_delete_guard(connection):
    if connection.dialect.name != "mysql":
        yield
        return
    lock = connection.execute(text(
        "SELECT GET_LOCK(CONCAT('tara-prelaunch:', DATABASE()), 0)"
    )).scalar_one()
    if lock != 1:
        raise MirrorError("Could not acquire the local activity-table maintenance lock")
    try:
        connection.execute(text("SET @tara_sanitize_transactions = 1"))
        yield
    finally:
        connection.execute(text("SET @tara_sanitize_transactions = NULL"))
        connection.execute(text(
            "SELECT RELEASE_LOCK(CONCAT('tara-prelaunch:', DATABASE()))"
        ))


def audit_database(engine):
    with engine.connect() as connection:
        with connection.begin():
            revision = assert_at_head(connection)
            metadata = _metadata_and_schema(connection)
            counts = _table_counts(connection, metadata)
            providers = connection.execute(
                select(metadata.tables["media_assets"].c.storage_provider,
                       func.count()).group_by(metadata.tables["media_assets"].c.storage_provider)
            ).all()
    return {
        "safe_target": True,
        "alembic_revision": list(revision),
        "sensitive_row_counts": {name: counts[name] for name in SENSITIVE_TABLES},
        "catalog_row_counts": {name: counts[name] for name in CATALOG_TABLES},
        "home_section_rows": counts["home_sections"],
        "media_provider_counts": {str(name): int(total) for name, total in providers},
    }


def sanitize_database(engine, *, execute=False, confirmed=False):
    require_confirmation(execute, confirmed)
    validate_target(os.environ.get("APP_ENV"), engine.url.render_as_string(hide_password=False))
    with engine.connect() as connection:
        with connection.begin():
            assert_at_head(connection)
            metadata = _metadata_and_schema(connection)
            before = _table_counts(connection, metadata)
            if not execute:
                return {"mode": "dry-run", "before": {name: before[name] for name in SENSITIVE_TABLES},
                        "projected_after": {name: 0 for name in SENSITIVE_TABLES},
                        "coupon_rows_reset": before["coupons"]}
            preserved = _preserved_fingerprints(connection, metadata)
            with _activity_delete_guard(connection):
                apply_sanitization(connection, metadata)
            after = _table_counts(connection, metadata)
            if any(after[name] for name in REMOVE_TABLES):
                raise MirrorError("Sanitization verification failed; transaction rolled back")
            if _preserved_fingerprints(connection, metadata) != preserved:
                raise MirrorError("Preserved data verification failed; transaction rolled back")
    return {"mode": "execute", "before": {name: before[name] for name in SENSITIVE_TABLES},
            "after": {name: after[name] for name in SENSITIVE_TABLES},
            "coupon_rows_reset": after["coupons"]}


def media_path(root: Path, stored_key: str) -> Path:
    if (not stored_key or "\\" in stored_key or "\x00" in stored_key
            or any(char in stored_key for char in (":", "?", "#", "%"))
            or stored_key.startswith("/")
            or any(part in {"", ".", ".."} for part in stored_key.split("/"))):
        raise MirrorError("Unsafe media key in local mirror")
    root_resolved = root.resolve()
    destination = root.joinpath(*PurePosixPath(stored_key).parts)
    try:
        destination.resolve().relative_to(root_resolved)
    except ValueError:
        raise MirrorError("Unsafe media path outside local media directory") from None
    return destination


def _validate_source_base(source_base_url: str) -> str:
    parsed = urlsplit(source_base_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise MirrorError("Source base URL must be a credential-free HTTPS URL")
    return source_base_url.rstrip("/")


def download_file(url: str, destination: Path) -> None:
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(url, timeout=30) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def rewrite_media_references(connection, mapping: dict[str, str]) -> None:
    if not mapping:
        return
    metadata = metadata_with_models()
    for name, columns in MEDIA_COLUMNS.items():
        table = metadata.tables[name]
        for column_name in columns:
            connection.execute(update(table).where(table.c[column_name].in_(mapping)).values(
                {column_name: case(mapping, value=table.c[column_name])}
            ))


def mirror_media(engine, source_base_url: str, media_root: Path = MEDIA_ROOT, *,
                 execute=False, confirmed=False, downloader=None):
    require_confirmation(execute, confirmed)
    validate_target(os.environ.get("APP_ENV"), engine.url.render_as_string(hide_password=False))
    source_base = _validate_source_base(source_base_url)
    downloader = downloader or download_file
    with engine.connect() as connection:
        with connection.begin():
            assert_at_head(connection)
            metadata = _metadata_and_schema(connection)
            assets = connection.execute(select(metadata.tables["media_assets"])).mappings().all()
    required = []
    for asset in assets:
        key = asset["stored_key"]
        target = media_path(media_root, key)
        old_url = f"{source_base}/{key}"
        if asset["url"] != old_url:
            raise MirrorError("A media asset URL does not match its stored key")
        required.append((asset, target, old_url, f"/media/{key}"))

    if not execute:
        return {"mode": "dry-run", "media_assets": len(required)}

    failures = 0
    media_root.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="tara-mirror-", dir=media_root.parent) as staging:
            staged = []
            for index, (asset, target, old_url, new_url) in enumerate(required):
                if target.is_file() and target.stat().st_size == asset["size_bytes"]:
                    staged.append((asset, target, old_url, new_url, None))
                    continue
                temp_path = Path(staging) / str(index)
                try:
                    downloader(old_url, temp_path)
                    if temp_path.stat().st_size != asset["size_bytes"]:
                        raise OSError("size mismatch")
                    staged.append((asset, target, old_url, new_url, temp_path))
                except Exception:
                    failures += 1
            if failures:
                raise MirrorError(f"Media downloads failed: {failures}")
            for _, target, _, _, temp_path in staged:
                if temp_path is not None:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temp_path.replace(target)

        mapping = {old: new for _, _, old, new in required}
        with engine.connect() as connection:
            with connection.begin():
                assert_at_head(connection)
                metadata = _metadata_and_schema(connection)
                table = metadata.tables["media_assets"]
                for asset, _, old_url, new_url in required:
                    connection.execute(update(table).where(table.c.id == asset["id"]).values(
                        storage_provider="local", url=new_url, thumbnail_url=None,
                    ))
                rewrite_media_references(connection, mapping)
                for _, target, _, _, _ in staged:
                    if not target.is_file():
                        raise MirrorError("Rewritten media file verification failed")
                for name, columns in MEDIA_COLUMNS.items():
                    ref_table = metadata.tables[name]
                    for column_name in columns:
                        urls = connection.execute(select(ref_table.c[column_name]).where(
                            ref_table.c[column_name].in_(mapping.values())
                        )).scalars().all()
                        for url in urls:
                            target = media_path(media_root, str(url)[len("/media/"):])
                            if not target.is_file():
                                raise MirrorError("Rewritten media reference has no local file")
    except MirrorError:
        raise
    except Exception:
        raise MirrorError("Media mirroring failed; database URLs were not rewritten") from None
    return {"media_assets": len(required), "downloaded": sum(item[4] is not None for item in staged),
            "skipped_existing": sum(item[4] is None for item in staged),
            "references_checked": len(MEDIA_COLUMNS)}


def safe_report(report):
    """Expose only aggregate report values; never serialize database row data."""
    if not isinstance(report, dict):
        return {"sensitive_values_omitted": True}
    output = {key: value for key, value in report.items()
            if key in {"safe_target", "alembic_revision", "sensitive_row_counts",
                       "catalog_row_counts", "home_section_rows", "media_provider_counts",
                       "mode", "before", "after", "projected_after", "coupon_rows_reset",
                       "media_assets", "downloaded",
                       "skipped_existing", "references_checked"}}
    output["sensitive_values_omitted"] = True
    return output


def _engine_and_target():
    url = validate_target(os.environ.get("APP_ENV"), os.environ.get("DATABASE_URL"))
    from sqlalchemy import create_engine
    return create_engine(url, pool_pre_ping=True, hide_parameters=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("audit", help="Read-only local mirror audit")
    sanitize = commands.add_parser("sanitize", help="Remove local operational and customer data")
    media = commands.add_parser("media", help="Download public media and rewrite local URLs")
    for command in (sanitize, media):
        command.add_argument("--execute", action="store_true")
        command.add_argument("--confirm-local-mirror", action="store_true")
    media.add_argument("--source-base-url", required=True)
    args = parser.parse_args(argv)
    engine = None
    try:
        if args.command != "audit":
            require_confirmation(args.execute, args.confirm_local_mirror)
        engine = _engine_and_target()
        report = (audit_database(engine) if args.command == "audit" else
                  sanitize_database(engine, execute=args.execute,
                                    confirmed=args.confirm_local_mirror)
                  if args.command == "sanitize" else
                  mirror_media(engine, args.source_base_url, execute=args.execute,
                               confirmed=args.confirm_local_mirror))
        print(json.dumps(safe_report(report), ensure_ascii=False, indent=2))
        return 0
    except MirrorError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Local mirror operation failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
