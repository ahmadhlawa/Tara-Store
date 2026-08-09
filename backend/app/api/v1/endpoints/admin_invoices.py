"""Admin invoice access.

Read, search and cancel. There is no create endpoint — invoices are issued by the domain
when an order is confirmed, never by hand. There is no update endpoint and no delete
endpoint: an issued invoice is immutable, and cancelling one keeps the row and its
number permanently.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentAdmin, DbSession, PageParams
from app.core.enums import InvoiceStatus, OrderSource, OrderStatus, PaymentStatus
from app.schemas.common import Page
from app.schemas.invoices import (
    InvoiceCancelRequest,
    InvoiceLinkOut,
    InvoiceListOut,
    InvoiceOut,
    InvoicePaymentUpdate,
)
from app.services import catalog as catalog_service
from app.services import invoices as invoices_service
from app.services import orders as orders_service

router = APIRouter(prefix="/admin", tags=["admin-invoices"])


@router.get("/invoices", response_model=Page[InvoiceListOut])
def list_invoices(
    db: DbSession,
    admin: CurrentAdmin,
    pagination: PageParams,
    q: Annotated[str | None, Query(max_length=120)] = None,
    invoice_status: Annotated[InvoiceStatus | None, Query(alias="status")] = None,
    payment_status: PaymentStatus | None = None,
    source: OrderSource | None = None,
    employee_id: Annotated[int | None, Query(ge=1)] = None,
    issued_from: Annotated[date | None, Query()] = None,
    issued_to: Annotated[date | None, Query()] = None,
) -> Page[InvoiceListOut]:
    """Search by invoice number, order number, customer name or phone; filter by
    status and issue date. `issued_to` is inclusive of the whole day."""
    stmt = invoices_service.search(
        db,
        q=q,
        status=invoice_status.value if invoice_status else None,
        payment_status=payment_status.value if payment_status else None,
        source=source.value if source else None,
        employee_id=employee_id,
        issued_from=datetime.combine(issued_from, time.min) if issued_from else None,
        issued_to=datetime.combine(issued_to, time.max) if issued_to else None,
    )
    rows, total = catalog_service.paginate(
        db, stmt, offset=pagination.offset, limit=pagination.page_size
    )
    return Page.build(
        [InvoiceListOut.model_validate(row) for row in rows],
        total,
        pagination.page,
        pagination.page_size,
    )


@router.get("/invoices/{invoice_number}", response_model=InvoiceOut)
def get_invoice(invoice_number: str, db: DbSession, admin: CurrentAdmin) -> InvoiceOut:
    return _invoice_detail(db, invoices_service.get_by_number(db, invoice_number))


def _invoice_detail(db: DbSession, invoice) -> InvoiceOut:
    """Build detail only from the invoice snapshot and its immutable audit records."""
    detail = InvoiceOut.model_validate(invoice)
    detail.history = [
        InvoiceLinkOut.model_validate(row)
        for row in invoices_service.history_for_invoice(db, invoice)
    ]
    return detail


@router.get("/orders/{order_id}/invoice", response_model=InvoiceOut)
def get_order_invoice(order_id: int, db: DbSession, admin: CurrentAdmin) -> InvoiceOut:
    from app.api.crud import get_or_404
    from app.models import Order

    get_or_404(db, Order, order_id, "الطلب غير موجود.")
    invoice = invoices_service.get_for_order(db, order_id)
    if invoice is None:
        from app.services.errors import NotFoundError

        raise NotFoundError("لا توجد فاتورة لهذا الطلب.", code="invoice_not_found")
    return _invoice_detail(db, invoice)


@router.patch("/invoices/{invoice_number}/payment", response_model=InvoiceOut)
def update_invoice_payment(
    invoice_number: str,
    payload: InvoicePaymentUpdate,
    db: DbSession,
    admin: CurrentAdmin,
) -> InvoiceOut:
    invoice = invoices_service.get_by_number(db, invoice_number)
    invoices_service.update_payment(
        db,
        invoice,
        paid_amount=payload.paid_amount,
        refunded_amount=payload.refunded_amount,
        payment_method=payload.payment_method.value if payload.payment_method else None,
        payment_details=payload.payment_details,
        details_provided="payment_details" in payload.model_fields_set,
        reason=payload.reason,
        admin=admin,
    )
    db.commit()
    return _invoice_detail(db, invoices_service.get_by_number(db, invoice_number))


@router.post("/invoices/{invoice_number}/cancel", response_model=InvoiceOut)
def cancel_invoice(
    invoice_number: str,
    payload: InvoiceCancelRequest,
    db: DbSession,
    admin: CurrentAdmin,
) -> InvoiceOut:
    """Cancel an invoice by cancelling its order.

    Deliberately routed through the order transition rather than flipping the invoice's
    status directly, so cancelling from this screen behaves exactly like cancelling from
    the order screen: stock is restored, the status history records who did it, and the
    order and its invoice can never disagree about whether it is live.
    """
    invoice = invoices_service.get_by_number(db, invoice_number)
    order = invoices_service.order_for_invoice(db, invoice)
    invoices_service.assert_cancellable(order)

    orders_service.change_status(
        db,
        order,
        OrderStatus.CANCELLED.value,
        admin=admin,
        note=payload.reason,
    )
    db.commit()
    return invoices_service.get_by_number(db, invoice_number)
