"""Preview dataset CLI — validate, plan, seed, status, purge.

Argparse, matching `scripts.instance_cli`. Run from `backend/`:

    python -m scripts.preview_cli validate --dataset ../instance/preview/vista-social-preview.yaml
    python -m scripts.preview_cli plan     --dataset ../instance/preview/vista-social-preview.yaml
    python -m scripts.preview_cli seed     --dataset ../instance/preview/vista-social-preview.yaml
    python -m scripts.preview_cli status   --dataset ../instance/preview/vista-social-preview.yaml
    python -m scripts.preview_cli purge    --dataset ../instance/preview/vista-social-preview.yaml
    python -m scripts.preview_cli purge    --dataset ... --confirm

`validate` and `plan` write nothing. `purge` is a dry run unless `--confirm` is given.

Installed as `vista-preview`, so the documented commands are `vista-preview validate`,
`vista-preview plan`, `vista-preview seed`, `vista-preview status`, `vista-preview purge`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.preview.dataset import DatasetError, PreviewDataset, load_dataset
from app.preview.importer import PreviewImporter, PreviewPlan

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_BLOCKED = 3

DEFAULT_DATASET = Path(__file__).resolve().parents[2] / "instance" / "preview" / (
    "vista-social-preview.yaml"
)


def _session():
    """Imported lazily so `validate` never needs a configured database."""
    from app.db.session import SessionLocal

    return SessionLocal()


def _render(plan: PreviewPlan) -> None:
    for action in plan.actions:
        print("  " + action.render())
    counts = ", ".join(f"{name}={count}" for name, count in sorted(plan.counts().items()))
    print(f"  ── {counts or 'no actions'}")


def cmd_validate(args: argparse.Namespace) -> int:
    dataset: PreviewDataset = load_dataset(args.dataset)
    print(f"Preview dataset OK: {args.dataset}")
    print(f"  batch key      {dataset.batch_key}")
    print(f"  source         {dataset.source_label}")
    print(f"  media prefix   {dataset.media_prefix}")
    print(f"  dataset hash   {dataset.dataset_hash()}")
    print("  content        " + ", ".join(f"{k}={v}" for k, v in dataset.counts().items()))
    print("  provenance     " + ", ".join(f"{k}={v}" for k, v in dataset.origin_counts().items()))
    print("\nNothing was written. This command does not open a database.")
    return EXIT_OK


def cmd_plan(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    with _session() as db:
        plan = PreviewImporter(db, dataset).plan()
        db.rollback()  # a plan must never write
    print(f"Plan for preview batch {dataset.batch_key!r}:")
    _render(plan)
    return EXIT_OK


def cmd_seed(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    with _session() as db:
        plan = PreviewImporter(db, dataset).seed(force=args.force)
    print(f"Seeded preview batch {dataset.batch_key!r}:")
    _render(plan)
    print("\nOnly rows owned by this batch were touched. No order or invoice was created.")
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    with _session() as db:
        report = PreviewImporter(db, dataset).status()
        db.rollback()

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
        return EXIT_OK

    if not report["exists"]:
        print(f"Preview batch {report['batch_key']!r} has never been seeded into this database.")
        return EXIT_OK

    print(f"Preview batch {report['batch_key']!r} (id {report['batch_id']}):")
    print(f"  source           {report['source_label']}")
    print(f"  media prefix     {report['media_prefix']}")
    print(f"  seeded           {report['seed_count']} time(s), last at {report['last_seeded_at']}")
    print(f"  dataset hash     {report['dataset_hash']}")
    print(
        "  matches file     "
        + ("yes" if report["dataset_hash_matches_file"] else "NO — the YAML has changed since")
    )
    print(f"  owned records    {report['record_total']}")
    for name, count in sorted(report["records"].items()):
        print(f"      {name:<16} {count}")
    if report["storage_providers"]:
        print(f"  media stored in  {', '.join(report['storage_providers'])}")
    if report["missing_rows"]:
        print(f"  missing rows     {report['missing_rows']} (deleted outside this tool)")
    if report["owner_edited"]:
        print(f"  owner-edited     {len(report['owner_edited'])} — purge will skip these:")
        for target in report["owner_edited"]:
            print(f"      {target}")
    return EXIT_OK


def cmd_purge(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    with _session() as db:
        importer = PreviewImporter(db, dataset)
        plan = importer.purge(apply=args.confirm, force=args.force)
        if not args.confirm:
            db.rollback()

    heading = "Purged" if args.confirm else "Dry run — nothing was deleted"
    print(f"{heading} for preview batch {dataset.batch_key!r}:")
    _render(plan)

    if plan.blocked:
        print("\nRefused to delete the following, and --force does not override them:")
        for action in plan.blocked:
            print(f"  {action.target} — {action.detail}")
    if not args.confirm:
        print("\nRe-run with --confirm to apply.")
        return EXIT_BLOCKED if plan.blocked else EXIT_OK
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vista-preview",
        description="Validate, plan, seed, inspect and remove a preview content batch.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def with_dataset(name: str, help_text: str):
        sub_parser = sub.add_parser(name, help=help_text, description=help_text)
        sub_parser.add_argument(
            "--dataset",
            default=str(DEFAULT_DATASET),
            help="Path to the preview dataset YAML file.",
        )
        return sub_parser

    with_dataset("validate", "Validate the dataset. Touches no database.").set_defaults(
        func=cmd_validate
    )
    with_dataset("plan", "Show what a seed would do. Writes nothing.").set_defaults(func=cmd_plan)

    seed_parser = with_dataset("seed", "Create or update this batch. Idempotent.")
    seed_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite rows the owner has edited since the last seed.",
    )
    seed_parser.set_defaults(func=cmd_seed)

    status_parser = with_dataset("status", "Report what this batch currently owns.")
    status_parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    status_parser.set_defaults(func=cmd_status)

    purge_parser = with_dataset("purge", "Remove this batch. Dry run unless --confirm.")
    purge_parser.add_argument(
        "--confirm", action="store_true", help="Actually delete. Without this it is a dry run."
    )
    purge_parser.add_argument(
        "--force",
        action="store_true",
        help="Also delete rows the owner has edited since the import.",
    )
    purge_parser.set_defaults(func=cmd_purge)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except DatasetError as exc:
        print(f"Invalid preview dataset:\n{exc}", file=sys.stderr)
        return EXIT_INVALID


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
