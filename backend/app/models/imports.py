"""Import-batch tracking.

One batch owns the rows a dataset created, so those rows — and only those rows — can be
removed again later. This is the mechanism that lets a demonstration catalog be dropped
into a client instance and taken back out without touching anything the owner wrote.

Deliberately two small tables rather than an `imported_by_batch_id` column on every
commerce model: ownership is an import concern, not a property of a product, and adding
a nullable FK to a dozen tables would put a migration and a foreign key in front of every
future schema change for the sake of a temporary dataset.

`content_fingerprint` is what makes a purge safe. It is a hash of exactly the fields the
importer wrote. If the owner edits an imported row through Admin, the fingerprint stops
matching and the purge skips that row instead of deleting the owner's work.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow


class ImportBatch(TimestampMixin, Base):
    """One named, re-runnable dataset import."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)

    batch_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    source_label: Mapped[str] = mapped_column(String(250), nullable=False, default="")
    dataset_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    media_prefix: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    seed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_seeded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    records: Mapped[list["ImportBatchRecord"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="ImportBatchRecord.id",
    )


class ImportBatchRecord(TimestampMixin, Base):
    """One row this batch owns, in one table."""

    __tablename__ = "import_batch_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # The model this row lives in, e.g. "product", "category", "media_asset".
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # The dataset-side key (slug, section key, coupon code...). Kept so a batch record is
    # still readable after the row it points at is gone.
    natural_key: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # For media rows: the storage key, so a purge can delete the object it uploaded.
    storage_key: Mapped[str | None] = mapped_column(String(300), nullable=True)

    batch: Mapped[ImportBatch] = relationship(back_populates="records")

    __table_args__ = (
        UniqueConstraint(
            "batch_id", "entity_type", "entity_id", name="uq_import_batch_record_entity"
        ),
    )
