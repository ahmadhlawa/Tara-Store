from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import DiscountType
from app.db.base import Base, TimestampMixin


class HeroSlide(TimestampMixin, Base):
    __tablename__ = "hero_slides"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(250), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    button_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    button_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    target_slug: Mapped[str | None] = mapped_column(String(160), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Coupon(TimestampMixin, Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(250), nullable=True)
    discount_type: Mapped[str] = mapped_column(
        String(16), default=DiscountType.PERCENTAGE.value, nullable=False
    )
    discount_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    min_order_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    max_discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint("discount_value > 0", name="ck_coupon_value_positive"),
        CheckConstraint("min_order_amount >= 0", name="ck_coupon_min_order_non_negative"),
        CheckConstraint("used_count >= 0", name="ck_coupon_used_non_negative"),
    )


class DeliveryArea(TimestampMixin, Base):
    __tablename__ = "delivery_areas"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    min_order_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    free_delivery_threshold: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    estimated_days: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        CheckConstraint("delivery_fee >= 0", name="ck_delivery_fee_non_negative"),
    )
