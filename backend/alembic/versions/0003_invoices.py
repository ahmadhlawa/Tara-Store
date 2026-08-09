"""order invoices, invoice numbering, and the invoice/tax/manual-payment settings

Adds the immutable invoice snapshot tables and the owner-editable configuration that
feeds them. Nothing in this migration backfills: orders that were already confirmed
before it ran have no invoice, which is the intended behaviour — an invoice records the
store as it was on the issue date, and that state no longer exists for a past order.

Every column type here is chosen to be identical on SQLite and MySQL 8 (String, Numeric,
Boolean, DateTime), matching the convention set by 0001.

Revision ID: 0003_invoices
Revises: 0002_instance_metadata
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_invoices"
down_revision: Union[str, None] = "0002_instance_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── store settings: invoicing, legal/tax, manual payment, Arabic name ────
    with op.batch_alter_table("store_settings") as batch:
        batch.add_column(sa.Column("store_name_ar", sa.String(length=150), nullable=True))
        batch.add_column(sa.Column("manual_payment_instructions", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column(
                "invoice_prefix",
                sa.String(length=12),
                nullable=False,
                server_default="INV",
            )
        )
        batch.add_column(sa.Column("invoice_notes", sa.Text(), nullable=True))
        batch.add_column(sa.Column("legal_business_name", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("registration_number", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("tax_number", sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column("tax_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(
            sa.Column(
                "tax_rate",
                sa.Numeric(precision=6, scale=3),
                nullable=False,
                server_default="0.000",
            )
        )
        batch.add_column(
            sa.Column(
                "prices_include_tax",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    # ── invoice numbering ───────────────────────────────────────────────────
    op.create_table(
        "invoice_sequences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("last_number >= 0", name="ck_invoice_sequence_non_negative"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prefix", name="uq_invoice_sequences_prefix"),
    )

    # ── invoices ────────────────────────────────────────────────────────────
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_number", sa.String(length=40), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("order_number", sa.String(length=32), nullable=False),
        sa.Column("payment_method", sa.String(length=32), nullable=False),
        sa.Column("customer_notes", sa.Text(), nullable=True),
        sa.Column("store_name", sa.String(length=150), nullable=False),
        sa.Column("store_phone", sa.String(length=40), nullable=True),
        sa.Column("store_whatsapp", sa.String(length=40), nullable=True),
        sa.Column("store_email", sa.String(length=255), nullable=True),
        sa.Column("store_address", sa.String(length=300), nullable=True),
        sa.Column("store_logo_url", sa.String(length=500), nullable=True),
        sa.Column("legal_business_name", sa.String(length=200), nullable=True),
        sa.Column("registration_number", sa.String(length=64), nullable=True),
        sa.Column("tax_number", sa.String(length=64), nullable=True),
        sa.Column("customer_name", sa.String(length=150), nullable=False),
        sa.Column("customer_phone", sa.String(length=40), nullable=False),
        sa.Column("customer_email", sa.String(length=255), nullable=True),
        sa.Column("delivery_address", sa.Text(), nullable=False),
        sa.Column("delivery_area_name", sa.String(length=150), nullable=True),
        sa.Column("currency_code", sa.String(length=8), nullable=False),
        sa.Column("currency_symbol", sa.String(length=8), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("discount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("coupon_code", sa.String(length=64), nullable=True),
        sa.Column("delivery_fee", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("tax_enabled", sa.Boolean(), nullable=False),
        sa.Column("tax_rate", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("prices_include_tax", sa.Boolean(), nullable=False),
        sa.Column("tax_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("grand_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=500), nullable=True),
        sa.Column("cancelled_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("subtotal >= 0", name="ck_invoices_subtotal_non_negative"),
        sa.CheckConstraint("grand_total >= 0", name="ck_invoices_grand_total_non_negative"),
        sa.CheckConstraint("tax_amount >= 0", name="ck_invoices_tax_non_negative"),
        # RESTRICT, not CASCADE: an invoice must survive any attempt to delete its order.
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cancelled_by_admin_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        # The database, not the application, guarantees one invoice per order.
        sa.UniqueConstraint("order_id", name="uq_invoices_order_id"),
    )
    op.create_index(op.f("ix_invoices_invoice_number"), "invoices", ["invoice_number"], unique=True)
    op.create_index(op.f("ix_invoices_order_number"), "invoices", ["order_number"], unique=False)
    op.create_index(op.f("ix_invoices_customer_phone"), "invoices", ["customer_phone"], unique=False)
    op.create_index(op.f("ix_invoices_status"), "invoices", ["status"], unique=False)
    op.create_index(op.f("ix_invoices_issued_at"), "invoices", ["issued_at"], unique=False)

    op.create_table(
        "invoice_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("product_name", sa.String(length=250), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=True),
        sa.Column("variant_description", sa.String(length=200), nullable=True),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_invoice_item_quantity_positive"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invoice_items_invoice_id"), "invoice_items", ["invoice_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_invoice_items_invoice_id"), table_name="invoice_items")
    op.drop_table("invoice_items")

    op.drop_index(op.f("ix_invoices_issued_at"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_status"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_customer_phone"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_order_number"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_invoice_number"), table_name="invoices")
    op.drop_table("invoices")

    op.drop_table("invoice_sequences")

    with op.batch_alter_table("store_settings") as batch:
        batch.drop_column("prices_include_tax")
        batch.drop_column("tax_rate")
        batch.drop_column("tax_enabled")
        batch.drop_column("tax_number")
        batch.drop_column("registration_number")
        batch.drop_column("legal_business_name")
        batch.drop_column("invoice_notes")
        batch.drop_column("invoice_prefix")
        batch.drop_column("manual_payment_instructions")
        batch.drop_column("store_name_ar")
