from __future__ import annotations

import argparse

from app.db.session import SessionLocal
from app.services.analytics import prune_analytics, retention_counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune first-party analytics past retention")
    parser.add_argument("--confirm", action="store_true", help="delete rows instead of dry-run")
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_size > 10000:
        parser.error("--batch-size must be between 1 and 10000")

    with SessionLocal() as db:
        sessions, views, cutoff = retention_counts(db)
        if not args.confirm:
            print(f"Dry run: sessions={sessions} product_views={views} older_than={cutoff.isoformat()}")
            print("Re-run with --confirm to prune expired analytics rows.")
            return 0
        deleted_sessions, deleted_views = prune_analytics(db, batch_size=args.batch_size)
        print(f"Pruned: sessions={deleted_sessions} product_views={deleted_views}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
