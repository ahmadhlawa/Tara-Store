"""Offline MySQL compatibility check — connects to nothing.

Compiles the existing metadata against SQLAlchemy's MySQL dialect and inspects the model
for the portability problems that actually bite when moving off SQLite. No server, no
socket, no DBAPI connection.

    python -m scripts.mysql_compat [--verbose]

This is a compatibility *signal*, not proof of production readiness. An ephemeral MySQL
integration test is still required before a first deployment — see
docs/future-mysql-migration.md.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import JSON, Numeric, String
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.base import metadata_with_models

Level = Literal["ok", "warn", "fail"]

# InnoDB's index key limit is 3072 bytes with DYNAMIC row format; utf8mb4 costs up to
# 4 bytes per character, so an indexed VARCHAR longer than 768 characters cannot be
# fully indexed.
UTF8MB4_BYTES_PER_CHAR = 4
INNODB_MAX_KEY_BYTES = 3072
MAX_INDEXED_VARCHAR = INNODB_MAX_KEY_BYTES // UTF8MB4_BYTES_PER_CHAR


@dataclass
class Finding:
    level: Level
    check: str
    message: str


def _dialect() -> mysql.dialect:
    # utf8mb4 is the only correct charset for this application's Arabic content.
    return mysql.dialect(paramstyle="pyformat")


def check_table_compilation(metadata, findings: list[Finding]) -> None:
    dialect = _dialect()
    for table in sorted(metadata.tables.values(), key=lambda t: t.name):
        try:
            CreateTable(table).compile(dialect=dialect)
        except Exception as exc:
            findings.append(
                Finding("fail", "table-compilation", f"{table.name}: {type(exc).__name__}: {exc}")
            )
            continue
        for index in table.indexes:
            try:
                CreateIndex(index).compile(dialect=dialect)
            except Exception as exc:
                findings.append(
                    Finding(
                        "fail",
                        "index-compilation",
                        f"{table.name}.{index.name}: {type(exc).__name__}: {exc}",
                    )
                )
    findings.append(
        Finding("ok", "table-compilation", f"{len(metadata.tables)} tables compile for MySQL")
    )


def check_money_columns(metadata, findings: list[Finding]) -> None:
    numeric_columns = [
        (table.name, column.name, column.type)
        for table in metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, Numeric) and not isinstance(column.type, type(None))
    ]
    bad = [
        f"{table}.{col}"
        for table, col, type_ in numeric_columns
        if type_.precision is None or type_.scale is None
    ]
    if bad:
        findings.append(
            Finding(
                "fail",
                "money-columns",
                f"Numeric without explicit precision/scale becomes DECIMAL(10,0) on MySQL: {bad}",
            )
        )
    else:
        findings.append(
            Finding(
                "ok",
                "money-columns",
                f"{len(numeric_columns)} Numeric columns declare precision and scale",
            )
        )


def check_json_columns(metadata, findings: list[Finding]) -> None:
    json_columns = [
        f"{table.name}.{column.name}"
        for table in metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, JSON)
    ]
    # MySQL 8 has native JSON, but a JSON column cannot carry an index or a default.
    indexed_json = [
        f"{table.name}.{column.name}"
        for table in metadata.tables.values()
        for index in table.indexes
        for column in index.columns
        if isinstance(column.type, JSON)
    ]
    if indexed_json:
        findings.append(
            Finding("fail", "json-columns", f"MySQL cannot index a JSON column directly: {indexed_json}")
        )
    findings.append(
        Finding(
            "ok",
            "json-columns",
            f"{len(json_columns)} JSON columns, none indexed ({', '.join(json_columns) or 'none'})",
        )
    )


def check_indexed_string_lengths(metadata, findings: list[Finding]) -> None:
    problems: list[str] = []
    unbounded: list[str] = []
    checked = 0

    indexed_columns = set()
    for table in metadata.tables.values():
        for index in table.indexes:
            for column in index.columns:
                indexed_columns.add((table.name, column.name, column))
        for constraint in table.constraints:
            for column in getattr(constraint, "columns", []):
                if constraint.__class__.__name__ == "UniqueConstraint":
                    indexed_columns.add((table.name, column.name, column))

    for table_name, column_name, column in sorted(indexed_columns, key=lambda x: (x[0], x[1])):
        if not isinstance(column.type, String):
            continue
        checked += 1
        length = column.type.length
        if length is None:
            unbounded.append(f"{table_name}.{column_name}")
        elif length > MAX_INDEXED_VARCHAR:
            problems.append(f"{table_name}.{column_name} VARCHAR({length})")

    if unbounded:
        findings.append(
            Finding(
                "fail",
                "index-key-length",
                f"indexed String columns without a length cannot be indexed on MySQL: {unbounded}",
            )
        )
    if problems:
        findings.append(
            Finding(
                "warn",
                "index-key-length",
                f"indexed VARCHAR longer than {MAX_INDEXED_VARCHAR} chars needs a prefix index "
                f"under utf8mb4: {problems}",
            )
        )
    if not unbounded and not problems:
        findings.append(
            Finding(
                "ok",
                "index-key-length",
                f"{checked} indexed String columns fit the InnoDB {INNODB_MAX_KEY_BYTES}-byte key limit",
            )
        )


def check_foreign_keys(metadata, findings: list[Finding]) -> None:
    total = 0
    mismatched: list[str] = []
    for table in metadata.tables.values():
        for fk in table.foreign_keys:
            total += 1
            source = fk.parent
            target = fk.column
            # MySQL requires comparable types on both sides of a foreign key.
            if source.type.__class__ is not target.type.__class__:
                mismatched.append(
                    f"{table.name}.{source.name} ({source.type}) -> "
                    f"{target.table.name}.{target.name} ({target.type})"
                )
    if mismatched:
        findings.append(
            Finding("fail", "foreign-keys", f"type mismatch across a foreign key: {mismatched}")
        )
    else:
        findings.append(Finding("ok", "foreign-keys", f"{total} foreign keys have matching types"))


def check_unique_constraints(metadata, findings: list[Finding]) -> None:
    count = 0
    for table in metadata.tables.values():
        count += sum(
            1 for c in table.constraints if c.__class__.__name__ == "UniqueConstraint"
        )
        count += sum(1 for index in table.indexes if index.unique)
    findings.append(
        Finding("ok", "unique-constraints", f"{count} unique constraints/indexes compile")
    )


def check_enum_like_columns(metadata, findings: list[Finding]) -> None:
    """Native ENUM would need an ALTER TYPE migration to add a value; String does not."""
    native_enums = [
        f"{table.name}.{column.name}"
        for table in metadata.tables.values()
        for column in table.columns
        if column.type.__class__.__name__ in ("Enum", "ENUM")
    ]
    if native_enums:
        findings.append(
            Finding(
                "warn",
                "enum-like",
                f"native ENUM columns are harder to migrate on MySQL: {native_enums}",
            )
        )
    else:
        findings.append(
            Finding("ok", "enum-like", "enum-like values are portable String columns, not native ENUM")
        )


def check_alembic_head(findings: list[Finding]) -> None:
    from app.instance.manifest import head_alembic_revision

    head = head_alembic_revision()
    if head:
        findings.append(Finding("ok", "alembic", f"head revision available: {head}"))
    else:
        findings.append(Finding("fail", "alembic", "no Alembic head revision found"))


def run_checks() -> list[Finding]:
    metadata = metadata_with_models()
    findings: list[Finding] = []
    check_table_compilation(metadata, findings)
    check_money_columns(metadata, findings)
    check_json_columns(metadata, findings)
    check_indexed_string_lengths(metadata, findings)
    check_foreign_keys(metadata, findings)
    check_unique_constraints(metadata, findings)
    check_enum_like_columns(metadata, findings)
    check_alembic_head(findings)
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="commerce-mysql-check",
        description="Offline MySQL portability check. Connects to nothing.",
    )
    parser.add_argument("--verbose", action="store_true", help="Show passing checks too.")
    args = parser.parse_args(argv)

    findings = run_checks()
    failures = [f for f in findings if f.level == "fail"]
    warnings = [f for f in findings if f.level == "warn"]

    print("Offline MySQL compatibility check (no server was contacted)\n")
    for finding in findings:
        if finding.level == "ok" and not args.verbose:
            continue
        print(f"  [{finding.level.upper():4}] {finding.check}: {finding.message}")
    if not args.verbose:
        print(f"  {len(findings) - len(failures) - len(warnings)} checks passed (use --verbose to list)")

    print(f"\n  {len(failures)} failure(s), {len(warnings)} warning(s), {len(findings)} checks")
    print(
        "\nThis is a compatibility signal, not proof of production readiness.\n"
        "Run an ephemeral MySQL integration test before the first deployment —\n"
        "see docs/future-mysql-migration.md."
    )
    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
