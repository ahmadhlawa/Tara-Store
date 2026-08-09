"""The preview batch, exercised against a real MySQL 8 server.

Everything here passes on SQLite already. It is repeated on MySQL because the parts
that could diverge are exactly the parts the preview batch depends on: Decimal money
survives a round trip with its scale intact, Arabic text survives utf8mb4, the
fingerprint computed from a row read back from MySQL still matches the one computed
when it was written, and the unique constraint on batch ownership is real.

A fingerprint that changed on a round trip would make every re-seed think the owner had
edited everything, and would make purge refuse to remove its own rows. That is the whole
reason this file exists.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Category, DeliveryArea, ImportBatch, ImportBatchRecord, Product
from app.preview.dataset import load_dataset, parse_dataset
from app.preview.importer import (
    MODEL_FOR_TYPE,
    PreviewImporter,
    find_batch,
    row_fingerprint,
)
from app.storage.local import LocalStorageProvider

VISTA_DATASET = (
    Path(__file__).resolve().parents[2] / "instance" / "preview" / "vista-social-preview.yaml"
)


def document(batch_key: str) -> dict:
    """A small dataset, keyed uniquely so parallel runs cannot collide."""
    suffix = uuid.uuid4().hex[:8]
    return {
        "preview_schema_version": 1,
        "batch_key": batch_key,
        "source_label": "MySQL preview test",
        "media_prefix": f"mysql-test/{suffix}/",
        "media": [
            {"key": "tile", "alt_text": "tile", "start_color": "#112233", "end_color": "#445566"}
        ],
        "categories": [
            {
                "slug": f"cat-{suffix}",
                "name": "قسم المعاينة العربي",
                "image": "tile",
                "origin": "inferred",
            }
        ],
        "products": [
            {
                "slug": f"prod-{suffix}",
                "name": "منتج تجريبي بالعربية — ٢٠٢٦",
                "category": f"cat-{suffix}",
                "price": "1234.56",
                "compare_at_price": "1500.00",
                "stock_quantity": 9,
                "short_description": "وصف عربي بحروف مركّبة: لآلئ، إنشاء، ﷺ",
                "image": "tile",
                "origin": "inferred",
            }
        ],
        "delivery_areas": [
            {
                "key": "preview-area",
                "name": f"منطقة تجريبية للمعاينة {suffix}",
                "delivery_fee": "0.00",
                "origin": "placeholder",
            }
        ],
    }


def owned(db: Session, importer: PreviewImporter, entity_type: str) -> list:
    """The rows this batch owns, resolved through its own ownership records.

    A developer's MySQL database is not the empty CI service container: it also holds the
    seeded Vista preview batch and the client bootstrap. Picking "the first row of this
    table" would silently assert against someone else's data, so every lookup here goes
    through the batch that created the row.
    """
    batch = find_batch(db, importer.dataset.batch_key)
    assert batch is not None
    ids = db.execute(
        select(ImportBatchRecord.entity_id).where(
            ImportBatchRecord.batch_id == batch.id,
            ImportBatchRecord.entity_type == entity_type,
        )
    ).scalars().all()
    return [db.get(MODEL_FOR_TYPE[entity_type], entity_id) for entity_id in ids]


@pytest.fixture()
def importer(db: Session, tmp_path: Path) -> Iterator[PreviewImporter]:
    key = f"mysql-preview-{uuid.uuid4().hex[:8]}"
    storage = LocalStorageProvider(tmp_path / "media", "/media")
    made = PreviewImporter(db, parse_dataset(document(key)), storage=storage)
    yield made
    made.purge(apply=True, force=True)


def test_the_shipped_vista_dataset_seeds_and_purges_on_mysql(db: Session, tmp_path: Path) -> None:
    dataset = load_dataset(VISTA_DATASET)
    storage = LocalStorageProvider(tmp_path / "media", "/media")
    made = PreviewImporter(db, dataset, storage=storage)
    try:
        made.seed()
        status = made.status()
        assert status["records"]["product"] == len(dataset.products)
        assert status["owner_edited"] == []

        # Idempotent on MySQL too: a second run must change no content row.
        second = made.seed()
        assert second.counts().get("create") is None
    finally:
        made.purge(apply=True, force=True)
    assert made.status()["exists"] is False


def test_decimal_money_keeps_its_scale(importer: PreviewImporter, db: Session) -> None:
    importer.seed()
    product = owned(db, importer, "product")[0]

    assert product.price == Decimal("1234.56")
    assert product.price.as_tuple().exponent == -2
    assert product.compare_at_price == Decimal("1500.00")


def test_arabic_content_survives_utf8mb4(importer: PreviewImporter, db: Session) -> None:
    importer.seed()
    product = owned(db, importer, "product")[0]
    category = owned(db, importer, "category")[0]
    area = owned(db, importer, "delivery_area")[0]

    assert product.name == "منتج تجريبي بالعربية — ٢٠٢٦"
    assert "لآلئ" in product.short_description
    assert "ﷺ" in product.short_description
    assert category.name == "قسم المعاينة العربي"
    assert area.name.startswith("منطقة تجريبية للمعاينة")


def test_fingerprints_survive_the_round_trip_through_mysql(
    importer: PreviewImporter, db: Session
) -> None:
    """The check that makes idempotency and safe purge possible at all."""
    importer.seed()
    db.expire_all()  # force every value to be re-read from the server

    checked = 0
    for record in db.execute(select(ImportBatchRecord)).scalars():
        model = MODEL_FOR_TYPE[record.entity_type]
        row = db.get(model, record.entity_id)
        assert row is not None
        assert row_fingerprint(record.entity_type, row) == record.content_fingerprint
        checked += 1
    assert checked > 0


def test_batch_ownership_is_enforced_by_a_unique_constraint(
    importer: PreviewImporter, db: Session
) -> None:
    importer.seed()
    batch = find_batch(db, importer.dataset.batch_key)
    record = db.execute(
        select(ImportBatchRecord).where(ImportBatchRecord.batch_id == batch.id)
    ).scalars().first()

    db.add(
        ImportBatchRecord(
            batch_id=record.batch_id,
            entity_type=record.entity_type,
            entity_id=record.entity_id,
            natural_key="duplicate",
            content_fingerprint="x",
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_batch_key_is_unique(importer: PreviewImporter, db: Session) -> None:
    importer.seed()
    existing = find_batch(db, importer.dataset.batch_key)

    db.add(ImportBatch(batch_key=existing.batch_key, source_label="clash"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_purging_the_batch_cascades_to_its_records(importer: PreviewImporter, db: Session) -> None:
    importer.seed()
    batch_id = find_batch(db, importer.dataset.batch_key).id

    importer.purge(apply=True)

    remaining = db.execute(
        select(ImportBatchRecord).where(ImportBatchRecord.batch_id == batch_id)
    ).scalars().all()
    assert remaining == []
