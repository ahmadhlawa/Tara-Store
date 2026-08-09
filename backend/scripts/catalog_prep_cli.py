"""Catalog preparation CLI — turn a client workbook into a canonical dataset.

Argparse, matching `scripts.preview_cli`. Run from `backend/`:

    python -m scripts.catalog_prep_cli prepare --input client-products.xlsx --dry-run
    python -m scripts.catalog_prep_cli prepare --input client-products.xlsx \
        --output ../instance/generated/client-catalog.yaml

`--dry-run` parses, validates and resolves every image filename against the Media
Library, then reports counts and writes nothing at all. Without it the command writes one
YAML file — and still touches no database row.

Importing is a separate command, deliberately:

    python -m scripts.preview_cli plan --dataset ../instance/generated/client-catalog.yaml
    python -m scripts.preview_cli seed --dataset ../instance/generated/client-catalog.yaml

Installed as `vista-catalog-prep`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.catalog_prep import (
    PreparationError,
    WorkbookError,
    prepare_catalog,
    read_sheets,
    render_yaml,
)

EXIT_OK = 0
EXIT_INVALID = 2

# Enough to see the shape of the problem without burying the summary line.
MAX_SHOWN_ISSUES = 20


def _session(database_url: str | None):
    """Imported lazily, so `--help` never needs a configured database."""
    if database_url:
        from sqlalchemy.orm import sessionmaker

        from app.db.session import build_engine

        return sessionmaker(bind=build_engine(database_url), future=True)()
    from app.db.session import SessionLocal

    return SessionLocal()


def cmd_prepare(args: argparse.Namespace) -> int:
    if not args.dry_run and not args.output:
        print("prepare needs --output, or --dry-run to validate without writing.", file=sys.stderr)
        return EXIT_INVALID

    sheets = read_sheets(args.input)
    with _session(args.database_url) as db:
        try:
            prepared = prepare_catalog(
                db,
                sheets,
                batch_key=args.batch_key,
                source_label=args.source_label,
                media_prefix=args.media_prefix,
                origin=args.origin,
            )
        finally:
            # Preparation only reads, but a rollback makes that impossible to get wrong.
            db.rollback()

    print(f"Workbook OK: {args.input}")
    for name, count in prepared.counts.items():
        print(f"  {name.replace('_', ' '):<20} {count}")
    for warning in prepared.warnings:
        print(f"  warning: {warning}")
    print(f"  {'dataset hash':<20} {prepared.dataset.dataset_hash()}")

    if args.dry_run:
        print("\nDry run: nothing was written, and no database row was created or changed.")
        return EXIT_OK

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_yaml(prepared.document), encoding="utf-8")
    print(f"\nWrote {output}")
    print("Nothing was imported. To import it:")
    print(f"  python -m scripts.preview_cli plan --dataset {output}")
    print(f"  python -m scripts.preview_cli seed --dataset {output}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vista-catalog-prep",
        description=(
            "Validate a client catalog workbook and generate the canonical dataset the "
            "existing importer consumes. Never writes to the database."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser(
        "prepare",
        help="Validate a workbook and generate a dataset YAML.",
        description="Validate a workbook and generate a dataset YAML.",
    )
    prepare.add_argument(
        "--input",
        required=True,
        help="An .xlsx workbook, or a directory holding products.csv and categories.csv.",
    )
    prepare.add_argument("--output", help="Where to write the generated dataset YAML.")
    prepare.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and resolve media only. Writes no file and no database row.",
    )
    prepare.add_argument(
        "--batch-key",
        default="client-catalog",
        help="Import batch that will own the imported rows (default: client-catalog).",
    )
    prepare.add_argument(
        "--source-label",
        default="Client catalog workbook",
        help="Human-readable description of where this data came from.",
    )
    prepare.add_argument(
        "--media-prefix",
        default="vista-store/client/",
        help=(
            "Storage prefix recorded on the batch. A prepared catalog uploads nothing, so "
            "this only bounds what a later purge is ever allowed to delete."
        ),
    )
    prepare.add_argument(
        "--origin",
        default="confirmed",
        choices=["confirmed", "inferred", "placeholder"],
        help="Provenance recorded on every generated row (default: confirmed).",
    )
    prepare.add_argument(
        "--database-url",
        help="Read the Media Library from this database instead of the configured one.",
    )
    prepare.set_defaults(func=cmd_prepare)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except WorkbookError as exc:
        print(f"Cannot read the workbook: {exc}", file=sys.stderr)
        return EXIT_INVALID
    except PreparationError as exc:
        print(f"{len(exc.issues)} problem(s) found. Nothing was generated.\n", file=sys.stderr)
        for issue in exc.issues[:MAX_SHOWN_ISSUES]:
            print(f"  {issue.render()}", file=sys.stderr)
        if len(exc.issues) > MAX_SHOWN_ISSUES:
            print(
                f"  … and {len(exc.issues) - MAX_SHOWN_ISSUES} more.",
                file=sys.stderr,
            )
        return EXIT_INVALID


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
