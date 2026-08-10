"""Client data cutover CLI — inspect, preserve, verify. Never purges, never imports.

Argparse, matching `scripts.preview_cli`. Run from `backend/`:

    python -m scripts.client_cutover_cli plan     --dataset path/to/preview.yaml
    python -m scripts.client_cutover_cli preserve --dataset ... --target hero_slide:"عنوان" --confirm
    python -m scripts.client_cutover_cli preserve --dataset ... --entity-type hero_slide --entity-id 12 --confirm
    python -m scripts.client_cutover_cli verify

`plan` and `verify` write nothing. `preserve` writes only with `--confirm`, and only to
the records it was explicitly told to promote.

The two destructive steps of a cutover stay where they already are, as separate operator
actions, so no single command can both wipe and reload a store:

    python -m scripts.preview_cli purge --dataset ...            # dry run
    python -m scripts.preview_cli purge --dataset ... --confirm  # the deletion
    python -m scripts.preview_cli seed  --dataset ...            # the new import

Installed as `tara-cutover`.
"""

from __future__ import annotations

import argparse
import json
import sys

from app.preview.cutover import (
    CutoverError,
    Selector,
    build_cutover_plan,
    preserve,
    verify_state,
)
from app.preview.dataset import DatasetError, load_dataset
from app.preview.importer import PreviewImporter

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_ATTENTION = 3

# Enough rows to act on without turning a summary into a database dump.
MAX_SHOWN = 25


def _session():
    """Imported lazily so `--help` never needs a configured database."""
    from app.db.session import SessionLocal

    return SessionLocal()


def _show(entries: list[dict], heading: str, *, reason: bool = False) -> None:
    if not entries:
        return
    print(f"\n{heading} ({len(entries)}):")
    for entry in entries[:MAX_SHOWN]:
        label = f" — {entry['label']}" if entry.get("label") else ""
        tail = f"\n        {entry['reason']}" if reason and entry.get("reason") else ""
        print(f"    {entry['target']}  #{entry['entity_id']}{label}{tail}")
    if len(entries) > MAX_SHOWN:
        print(f"    … and {len(entries) - MAX_SHOWN} more")


