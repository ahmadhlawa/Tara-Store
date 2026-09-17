"""Offline, prelaunch-only transaction sanitation. Defaults to a read-only audit.

Use only while all application/import/translation writers are stopped and every
transaction is confirmed test data. No storage provider is imported or called.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from contextlib import contextmanager

from sqlalchemy import MetaData, and_, delete, func, inspect, select, text, update

from app.db.base import metadata_with_models
from app.db.session import build_engine

TABLES = (
    "order_activities", "invoice_items", "invoices", "invoice_sequences",
    "order_item_package_components", "order_items", "order_status_history",
    "orders", "audit_logs",
)
TRIGGERS = {"trg_order_activities_no_update", "trg_order_activities_no_delete"}
HEAD = "0026_prelaunch_sanitation"


class SanitationError(RuntimeError):
    pass


def _schema(connection):
    expected = metadata_with_models()
    inspector = inspect(connection)
    names = set(inspector.get_table_names())
    if names != set(expected.tables) | {"alembic_version"}:
        raise SanitationError("Unexpected schema tables; refuse to guess transaction dependencies")
    metadata = MetaData()
    metadata.reflect(connection)
    for name, table in expected.tables.items():
        actual = metadata.tables[name]
        if set(actual.c.keys()) != set(table.c.keys()):
            raise SanitationError(f"Unexpected columns in {name}")
        def signature(fk):
            return (tuple(c.name for c in fk.columns), tuple(e.target_fullname for e in fk.elements), fk.ondelete)
        if {signature(fk) for fk in actual.foreign_key_constraints} != {
            signature(fk) for fk in table.foreign_key_constraints
        }:
            raise SanitationError(f"Unexpected FK state in {name}")
        for fk in actual.foreign_key_constraints:
            elements = list(fk.elements)
            parent = elements[0].column.table
            child = actual.alias()
            match = and_(*(child.c[e.parent.name] == e.column for e in elements))
            populated = and_(*(child.c[e.parent.name].is_not(None) for e in elements))
            if connection.execute(select(child).where(
                populated, ~select(parent).where(match).exists()
            ).limit(1)).first() is not None:
                raise SanitationError(f"Orphaned FK data in {name}")
    if connection.dialect.name == "mysql":
        engines = connection.execute(text(
            "SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()"
        )).scalars().all()
        if any(str(engine).upper() != "INNODB" for engine in engines):
            raise SanitationError("All tables must use transactional InnoDB")
        if not connection.execute(text("SELECT @@FOREIGN_KEY_CHECKS")).scalar_one():
            raise SanitationError("Foreign key checks must be enabled")
    elif connection.dialect.name == "sqlite":
        if not connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one():
            raise SanitationError("Foreign key checks must be enabled")
    else:
        raise SanitationError("Only SQLite development copies and MySQL are supported")
    return metadata


def _counts(connection, metadata):
    result = {name: connection.execute(select(func.count()).select_from(table)).scalar_one()
              for name, table in sorted(metadata.tables.items())}
    result["coupon_used_count"] = connection.execute(
        select(func.coalesce(func.sum(metadata.tables["coupons"].c.used_count), 0))
    ).scalar_one()
    return result


def _preserved(connection, metadata):
    result = {}
    for name, table in sorted(metadata.tables.items()):
        if name in TABLES:
            continue
        columns = [c for c in table.c if not (name == "coupons" and c.name == "used_count")]
        digest = hashlib.sha256()
        for row in connection.execute(select(*columns).order_by(*table.primary_key.columns)):
            digest.update(json.dumps(list(row), default=str, ensure_ascii=False, sort_keys=True).encode())
            digest.update(b"\n")
        result[name] = digest.hexdigest()
    return result


def _triggers(connection):
    if connection.dialect.name == "sqlite":
        rows = connection.execute(text("SELECT name, sql FROM sqlite_master WHERE type = 'trigger'")).all()
    else:
        rows = connection.execute(text(
            "SELECT TRIGGER_NAME, ACTION_STATEMENT FROM information_schema.TRIGGERS "
            "WHERE TRIGGER_SCHEMA = DATABASE()"
        )).all()
    triggers = dict(rows)
    if set(triggers) != TRIGGERS or any("order_activity_immutable" not in sql for sql in triggers.values()):
        raise SanitationError("Missing or unexpected triggers; refuse sanitation")
    return triggers


@contextmanager
def _activity_deletion(connection, triggers):
    if connection.dialect.name == "mysql":
        if "@tara_sanitize_transactions" not in triggers["trg_order_activities_no_delete"]:
            raise SanitationError("Apply forward migration 0026 before MySQL sanitation")
        lock = connection.execute(text("SELECT GET_LOCK(CONCAT('tara-prelaunch:', DATABASE()), 0)")).scalar_one()
        if lock != 1:
            raise SanitationError("Another sanitation connection holds the maintenance lock")
        try:
            connection.execute(text("SET @tara_sanitize_transactions = 1"))
            yield
        finally:
            connection.execute(text("SET @tara_sanitize_transactions = NULL"))
            connection.execute(text("SELECT RELEASE_LOCK(CONCAT('tara-prelaunch:', DATABASE()))"))
    else:
        # SQLite supports transactional trigger DDL. BEGIN IMMEDIATE is issued
        # explicitly below, before this DDL (including with legacy sqlite3 mode).
        connection.exec_driver_sql("DROP TRIGGER trg_order_activities_no_delete")
        try:
            yield
        finally:
            connection.exec_driver_sql(triggers["trg_order_activities_no_delete"])


def sanitize(engine, *, execute=False, confirmed_test_data=False, writers_stopped=False):
    if execute and not (confirmed_test_data and writers_stopped):
        raise SanitationError("Execution requires test-data confirmation and stopped writers")
    with engine.connect() as connection:
        if connection.dialect.name == "mysql":
            connection = connection.execution_options(isolation_level="SERIALIZABLE")
        with connection.begin():
            if connection.dialect.name == "sqlite":
                connection.exec_driver_sql("BEGIN IMMEDIATE" if execute else "BEGIN")
            metadata = _schema(connection)
            triggers = _triggers(connection)
            before = _counts(connection, metadata)
            preserved = _preserved(connection, metadata)
            report = {"mode": "execute" if execute else "dry-run", "before": before,
                      "actions": {name: "delete all test rows" for name in TABLES},
                      "coupon_action": "reset used_count; preserve definitions",
                      "mysql_execution_requires": HEAD}
            if execute:
                revision = connection.execute(select(metadata.tables["alembic_version"].c.version_num)).scalar_one()
                if revision != HEAD:
                    raise SanitationError(f"Execution requires migration {HEAD}")
                with _activity_deletion(connection, triggers):
                    # Self-referencing replacement links must be removed before DELETE.
                    invoices = metadata.tables["invoices"]
                    connection.execute(update(invoices).values(replacement_invoice_id=None))
                    for name in TABLES:
                        connection.execute(delete(metadata.tables[name]))
                    coupons = metadata.tables["coupons"]
                    connection.execute(update(coupons).values(used_count=0))
                if _preserved(connection, metadata) != preserved:
                    raise SanitationError("Preserved data changed; rolling back all sanitation")
                report["after"] = _counts(connection, metadata)
                if any(report["after"][name] for name in TABLES) or report["after"]["coupon_used_count"]:
                    raise SanitationError("Nonzero transaction totals after sanitation; rolling back")
                _schema(connection)
            else:
                report["after"] = before.copy()
                report["projected_after"] = {**before, **dict.fromkeys(TABLES, 0), "coupon_used_count": 0}
            report["preserved_sha256"] = preserved
            report["r2_operations"] = 0
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Destructively remove ALL transaction data")
    parser.add_argument("--confirm-test-data", action="store_true", help="Confirm ALL orders, invoices and coupon usage are tests")
    parser.add_argument("--writers-stopped", action="store_true", help="Confirm all writers are offline")
    args = parser.parse_args(argv)
    engine = build_engine()
    try:
        print(json.dumps(sanitize(engine, execute=args.execute, confirmed_test_data=args.confirm_test_data,
                                  writers_stopped=args.writers_stopped), ensure_ascii=False, indent=2))
    except Exception as exc:
        # SQLAlchemy errors can include URLs/parameters. Do not print raw errors.
        print(str(exc) if isinstance(exc, SanitationError) else f"Sanitation failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
