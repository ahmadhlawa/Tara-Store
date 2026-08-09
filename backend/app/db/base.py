"""Declarative base plus the model imports Alembic autogenerate relies on."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Naive UTC. One timezone everywhere; MySQL DATETIME compatible."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


def metadata_with_models():
    """Import every model so Base.metadata is complete, then return it.

    Alembic and the test bootstrap call this; importing models here rather than at
    module import time keeps `app.models` -> `app.db.base` a one-way dependency.
    """
    import app.models  # noqa: F401  (registers all tables on Base.metadata)

    return Base.metadata
