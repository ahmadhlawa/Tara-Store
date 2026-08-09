"""Invoice schemas — admin surface only.

There is deliberately no public/storefront invoice schema. A customer's confirmation
page shows their order; invoices are an internal financial record and carry the store's
legal identity, so nothing here is reachable without an admin token.
"""

from __future__ import annotations

from pydantic import EmailStr, Field

from app.core.enums import InvoiceStatus, OrderSource, PaymentMethod, PaymentStatus
from app.schemas.common import APIModel, Money, UTCDateTime


class InvoiceItemOut(APIModel):
    id: int
    product_name: str
    sku: str | None = None
    variant_description: str | None = None
    unit_price: Money
    quantity: int
    line_total: Money


class InvoiceListOut(APIModel):
    id: int
    invoice_number: str
    order_id: int
    order_number: str
    source: OrderSource
    customer_name: str
    customer_phone: str
    issued_at: UTCDateTime
    grand_total: Money
    currency_symbol: str
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    paid_amount: Money
    remaining_amount: Money
    status: InvoiceStatus


class InvoiceLinkOut(APIModel):
    id: int
    invoice_number: str
    status: InvoiceStatus
    issued_at: UTCDateTime


class InvoiceActivityOut(APIModel):
    id: int
    actor_admin_id: int | None = None
    event_type: str
    before_data: dict | None = None
    after_data: dict | None = None
    reason: str | None = None
    created_at: UTCDateTime


class InvoiceOut(APIModel):
    """The full immutable snapshot, as printed."""

    id: int
    invoice_number: str
    status: InvoiceStatus
    issued_at: UTCDateTime

    order_id: int
    order_number: str
    source: OrderSource
    payment_method: PaymentMethod
    customer_notes: str | None = None

    store_name: str
    store_phone: str | None = None
    store_whatsapp: str | None = None
    store_email: EmailStr | None = None
    store_address: str | None = None
    store_logo_url: str | None = None
    legal_business_name: str | None = None
    registration_number: str | None = None
    tax_number: str | None = None

    customer_name: str
    customer_phone: str
    customer_email: EmailStr | None = None
    delivery_address: str
    delivery_area_name: str | None = None

    currency_code: str
    currency_symbol: str
    subtotal: Money
    discount: Money
    coupon_code: str | None = None
    delivery_fee: Money
    tax_enabled: bool
    tax_rate: Money
    prices_include_tax: bool
    tax_amount: Money
    grand_total: Money
    payment_status: PaymentStatus
    paid_amount: Money
    refunded_amount: Money
    remaining_amount: Money
    payment_details: str | None = None
    invoice_notes: str | None = None
    issued_by_admin_id: int | None = None
    issued_by_admin_name: str | None = None
    issued_by_admin_email: EmailStr | None = None

    cancelled_at: UTCDateTime | None = None
    cancellation_reason: str | None = None
    cancelled_by_admin_id: int | None = None

    items: list[InvoiceItemOut] = Field(default_factory=list)
    history: list[InvoiceLinkOut] = Field(default_factory=list)
    replacement_invoice: InvoiceLinkOut | None = None
    replaces_invoice: InvoiceLinkOut | None = None
    activities: list[InvoiceActivityOut] = Field(default_factory=list)


class InvoiceSummary(APIModel):
    """Attached to an order so Admin can link straight to it."""

    id: int
    invoice_number: str
    status: InvoiceStatus
    issued_at: UTCDateTime
    grand_total: Money


class InvoiceCancelRequest(APIModel):
    reason: str | None = Field(default=None, max_length=500)


class InvoicePaymentUpdate(APIModel):
    paid_amount: Money | None = Field(default=None, ge=0)
    refunded_amount: Money | None = Field(default=None, ge=0)
    payment_method: PaymentMethod | None = None
    payment_details: str | None = Field(default=None, max_length=2000)
    reason: str | None = Field(default=None, max_length=500)
