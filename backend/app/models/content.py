from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import HomeSectionType
from app.db.base import Base, TimestampMixin


class HomeSection(TimestampMixin, Base):
    """An ordered, toggleable block on the storefront homepage."""

    __tablename__ = "home_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    section_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    section_type: Mapped[str] = mapped_column(
        String(32), default=HomeSectionType.FEATURED_PRODUCTS.value, nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Article(TimestampMixin, Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    slug: Mapped[str] = mapped_column(String(260), unique=True, index=True, nullable=False)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    featured_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    seo_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(Text, nullable=True)


class StaticPage(TimestampMixin, Base):
    """about / contact / privacy-policy / terms / return-policy / shipping-policy."""

    __tablename__ = "static_pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    lead: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    seo_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(Text, nullable=True)
