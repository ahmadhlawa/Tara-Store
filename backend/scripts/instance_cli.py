"""Instance CLI — validate, plan, apply, manifest.

Argparse, matching the existing `app.initial_data` / `scripts.seed` convention. Four
commands do not justify a CLI framework.

    python -m scripts.instance_cli validate --profile ../instance/client-profile.example.yaml
    python -m scripts.instance_cli plan     --profile ../instance/demo-profile.yaml
    python -m scripts.instance_cli apply    --profile ../instance/demo-profile.yaml
    python -m scripts.instance_cli manifest [--output manifest.json]

`apply` performs application-level initialization only. It never creates database servers
or database users, never writes demo data, and never creates an admin account — use
`python -m app.initial_data` for that.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.template_version import template_version
from app.instance.bootstrap import InstanceConflictError, apply_profile, build_plan
from app.instance.manifest import build_manifest
from app.instance.profile import ProfileError, load_profile

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_CONFLICT = 3


def _session():
    """Imported lazily so `validate` never needs a configured database."""
    from app.db.session import SessionLocal

    return SessionLocal()


def cmd_validate(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    print(f"Profile OK: {args.profile}")
    print(f"  client slug            {profile.client_slug}")
    print(f"  store name             {profile.store.name}")
    print(f"  profile schema version {profile.profile_schema_version}")
    print(f"  intended template      {profile.template_version}")
    print(f"  running template       {template_version()}")
    print(f"  enabled features       {', '.join(profile.enabled_features()) or '(none)'}")
    print(f"  profile hash           {profile.profile_hash()}")
    if profile.template_version != template_version():
        print(
            f"  note: profile targets {profile.template_version}, this checkout is "
            f"{template_version()}."
        )
    return EXIT_OK


def cmd_plan(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    with _session() as db:
        plan = build_plan(db, profile)
        db.rollback()  # a plan must never write

    print(f"Plan for {profile.client_slug} (template {template_version()}):")
    for action in plan.actions:
        print("  " + action.render())
    counts = ", ".join(f"{name}={count}" for name, count in sorted(plan.counts().items()))
    print(f"  ── {counts or 'no actions'}")

    if plan.has_conflict:
        print("\nRefusing to apply: this database belongs to a different instance.")
        return EXIT_CONFLICT
    return EXIT_OK


def cmd_apply(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    with _session() as db:
        try:
            plan = apply_profile(db, profile)
        except InstanceConflictError as exc:
            print(f"Conflict: {exc}", file=sys.stderr)
            print("Nothing was written.", file=sys.stderr)
            return EXIT_CONFLICT

    print(f"Applied profile for {profile.client_slug} (template {template_version()}):")
    for action in plan.actions:
        print("  " + action.render())
    print("\nNo products, orders, coupons or admin accounts were created.")
    print("Create the first administrator with: python -m app.initial_data --email ... --password ...")
    return EXIT_OK


def cmd_manifest(args: argparse.Namespace) -> int:
    with _session() as db:
        manifest = build_manifest(db)
        db.rollback()

    document = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(document + "\n", encoding="utf-8")
        print(f"Manifest written to {args.output}")
    else:
        print(document)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="commerce-instance",
        description="Validate, plan and apply a non-secret instance profile.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def with_profile(name: str, help_text: str):
        sub_parser = sub.add_parser(name, help=help_text, description=help_text)
        sub_parser.add_argument("--profile", required=True, help="Path to the profile YAML file.")
        return sub_parser

    with_profile("validate", "Validate a profile. Touches no database.").set_defaults(
        func=cmd_validate
    )
    with_profile("plan", "Show the intended actions. Writes nothing.").set_defaults(func=cmd_plan)
    with_profile("apply", "Initialize this instance from the profile. Idempotent.").set_defaults(
        func=cmd_apply
    )

    manifest_parser = sub.add_parser(
        "manifest", help="Print a non-secret instance manifest as JSON."
    )
    manifest_parser.add_argument("--output", help="Write to this file instead of stdout.")
    manifest_parser.set_defaults(func=cmd_manifest)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ProfileError as exc:
        print(f"Invalid profile:\n{exc}", file=sys.stderr)
        return EXIT_INVALID


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
