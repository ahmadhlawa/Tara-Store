"""order packaging

Revision ID: 0030_order_packaging
Revises: 0029_storefront_analytics
Create Date: 2026-10-03 21:33:22.442177
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0030_order_packaging'
down_revision: Union[str, None] = '0029_storefront_analytics'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("orders", "invoices"):
        op.add_column(table, sa.Column(
            "packaging_type", sa.String(16), nullable=False, server_default="normal"
        ))
        op.add_column(table, sa.Column(
            "packaging_fee", sa.Numeric(12, 2), nullable=False, server_default="0.00"
        ))


def downgrade() -> None:
    for table in ("invoices", "orders"):
        op.drop_column(table, "packaging_fee")
        op.drop_column(table, "packaging_type")
