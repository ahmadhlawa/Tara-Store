"""Invoice issuance, synchronization, numbering and archival.

Writes share the caller's transaction with the order. Completion issues one active
invoice, enforced by the unique active marker. Completed edits synchronize that row;
leaving completion archives it. Historical rows, issuer/settings snapshots and numbers
are retained, and the numbering counter never decrements.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import InvoiceStatus, OrderStatus, PaymentStatus
from app.db.base import utcnow
from app.models import AdminUser, Invoice, InvoiceItem, InvoiceSequence, Order
from app.models.invoices import DEFAULT_INVOICE_PREFIX
from app.services import store_settings as settings_service
from app.services.errors import ConflictError, DomainError, NotFoundError
from app.services.pricing import ZERO, money

# Zero-padding for the numeric part: INV-000001. Six digits keeps a million invoices
# aligned in a printed list; past that the number simply grows.
NUMBER_WIDTH = 6


@dataclass(frozen=True, slots=True)
class PaymentUpdate:
    paid_amount: Decimal
    refunded_amount: Decimal
    remaining_amount: Decimal
    status: PaymentStatus


def _nonnegative_payment_amount(value: Decimal, *, field: str) -> Decimal:
    raw = Decimal(str(value))
    if raw < 0:
        raise DomainError(f"{field} cannot be negative.", code=f"negative_{field}")
    return money(raw)


def validate_payment_update(*, total_amount: Decimal, payment_status: str) -> PaymentUpdate:
    """Derive a complete payment snapshot from the requested state and server total."""
    if payment_status not in {PaymentStatus.UNPAID.value, PaymentStatus.PAID.value, PaymentStatus.REFUNDED.value}:
        raise DomainError("Select unpaid, paid or refunded.", code="invalid_payment_status")
    total = _nonnegative_payment_amount(total_amount, field="total_amount")
    status = PaymentStatus(payment_status)
    paid = ZERO if status == PaymentStatus.UNPAID else total
    refunded = total if status == PaymentStatus.REFUNDED else ZERO
    remaining = total if status == PaymentStatus.UNPAID else ZERO
    return PaymentUpdate(paid, refunded, remaining, status)


def _normalize_prefix(raw: str | None) -> str:
    """A prefix is upper-case, alphanumeric-or-dash, and never empty."""
    cleaned = "".join(
        char for char in (raw or "").strip().upper() if char.isalnum() or char in "-_"
    )
    return cleaned[:12] or DEFAULT_INVOICE_PREFIX


def next_invoice_number(db: Session, prefix: str) -> str:
    """Reserve the next number in `prefix`'s series.

    The row is locked for update where the database supports it, so two concurrent
    completions queue rather than race. SQLite has no row locks, but it serialises
    write transactions anyway, which gives the same outcome. The unique constraint on
    `invoice_number` is the backstop under either engine.
    """
    stmt = select(InvoiceSequence).where(InvoiceSequence.prefix == prefix)
    if db.bind is not None and db.bind.dialect.name != "sqlite":
        stmt = stmt.with_for_update()

    sequence = db.execute(stmt).scalar_one_or_none()
    if sequence is None:
        sequence = InvoiceSequence(prefix=prefix, last_number=0)
        db.add(sequence)
        db.flush()

    sequence.last_number += 1
    db.flush()
    return f"{prefix}-{sequence.last_number:0{NUMBER_WIDTH}d}"


def _tax_for(total: Decimal, *, enabled: bool, rate: Decimal, inclusive: bool) -> Decimal:
    """Tax on the order total (goods after discount, delivery and packaging).

    Disabled, or a zero rate, means exactly zero — never a rounding artefact — so a
    non-tax instance's invoice totals match its order totals to the cent.
    """
    if not enabled or rate <= 0:
        return ZERO
    fraction = Decimal(str(rate)) / Decimal("100")
    if inclusive:
        # The total already contains the tax; report the portion of it that is tax.
        return money(total - (total / (Decimal("1") + fraction)))
    return money(total * fraction)


def get_for_order(db: Session, order_id: int) -> Invoice | None:
    return db.execute(
        select(Invoice)
        .options(selectinload(Invoice.items))
        .where(
            Invoice.order_id == order_id,
            Invoice.status == InvoiceStatus.ACTIVE.value,
            Invoice.active_invoice_marker == InvoiceStatus.ACTIVE.value,
        )
        .order_by(Invoice.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def issue_for_order(
    db: Session,
    order: Order,
    *,
    admin: AdminUser | None = None,
    payment_method: str | None = None,
    payment_status: str = PaymentStatus.UNPAID.value,
    payment_details: str | None = None,
    invoice_notes: str | None = None,
) -> Invoice:
    """Issue for a completed order, idempotently returning its active invoice."""
    order = db.execute(
        select(Order).where(Order.id == order.id).with_for_update()
    ).scalar_one()
    if order.status != OrderStatus.COMPLETED.value:
        raise DomainError("Only completed orders can receive an invoice.", code="order_not_completed")
    existing = get_for_order(db, order.id)
    if existing is not None:
        return existing

    settings = settings_service.get_or_create_settings(db)
    prefix = _normalize_prefix(settings.invoice_prefix)

    tax_enabled = bool(settings.tax_enabled)
    tax_rate = Decimal(str(settings.tax_rate or 0))
    inclusive = bool(settings.prices_include_tax)
    order_total = money(order.total)
    tax_amount = _tax_for(
        order_total, enabled=tax_enabled, rate=tax_rate, inclusive=inclusive
    )
    # Inclusive tax is already inside the order total, so it must not be added again.
    grand_total = order_total if (inclusive or not tax_enabled) else money(order_total + tax_amount)
    payment = validate_payment_update(
        total_amount=grand_total,
        payment_status=payment_status,
    )

    predecessor = db.execute(
        select(Invoice)
        .where(
            Invoice.order_id == order.id,
            Invoice.status == InvoiceStatus.REPLACED.value,
        )
        .order_by(Invoice.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    invoice = Invoice(
        invoice_number=next_invoice_number(db, prefix),
        order_id=order.id,
        status=InvoiceStatus.ISSUED.value,
        active_invoice_marker=InvoiceStatus.ACTIVE.value,
        replacement_invoice=predecessor,
        issued_at=utcnow(),
        order_number=order.order_number,
        source=order.source,
        payment_method=payment_method or order.payment_method,
        customer_notes=order.customer_notes,
        store_name=settings.store_name_ar or settings.store_name,
        store_phone=settings.phone,
        store_whatsapp=settings.whatsapp,
        store_email=settings.email,
        store_address=settings.address,
        store_logo_url=settings.logo_url,
        legal_business_name=settings.legal_business_name,
        registration_number=settings.registration_number,
        tax_number=settings.tax_number,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        customer_email=order.customer_email,
        delivery_address=order.address,
        delivery_area_name=order.delivery_area_name,
        currency_code=settings.currency_code,
        currency_symbol=settings.currency_symbol,
        subtotal=money(order.subtotal),
        discount=money(order.discount),
        coupon_code=order.coupon_code,
        delivery_fee=money(order.delivery_fee),
        packaging_type=order.packaging_type,
        packaging_fee=money(order.packaging_fee),
        tax_enabled=tax_enabled,
        tax_rate=tax_rate,
        prices_include_tax=inclusive,
        tax_amount=tax_amount,
        grand_total=grand_total,
        payment_status=payment.status.value,
        paid_amount=payment.paid_amount,
        refunded_amount=payment.refunded_amount,
        remaining_amount=payment.remaining_amount,
        payment_details=(payment_details or "").strip() or None,
        invoice_notes=(invoice_notes or "").strip() or None,
        issued_by_admin_id=admin.id if admin else None,
        issued_by_admin_name=admin.full_name if admin else None,
        issued_by_admin_email=admin.email if admin else None,
    )

    for item in order.items:
        invoice.items.append(
            InvoiceItem(
                product_name=item.product_name,
                sku=item.sku,
                variant_description=item.variant_description,
                item_kind=item.item_kind,
                manual_description=item.manual_description,
                unit_price=money(item.unit_price),
                quantity=item.quantity,
                line_total=money(item.line_total),
            )
        )

    db.add(invoice)
    db.flush()
    from app.services.orders import record_order_activity

    record_order_activity(
        db,
        order_id=order.id,
        invoice_id=invoice.id,
        actor_admin_id=admin.id if admin else None,
        event_type="invoice_issued",
        before_data=None,
        after_data={
            "invoice_number": invoice.invoice_number,
            "total_amount": invoice.grand_total,
            "replacement_invoice_id": predecessor.id if predecessor else None,
        },
        reason=None,
    )
    return invoice


def archive_active_for_order(
    db: Session, order: Order, *, admin: AdminUser | None = None, reason: str | None = None
) -> Invoice | None:
    """Retire the current snapshot without deleting its row or releasing stock."""
    invoice = get_for_order(db, order.id)
    if invoice is None:
        return None

    invoice.status = InvoiceStatus.REPLACED.value
    invoice.active_invoice_marker = None
    db.flush()
    from app.services.orders import record_order_activity

    record_order_activity(
        db,
        order_id=order.id,
        invoice_id=invoice.id,
        actor_admin_id=admin.id if admin else None,
        event_type="invoice_replaced",
        before_data={"status": InvoiceStatus.ACTIVE.value, "invoice_number": invoice.invoice_number},
        after_data={"status": InvoiceStatus.REPLACED.value, "invoice_number": invoice.invoice_number},
        reason=reason,
    )
    return invoice


def replace_for_reopen(
    db: Session, order: Order, *, admin: AdminUser, reason: str
) -> Invoice | None:
    """Compatibility entry point for archiving on reopen."""
    return archive_active_for_order(db, order, admin=admin, reason=reason)


_ORDER_SNAPSHOT_FIELDS = {
    "customer_name": "customer_name", "customer_phone": "customer_phone",
    "customer_email": "customer_email", "delivery_address": "address",
    "delivery_area_name": "delivery_area_name", "customer_notes": "customer_notes",
    "payment_method": "payment_method", "subtotal": "subtotal", "discount": "discount",
    "coupon_code": "coupon_code", "delivery_fee": "delivery_fee",
    "packaging_type": "packaging_type", "packaging_fee": "packaging_fee",
}
_ITEM_SNAPSHOT_FIELDS = (
    "product_name", "sku", "variant_description", "item_kind", "manual_description",
    "unit_price", "quantity", "line_total",
)


def _current_snapshot(invoice: Invoice) -> dict:
    fields = (*_ORDER_SNAPSHOT_FIELDS, "tax_amount", "grand_total", "payment_status",
              "paid_amount", "refunded_amount", "remaining_amount")
    return {
        **{field: getattr(invoice, field) for field in fields},
        "items": [{field: getattr(item, field) for field in _ITEM_SNAPSHOT_FIELDS}
                  for item in invoice.items],
    }


def sync_active_from_order(
    db: Session, order: Order, *, admin: AdminUser, reason: str | None = None
) -> Invoice:
    """Synchronize business values using historical tax settings and invoice identity."""
    if order.status != OrderStatus.COMPLETED.value:
        raise DomainError("Only completed orders can synchronize an invoice.", code="order_not_completed")
    invoice = db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(
            Invoice.order_id == order.id, Invoice.status == InvoiceStatus.ACTIVE.value,
            Invoice.active_invoice_marker == InvoiceStatus.ACTIVE.value,
        ).with_for_update().execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if invoice is None:
        raise DomainError("Completed orders require an active invoice.", code="active_invoice_required")
    before = _current_snapshot(invoice)
    for field, order_field in _ORDER_SNAPSHOT_FIELDS.items():
        setattr(invoice, field, getattr(order, order_field))
    order_total = money(order.total)
    invoice.tax_amount = _tax_for(order_total, enabled=invoice.tax_enabled,
                                  rate=invoice.tax_rate, inclusive=invoice.prices_include_tax)
    invoice.grand_total = (order_total if invoice.prices_include_tax or not invoice.tax_enabled
                           else money(order_total + invoice.tax_amount))
    if invoice.grand_total != before["grand_total"]:
        # Match migration 0018's aliases only when financially updating the snapshot.
        status = {PaymentStatus.PARTIALLY_PAID.value: PaymentStatus.UNPAID.value,
                  PaymentStatus.PARTIALLY_REFUNDED.value: PaymentStatus.REFUNDED.value}.get(
                      invoice.payment_status, invoice.payment_status)
        payment = validate_payment_update(total_amount=invoice.grand_total, payment_status=status)
        invoice.payment_status = payment.status.value
        invoice.paid_amount = payment.paid_amount
        invoice.refunded_amount = payment.refunded_amount
        invoice.remaining_amount = payment.remaining_amount
    invoice.items[:] = [InvoiceItem(**{field: getattr(item, field) for field in _ITEM_SNAPSHOT_FIELDS})
                        for item in order.items]
    after = _current_snapshot(invoice)
    if before != after:
        from app.services.orders import record_order_activity
        record_order_activity(
            db, order_id=order.id, invoice_id=invoice.id, actor_admin_id=admin.id,
            event_type="invoice_synchronized", before_data=before, after_data=after, reason=reason,
        )
    db.flush()
    return invoice


def cancel_for_order(
    db: Session,
    order: Order,
    *,
    admin: AdminUser | None = None,
    reason: str | None = None,
) -> Invoice | None:
    """Cancel the order's invoice, if it has one that is still issued.

    The invoice row and its number survive: only the status and the three audit columns
    change. An order with no invoice, or one already cancelled, is left alone.
    """
    invoice = get_for_order(db, order.id)
    if invoice is None or invoice.is_cancelled:
        return invoice

    invoice.status = InvoiceStatus.CANCELLED.value
    invoice.active_invoice_marker = None
    invoice.cancelled_at = utcnow()
    invoice.cancellation_reason = (reason or "").strip()[:500] or None
    invoice.cancelled_by_admin_id = admin.id if admin else None
    db.flush()
    from app.services.orders import record_order_activity

    record_order_activity(
        db,
        order_id=order.id,
        invoice_id=invoice.id,
        actor_admin_id=admin.id if admin else None,
        event_type="invoice_cancelled",
        before_data={"status": InvoiceStatus.ACTIVE.value},
        after_data={"status": InvoiceStatus.CANCELLED.value},
        reason=reason,
    )
    return invoice


def get_by_number(db: Session, invoice_number: str) -> Invoice:
    invoice = db.execute(
        select(Invoice)
        .options(
            selectinload(Invoice.items),
            selectinload(Invoice.activities),
            selectinload(Invoice.replacement_invoice),
            selectinload(Invoice.replaces_invoice),
        )
        .where(Invoice.invoice_number == invoice_number.strip().upper())
    ).scalar_one_or_none()
    if invoice is None:
        raise NotFoundError("الفاتورة غير موجودة.", code="invoice_not_found")
    return invoice


def order_for_invoice(db: Session, invoice: Invoice) -> Order:
    order = db.get(Order, invoice.order_id)
    if order is None:  # pragma: no cover - the FK is RESTRICT, so this cannot happen
        raise NotFoundError("طلب الفاتورة غير موجود.", code="order_not_found")
    return order


def assert_cancellable(order: Order) -> None:
    """An invoice is cancelled by cancelling its order, so the order must allow it."""
    if order.status == OrderStatus.CANCELLED.value:
        raise ConflictError("الطلب ملغى مسبقاً.", code="order_already_cancelled")


def search(
    db: Session,
    *,
    q: str | None = None,
    status: str | None = None,
    payment_status: str | None = None,
    source: str | None = None,
    employee_id: int | None = None,
    issued_from=None,
    issued_to=None,
):
    """Build the admin list query: free-text over the three identifiers, plus filters."""
    stmt = select(Invoice)
    if status:
        stmt = stmt.where(Invoice.status == status)
    if payment_status:
        stmt = stmt.where(Invoice.payment_status == payment_status)
    if employee_id is not None:
        stmt = stmt.where(Invoice.issued_by_admin_id == employee_id)
    if source:
        stmt = stmt.where(Invoice.source == source)
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(
            func.upper(Invoice.invoice_number).like(needle.upper())
            | func.upper(Invoice.order_number).like(needle.upper())
            | Invoice.customer_name.like(needle)
            | Invoice.customer_phone.like(needle)
        )
    if issued_from is not None:
        stmt = stmt.where(Invoice.issued_at >= issued_from)
    if issued_to is not None:
        stmt = stmt.where(Invoice.issued_at <= issued_to)
    return stmt.order_by(Invoice.id.desc())


def history_for_invoice(db: Session, invoice: Invoice) -> list[Invoice]:
    """Return persisted snapshots for the same order; never hydrate live order data."""
    return list(
        db.execute(
            select(Invoice)
            .where(Invoice.order_id == invoice.order_id)
            .order_by(Invoice.id.asc())
        ).scalars()
    )


def update_payment(
    db: Session,
    invoice: Invoice,
    *,
    payment_status: str,
    payment_method: str | None,
    payment_details: str | None,
    details_provided: bool,
    reason: str | None,
    admin: AdminUser,
) -> Invoice:
    """Apply the narrowly permitted financial mutation and append its audit event."""
    # Serialize concurrent financial writes and refresh rows that callers may have
    # loaded before another transaction committed.
    invoice = db.execute(
        select(Invoice)
        .where(Invoice.id == invoice.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()
    if invoice.status != InvoiceStatus.ACTIVE.value:
        raise ConflictError("Only an active invoice can receive a payment update.", code="invoice_not_active")

    before = {
        "payment_method": invoice.payment_method,
        "payment_status": invoice.payment_status,
        "paid_amount": invoice.paid_amount,
        "refunded_amount": invoice.refunded_amount,
        "remaining_amount": invoice.remaining_amount,
        "payment_details": invoice.payment_details,
    }
    payment = validate_payment_update(total_amount=invoice.grand_total, payment_status=payment_status)
    invoice.paid_amount = payment.paid_amount
    invoice.refunded_amount = payment.refunded_amount
    invoice.remaining_amount = payment.remaining_amount
    invoice.payment_status = payment.status.value
    if payment_method is not None:
        invoice.payment_method = payment_method
    if details_provided:
        invoice.payment_details = (payment_details or "").strip() or None

    from app.services.orders import record_order_activity

    record_order_activity(
        db,
        order_id=invoice.order_id,
        invoice_id=invoice.id,
        actor_admin_id=admin.id,
        event_type="payment_updated",
        before_data=before,
        after_data={
            "payment_method": invoice.payment_method,
            "payment_status": invoice.payment_status,
            "paid_amount": invoice.paid_amount,
            "refunded_amount": invoice.refunded_amount,
            "remaining_amount": invoice.remaining_amount,
            "payment_details": invoice.payment_details,
        },
        reason=reason,
    )
    db.flush()
    return invoice
