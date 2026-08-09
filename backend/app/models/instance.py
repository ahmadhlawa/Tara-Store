"""Instance provenance.

One row, describing this instance and the template release it came from. This is not a
tenancy mechanism: there is no `tenant_id` and nothing else in the schema references it.
One running application is still exactly one store.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, utcnow


class InstanceMetadata(TimestampMixin, Base):
    __tablename__ = "instance_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)

    instance_slug: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    template_version: Mapped[str] = mapped_column(String(32), nullable=False)
    profile_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled_features: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)

    initialized_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    last_bootstrap_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
