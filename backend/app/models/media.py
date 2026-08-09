from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import StorageProviderName
from app.db.base import Base, utcnow


class MediaAsset(Base):
    """Metadata for an uploaded file. Bytes live in the storage provider, never here."""

    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Unique because the catalog importer resolves a product image by this name: two rows
    # sharing it would make that lookup ambiguous. The database is the authority — the
    # upload pre-check only turns the collision into a friendly answer.
    original_filename: Mapped[str] = mapped_column(
        String(300), unique=True, index=True, nullable=False
    )
    stored_key: Mapped[str] = mapped_column(String(300), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    url: Mapped[str] = mapped_column(String(600), nullable=False)
    storage_provider: Mapped[str] = mapped_column(
        String(16), default=StorageProviderName.LOCAL.value, nullable=False
    )
    uploaded_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
