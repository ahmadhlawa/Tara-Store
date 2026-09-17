"""Idempotent backfill/retry: python -m app.cli.translate_content."""
import argparse
import time
from sqlalchemy import select
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.translations import FIELDS, LibreTranslator, process_pending, stage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=20, choices=range(1, 101), metavar="1..100")
    parser.add_argument("--max-batches", type=int, default=1)
    parser.add_argument("--pause", type=float, default=1)
    parser.add_argument("--queue-only", action="store_true")
    parser.add_argument("--retry", action="store_true", help="Retry failed rows immediately on the first batch")
    args = parser.parse_args()
    if args.max_batches < 1 or args.pause < 0:
        parser.error("max-batches must be positive and pause nonnegative")
    if not args.queue_only and not settings.LIBRETRANSLATE_URL:
        parser.error("LIBRETRANSLATE_URL is required unless --queue-only")
    for model in FIELDS:
        last_id = 0
        while True:
            with SessionLocal() as db:
                rows = list(db.scalars(select(model).where(model.id > last_id).order_by(model.id).limit(100)))
                if not rows:
                    break
                for row in rows:
                    stage(db.connection(), row)
                last_id = rows[-1].id
                db.commit()
    print("Missing/changed fields queued; Arabic preserved.")
    if args.queue_only:
        return
    for index in range(args.max_batches):
        attempted, completed = process_pending(SessionLocal, LibreTranslator(settings),
            limit=args.batch_size, force_retry=args.retry and index == 0)
        print(f"Batch {index + 1}: {completed}/{attempted} completed")
        if not attempted:
            break
        if index + 1 < args.max_batches:
            time.sleep(args.pause)


if __name__ == "__main__":
    main()
