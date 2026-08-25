from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.invoices import DEFAULT_INVOICE_PREFIX

# Single source of truth for the shipped defaults: used as the column defaults and
# as the response for an instance whose settings row has not been created yet.
STORE_SETTINGS_DEFAULTS: dict[str, object] = {
    "store_name": "Store",
    "currency_code": "ILS",
    "currency_symbol": "₪",
    # Tara's approved palette: deep lilac as the brand, warm gold kept back as a
    # special accent and a muted sage for success states. The storefront's
    # stylesheet carries the same three as its own fallback, so an instance is on
    # brand whether or not this row has been written yet — and the owner can still
    # restyle from Admin.
    "primary_color": "#7F568F",
    "secondary_color": "#D19F57",
    "accent_color": "#4C7C63",
    "maintenance_mode": False,
    "instagram_visible": True,
    "facebook_visible": True,
    "tiktok_visible": True,
    "youtube_visible": True,
    "invoice_prefix": DEFAULT_INVOICE_PREFIX,
    "tax_enabled": False,
    "tax_rate": Decimal("0.000"),
    "prices_include_tax": False,
}


class StoreSettings(TimestampMixin, Base):
    """Single-row store identity. One instance == one store."""

    __tablename__ = "store_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    store_name: Mapped[str] = mapped_column(String(150), nullable=False, default="Store")
    store_tagline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    location_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    working_hours: Mapped[str | None] = mapped_column(String(200), nullable=True)
    announcement: Mapped[str | None] = mapped_column(String(300), nullable=True)

    instagram_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    facebook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tiktok_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    youtube_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    instagram_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    facebook_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tiktok_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    youtube_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    currency_code: Mapped[str] = mapped_column(String(8), default="ILS", nullable=False)
    currency_symbol: Mapped[str] = mapped_column(String(8), default="₪", nullable=False)

    primary_color: Mapped[str] = mapped_column(String(16), default="#7F568F", nullable=False)
    secondary_color: Mapped[str] = mapped_column(String(16), default="#D19F57", nullable=False)
    accent_color: Mapped[str] = mapped_column(String(16), default="#4C7C63", nullable=False)

    # Storefront-only optional overrides. Null deliberately means the CSS theme owns
    # the effective value; legacy identity colors above remain backward compatible.
    theme_primary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    theme_secondary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    theme_soft_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    theme_nav_strip_background: Mapped[str | None] = mapped_column(String(7), nullable=True)
    theme_nav_strip_text: Mapped[str | None] = mapped_column(String(7), nullable=True)
    theme_footer_background: Mapped[str | None] = mapped_column(String(7), nullable=True)
    theme_footer_text: Mapped[str | None] = mapped_column(String(7), nullable=True)
    theme_footer_muted_text: Mapped[str | None] = mapped_column(String(7), nullable=True)
    theme_button_primary_background: Mapped[str | None] = mapped_column(String(7), nullable=True)
    theme_button_primary_text: Mapped[str | None] = mapped_column(String(7), nullable=True)

    seo_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    maintenance_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    order_notifications_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Arabic display name ──────────────────────────────────────────────────
    # The storefront is Arabic and RTL, but the registered/latin name is often what the
    # client calls the business in writing. Both are kept; the storefront prefers this
    # one when it is set, and falls back to store_name when it is not.
    store_name_ar: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # ── Manual payment ───────────────────────────────────────────────────────
    # Free text shown to a customer who chooses the manual/transfer method. Blank until
    # the owner supplies real account details — the storefront shows nothing rather than
    # inventing bank instructions.
    manual_payment_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Invoicing ────────────────────────────────────────────────────────────
    invoice_prefix: Mapped[str] = mapped_column(
        String(12), default=DEFAULT_INVOICE_PREFIX, nullable=False
    )
    invoice_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Legal and tax ────────────────────────────────────────────────────────
    # Tax is OFF by default and these are blank by default. An instance is not a tax
    # invoice issuer until its owner says so in writing; see
    # docs/client/data-needed-from-owner.md.
    legal_business_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tax_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tax_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(6, 3), default=Decimal("0.000"), nullable=False
    )
    prices_include_tax: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
