from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import OrderSource, OrderStatus, PaymentMethod
from app.db.base import Base, TimestampMixin, utcnow
from app.services.errors import ImmutableActivityError


class Order(TimestampMixin, Base):
    """Guest order. Delivery/coupon values are snapshots taken at creation time."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    public_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=OrderStatus.NEW.value,
        server_default=OrderStatus.NEW.value,
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(24),
        default=OrderSource.WEBSITE.value,
        server_default=OrderSource.WEBSITE.value,
        nullable=False,
        index=True,
    )
    source_note: Mapped[str | None] = mapped_column(String(250), nullable=True)
    client_reference: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    is_locked: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )

    customer_name: Mapped[str] = mapped_column(String(150), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)

    delivery_area_id: Mapped[int | None] = mapped_column(
        ForeignKey("delivery_areas.id", ondelete="SET NULL"), nullable=True
    )
    delivery_area_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    delivery_fee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    coupon_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    payment_method: Mapped[str] = mapped_column(
        String(32), default=PaymentMethod.CASH_ON_DELIVERY.value, nullable=False
    )
    customer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id"
    )
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusHistory.id",
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="order", order_by="Invoice.id"
    )
    # Compatibility accessor for the pre-replacement admin response. New workflow code
    # uses ``invoices`` and selects the active row explicitly.
    invoice = relationship(
        "Invoice",
        primaryjoin="and_(Order.id == Invoice.order_id, Invoice.status == 'active')",
        order_by="Invoice.id.desc()",
        uselist=False,
        viewonly=True,
        overlaps="invoices,order",
    )
    activities: Mapped[list["OrderActivity"]] = relationship(
        back_populates="order", order_by="OrderActivity.id", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="ck_orders_subtotal_non_negative"),
        CheckConstraint("total >= 0", name="ck_orders_total_non_negative"),
    )


class OrderItem(Base):
    """Immutable snapshot of a purchased line."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True
    )

    item_kind: Mapped[str] = mapped_column(
        String(16), default="catalog", server_default="catalog", nullable=False
    )
    product_name: Mapped[str] = mapped_column(String(250), nullable=False)
    original_product_name: Mapped[str] = mapped_column(
        String(250), default="", server_default="", nullable=False
    )
    sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    original_sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    variant_description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    selected_option_value_ids: Mapped[list[int]] = mapped_column(
        JSON, default=list, server_default="[]", nullable=False
    )
    original_variant_description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    manual_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), server_default="0.00", nullable=False
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    package_components: Mapped[list["OrderItemPackageComponent"]] = relationship(
        back_populates="order_item", cascade="all, delete-orphan", order_by="OrderItemPackageComponent.id"
    )

    __table_args__ = (CheckConstraint("quantity > 0", name="ck_order_item_quantity_positive"),)


class OrderItemPackageComponent(Base):
    """Immutable fulfillment snapshot for one component of a purchased package."""

    __tablename__ = "order_item_package_components"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False, index=True)
    source_product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    source_variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True)
    product_name: Mapped[str] = mapped_column(String(250), nullable=False)
    variant_description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quantity_per_package: Mapped[int] = mapped_column(Integer, nullable=False)
    package_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    tracks_inventory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    order_item: Mapped[OrderItem] = relationship(back_populates="package_components")

    __table_args__ = (
        CheckConstraint("quantity_per_package > 0", name="ck_package_component_quantity_positive"),
        CheckConstraint("package_quantity > 0", name="ck_package_component_package_quantity_positive"),
        CheckConstraint("total_quantity > 0", name="ck_package_component_total_quantity_positive"),
    )


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    old_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    admin_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    order: Mapped[Order] = relationship(back_populates="status_history")


class OrderActivity(Base):
    """Append-only operational history for order and invoice changes."""

    __tablename__ = "order_activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    before_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    order: Mapped[Order] = relationship(back_populates="activities")
    invoice: Mapped["Invoice | None"] = relationship(back_populates="activities")


@event.listens_for(OrderActivity, "before_update")
def _reject_order_activity_update(*_args) -> None:
    raise ImmutableActivityError()


@event.listens_for(OrderActivity, "before_delete")
def _reject_order_activity_delete(*_args) -> None:
    raise ImmutableActivityError()
