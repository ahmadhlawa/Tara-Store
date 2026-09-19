from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class AnalyticsSession(Base):
    __tablename__ = "analytics_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    visitor_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    raw_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    raw_region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location_label: Mapped[str] = mapped_column(String(120), default="غير محدد", nullable=False)

    product_views: Mapped[list["AnalyticsProductView"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_analytics_sessions_started_at", "started_at"),
        Index("ix_analytics_sessions_visitor_last_activity", "visitor_hash", "last_activity_at"),
        Index("ix_analytics_sessions_location_started", "location_label", "started_at"),
    )


class AnalyticsProductView(Base):
    __tablename__ = "analytics_product_views"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("analytics_sessions.id", ondelete="CASCADE"), nullable=False
    )
    # Deliberately not an FK: historical analytics must retain product identity
    # after a catalog product is deleted.
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_slug_snapshot: Mapped[str] = mapped_column(String(260), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(250), nullable=False)
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    session: Mapped[AnalyticsSession] = relationship(back_populates="product_views")

    __table_args__ = (
        Index("ix_analytics_product_views_viewed_at", "viewed_at"),
        Index("ix_analytics_product_views_product_viewed", "product_id", "viewed_at"),
        Index(
            "ix_analytics_product_views_session_product_viewed",
            "session_id",
            "product_id",
            "viewed_at",
        ),
    )
