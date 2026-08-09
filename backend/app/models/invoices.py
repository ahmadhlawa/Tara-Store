"""Order invoices.

An invoice is an **immutable financial snapshot**. Once issued, nothing on it is
recomputed and nothing is joined at read time: the store's name, the customer's details,
every line and every total are copied into these tables at issue time, so editing a
product price or renaming the store later cannot change an invoice that was already
given to a customer.

The only mutation an issued invoice ever accepts is cancellation, which sets a status and
three audit columns and leaves every snapshot value untouched. Rows are never deleted and
numbers are never reused.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import InvoiceStatus, PaymentStatus
from app.db.base import Base, TimestampMixin, utcnow

DEFAULT_INVOICE_PREFIX = "INV"


class InvoiceSequence(Base):
    """Monotonic counter behind invoice numbering, one row per prefix.

    A counter rather than `MAX(invoice_number) + 1` so that a cancelled invoice's number
    can never be handed out again: cancellation does not decrement anything.
    """

    __tablename__ = "invoice_sequences"

    id: Mapped[int] = mapped_column(primary_key=True)
    prefix: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    last_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        CheckConstraint("last_number >= 0", name="ck_invoice_sequence_non_negative"),
    )


class Invoice(TimestampMixin, Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str] = mapped_column(
        String(40), unique=True, index=True, nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default=InvoiceStatus.ACTIVE.value,
        server_default=InvoiceStatus.ACTIVE.value,
        nullable=False,
        index=True,
    )
    # ``active`` is stored only for the one current invoice; archived rows use NULL.
    # The nullable unique pair is portable across SQLite and MySQL.
    active_invoice_marker: Mapped[str | None] = mapped_column(
        String(16).evaluates_none(), server_default="active", nullable=True
    )
    replacement_invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT"), unique=True, nullable=True
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )

    # ── snapshot: the order it was issued for ────────────────────────────────
    order_number: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── snapshot: the store, as it was on the issue date ─────────────────────
    store_name: Mapped[str] = mapped_column(String(150), nullable=False)
    store_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    store_whatsapp: Mapped[str | None] = mapped_column(String(40), nullable=True)
    store_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    store_address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    store_logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Legal identity. Blank unless the owner has confirmed it in settings — an invoice
    # must never carry a registration number nobody verified.
    legal_business_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tax_number: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ── snapshot: the customer ───────────────────────────────────────────────
    customer_name: Mapped[str] = mapped_column(String(150), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_address: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_area_name: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # ── snapshot: the money ──────────────────────────────────────────────────
    currency_code: Mapped[str] = mapped_column(String(8), nullable=False)
    currency_symbol: Mapped[str] = mapped_column(String(8), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    coupon_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delivery_fee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    # Tax is off by default. When it is off, tax_amount is 0.00 and grand_total equals
    # the order total exactly.
    tax_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(6, 3), default=Decimal("0.000"), nullable=False
    )
    prices_include_tax: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    payment_status: Mapped[str] = mapped_column(
        String(24),
        default=PaymentStatus.UNPAID.value,
        server_default=PaymentStatus.UNPAID.value,
        nullable=False,
        index=True,
    )
    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), server_default="0.00", nullable=False
    )
    refunded_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), server_default="0.00", nullable=False
    )
    remaining_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), server_default="0.00", nullable=False
    )
    payment_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Value snapshot: account edits or deletion cannot rewrite the issuer identity.
    issued_by_admin_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    issued_by_admin_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    issued_by_admin_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── cancellation ─────────────────────────────────────────────────────────
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancelled_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )

    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceItem.id"
    )
    order = relationship("Order", back_populates="invoices", overlaps="invoice")
    replacement_invoice: Mapped["Invoice | None"] = relationship(
        "Invoice",
        remote_side="Invoice.id",
        foreign_keys=[replacement_invoice_id],
        back_populates="replaces_invoice",
    )
    replaces_invoice: Mapped["Invoice | None"] = relationship(
        "Invoice",
        uselist=False,
        foreign_keys="Invoice.replacement_invoice_id",
        back_populates="replacement_invoice",
    )
    activities: Mapped[list["OrderActivity"]] = relationship(back_populates="invoice")

    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="ck_invoices_subtotal_non_negative"),
        CheckConstraint("grand_total >= 0", name="ck_invoices_grand_total_non_negative"),
        CheckConstraint("tax_amount >= 0", name="ck_invoices_tax_non_negative"),
        CheckConstraint(
            "(status = 'active' AND active_invoice_marker IS NOT NULL "
            "AND active_invoice_marker = 'active') "
            "OR (status <> 'active' AND active_invoice_marker IS NULL)",
            name="ck_invoices_active_invoice_marker",
        ),
        UniqueConstraint("order_id", "active_invoice_marker", name="uq_invoices_order_active_marker"),
    )

    @property
    def is_cancelled(self) -> bool:
        return self.status == InvoiceStatus.CANCELLED.value


class InvoiceItem(Base):
    """One invoiced line. Copied from the order item; never re-derived from the product."""

    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )

    product_name: Mapped[str] = mapped_column(String(250), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    variant_description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    item_kind: Mapped[str] = mapped_column(
        String(16), default="catalog", server_default="catalog", nullable=False
    )
    manual_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_invoice_item_quantity_positive"),
    )