def cmd_plan(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    with _session() as db:
        report = build_cutover_plan(PreviewImporter(db, dataset), force=args.force)
        db.rollback()  # a plan must never write

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
        return EXIT_OK

    if not report["exists"]:
        print(f"Preview batch {report['batch_key']!r} is not present in this database.")
        print("There is nothing to purge, so the cutover starts at the import step.")
        return EXIT_OK

    print(f"Cutover plan for preview batch {report['batch_key']!r} — nothing was written.\n")
    print(f"  would delete       {report['would_delete_total']} record(s)")
    for name, count in sorted(report["would_delete"].items()):
        print(f"      {name:<16} {count}")
    print(f"  protected (edited) {len(report['protected_owner_edited'])}")
    print(f"  refused (blocked)  {len(report['blocked'])}")
    print(f"  already gone       {len(report['already_gone'])}")
    print(f"  media removed      {len(report['media_to_delete'])}")
    print(f"  media kept at risk {len(report['media_at_risk'])}")

    print("\n  surviving owner/system content:")
    for name, count in sorted(report["surviving"].items()):
        print(f"      {name:<16} {count}")
    print("  bootstrap:")
    for name, count in sorted(report["bootstrap"].items()):
        print(f"      {name:<18} {count}")
    print("  commercial (never touched by a purge):")
    for name, count in sorted(report["commercial"].items()):
        print(f"      {name:<18} {count}")

    _show(report["protected_owner_edited"], "Owner-edited — the purge keeps these", reason=True)
    _show(report["blocked"], "Refused — --force does not override these", reason=True)
    _show(report["media_at_risk"], "Media still displayed by surviving content", reason=True)
    _show(report["media_to_delete"], "Media the purge would delete")

    print(
        "\nReview the delete list. Anything on it that is genuinely the client's must be "
        "promoted first:\n"
        "  python -m scripts.client_cutover_cli preserve --target <entity_type:natural_key> "
        "--confirm\n"
        "If the owner has renamed a record, use the id printed after it instead:\n"
        "  python -m scripts.client_cutover_cli preserve --entity-type <entity_type> "
        "--entity-id <id> --confirm"
    )
    return EXIT_ATTENTION if report["media_at_risk"] or report["blocked"] else EXIT_OK


def _preserve_selectors(args: argparse.Namespace) -> list:
    """The records this invocation names, from exactly one selector style.

    `--target` carries the natural key and stays the readable default. `--entity-type`
    with `--entity-id` is the fallback for a record the owner has since renamed, where
    the row id printed by `plan` is the only stable handle left. Mixing the two in one
    command is refused rather than guessed at.
    """
    by_id = args.entity_type is not None or args.entity_id is not None
    if args.target and by_id:
        raise CutoverError(
            "Use --target, or --entity-type with --entity-id, but not both in one command."
        )
    if by_id and (args.entity_type is None or args.entity_id is None):
        raise CutoverError("--entity-type and --entity-id must be given together.")
    if not args.target and not by_id:
        raise CutoverError(
            "Nothing to preserve. Name a record with --target ENTITY_TYPE:NATURAL_KEY, "
            "or with --entity-type ENTITY_TYPE --entity-id N, as `plan` prints them."
        )
    if by_id:
        return [Selector(args.entity_type, entity_id=args.entity_id)]
    return list(args.target)


def cmd_preserve(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    selectors = _preserve_selectors(args)
    with _session() as db:
        results = preserve(
            db,
            dataset.batch_key,
            selectors,
            apply=args.confirm,
            include_media=not args.without_media,
        )
        if not args.confirm:
            db.rollback()

    heading = "Preserved" if args.confirm else "Dry run — nothing was changed"
    print(f"{heading} in preview batch {dataset.batch_key!r}:")
    for result in results:
        print("  " + result.render())

    unresolved = [r for r in results if r.outcome == "unknown"]
    if not args.confirm:
        print("\nRe-run with --confirm to apply.")
    else:
        print(
            "\nThe rows themselves were not modified — only the batch's claim on them was "
            "dropped, so a later purge will leave them alone."
        )
    if unresolved:
        print("\nNo record matched these targets; check the spelling against `plan`:")
        for result in unresolved:
            print(f"  {result.target}")
        return EXIT_ATTENTION
    return EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    with _session() as db:
        checks = verify_state(db)
        db.rollback()

    print("Structural check of the current database — nothing was written.\n")
    for check in checks:
        print("  " + check.render())
    failures = [check for check in checks if not check.ok]
    print(f"\n  -- {len(checks) - len(failures)} passed, {len(failures)} failed")
    return EXIT_ATTENTION if failures else EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tara-cutover",
        description=(
            "Prepare a preview instance for real client data: inspect what a purge would "
            "remove, promote the records that turned out to be real, and check the result. "
            "This tool never deletes demo content and never imports a catalog."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def with_dataset(name: str, help_text: str):
        sub_parser = sub.add_parser(name, help=help_text, description=help_text)
        sub_parser.add_argument(
            "--dataset",
            required=True,
            metavar="PATH",
            help="Preview dataset YAML path (required; Tara ships no default dataset).",
        )
        return sub_parser

    plan_parser = with_dataset("plan", "Report what a purge would do. Writes nothing.")
    plan_parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    plan_parser.add_argument(
        "--force",
        action="store_true",
        help="Report the plan a purge --force would follow (owner-edited rows deleted too).",
    )
    plan_parser.set_defaults(func=cmd_plan)

    preserve_parser = with_dataset(
        "preserve",
        "Promote named records out of the batch so no purge deletes them. "
        "Dry run unless --confirm.",
    )
    preserve_parser.add_argument(
        "--target",
        action="append",
        default=[],
        metavar="ENTITY_TYPE:NATURAL_KEY",
        help="A record to preserve, exactly as `plan` prints it. Repeatable.",
    )
    preserve_parser.add_argument(
        "--entity-type",
        metavar="ENTITY_TYPE",
        help=(
            "Select one record by row id instead of by natural key — use this when the "
            "owner has renamed it. Requires --entity-id, and cannot be combined with "
            "--target."
        ),
    )
    preserve_parser.add_argument(
        "--entity-id",
        type=int,
        metavar="N",
        help="The row id `plan` prints beside the record. Requires --entity-type.",
    )
    preserve_parser.add_argument(
        "--confirm", action="store_true", help="Actually apply. Without this it is a dry run."
    )
    preserve_parser.add_argument(
        "--without-media",
        action="store_true",
        help="Do not promote the media the record displays. The purge may then delete it.",
    )
    preserve_parser.set_defaults(func=cmd_preserve)

    verify_parser = sub.add_parser(
        "verify",
        help="Check that the database is structurally coherent. Writes nothing.",
        description="Check that the database is structurally coherent. Writes nothing.",
    )
    verify_parser.set_defaults(func=cmd_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except DatasetError as exc:
        print(f"Invalid preview dataset:\n{exc}", file=sys.stderr)
        return EXIT_INVALID
    except CutoverError as exc:
        print(f"Cannot run this cutover step:\n{exc}", file=sys.stderr)
        return EXIT_INVALID


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
