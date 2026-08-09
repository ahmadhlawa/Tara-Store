from __future__ import annotations

from decimal import Decimal

from pydantic import EmailStr, Field

from app.schemas.common import APIModel, Money, UTCDateTime


class StoreSettingsPublic(APIModel):
    """What the storefront is allowed to know about the store.

    Legal identity, tax configuration and the invoice prefix are deliberately absent:
    they belong on an invoice, not in a public JSON payload.
    """

    store_name: str
    store_name_ar: str | None = None
    store_tagline: str | None = None
    logo_url: str | None = None
    favicon_url: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    location_url: str | None = None
    working_hours: str | None = None
    announcement: str | None = None
    instagram_url: str | None = None
    facebook_url: str | None = None
    tiktok_url: str | None = None
    youtube_url: str | None = None
    currency_code: str
    currency_symbol: str
    primary_color: str
    secondary_color: str
    accent_color: str
    seo_title: str | None = None
    seo_description: str | None = None
    maintenance_mode: bool
    # Shown to a customer who picks the manual/transfer method. Empty until the owner
    # supplies real account details, and the storefront shows nothing while it is empty.
    manual_payment_instructions: str | None = None


class StoreSettingsAdmin(StoreSettingsPublic):
    """Adds the operational fields that must not reach the storefront."""

    id: int
    order_notifications_email: EmailStr | None = None
    invoice_prefix: str
    invoice_notes: str | None = None
    legal_business_name: str | None = None
    registration_number: str | None = None
    tax_number: str | None = None
    tax_enabled: bool
    tax_rate: Money
    prices_include_tax: bool
    updated_at: UTCDateTime


class StoreSettingsUpdate(APIModel):
    store_name: str | None = Field(default=None, min_length=1, max_length=150)
    store_name_ar: str | None = Field(default=None, max_length=150)
    store_tagline: str | None = Field(default=None, max_length=200)
    logo_url: str | None = Field(default=None, max_length=500)
    favicon_url: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=40)
    whatsapp: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=300)
    location_url: str | None = Field(default=None, max_length=500)
    working_hours: str | None = Field(default=None, max_length=200)
    announcement: str | None = Field(default=None, max_length=300)
    instagram_url: str | None = Field(default=None, max_length=500)
    facebook_url: str | None = Field(default=None, max_length=500)
    tiktok_url: str | None = Field(default=None, max_length=500)
    youtube_url: str | None = Field(default=None, max_length=500)
    currency_code: str | None = Field(default=None, min_length=1, max_length=8)
    currency_symbol: str | None = Field(default=None, min_length=1, max_length=8)
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    secondary_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    accent_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = None
    maintenance_mode: bool | None = None
    order_notifications_email: EmailStr | None = None
    manual_payment_instructions: str | None = Field(default=None, max_length=2000)

    # Invoicing. The prefix applies to invoices issued from now on; numbers already
    # issued keep the prefix they were created with.
    invoice_prefix: str | None = Field(
        default=None, min_length=1, max_length=12, pattern=r"^[A-Za-z0-9_-]+$"
    )
    invoice_notes: str | None = Field(default=None, max_length=2000)

    # Legal and tax. Leave these alone unless the owner has confirmed the values in
    # writing — they are printed on customer invoices.
    legal_business_name: str | None = Field(default=None, max_length=200)
    registration_number: str | None = Field(default=None, max_length=64)
    tax_number: str | None = Field(default=None, max_length=64)
    tax_enabled: bool | None = None
    tax_rate: Decimal | None = Field(default=None, ge=0, le=100)
    prices_include_tax: bool | None = None
