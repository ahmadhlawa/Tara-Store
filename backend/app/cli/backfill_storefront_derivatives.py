"""Pre-generate persistent responsive storefront images for currently used media."""

from __future__ import annotations

import argparse
import sys

from app.core.enums import StorageProviderName
from app.services.storefront_derivatives import backfill_storefront_derivatives
from app.storage import get_storage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true", help="Generate and upload missing derivatives.")
    args = parser.parse_args(argv)
    storage = get_storage()
    if storage.name != StorageProviderName.R2.value:
        print("Refused: persistent storefront derivative backfill requires STORAGE_PROVIDER=r2.", file=sys.stderr)
        return 2

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        report = backfill_storefront_derivatives(db, storage, write=args.confirm)
    mode = "Backfilled" if args.confirm else "Dry run"
    print(f"{mode}: assets={report.assets} missing={report.generated} existing={report.skipped} failed={report.failed}")
    if not args.confirm:
        print("Re-run with --confirm to generate missing derivatives.")
    return 1 if report.failed else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
