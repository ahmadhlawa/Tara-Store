"""add global inventory alert threshold and simplify product types

Revision ID: 0019_inventory_alerts
Revises: 0018_simplify_order_vocab
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_inventory_alerts"
down_revision: Union[str, None] = "0018_simplify_order_vocab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "store_settings",
        sa.Column("low_stock_threshold", sa.Integer(), nullable=False, server_default="5"),
    )
    with op.batch_alter_table("products") as batch_op:
        batch_op.alter_column("low_stock_threshold", existing_type=sa.Integer(), nullable=True)
    op.execute(sa.text(
        "UPDATE products SET product_type='standard' WHERE product_type='silicone_mold'"
    ))
    op.execute(sa.text(
        "UPDATE home_sections SET section_type='featured_products' WHERE section_type='silicone_molds'"
    ))
    # Existing per-product value 3 was the old mandatory default, not an intentional override.
    op.execute(sa.text("UPDATE products SET low_stock_threshold=NULL WHERE low_stock_threshold=3"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE products SET low_stock_threshold=3 WHERE low_stock_threshold IS NULL"))
    with op.batch_alter_table("products") as batch_op:
        batch_op.alter_column("low_stock_threshold", existing_type=sa.Integer(), nullable=False)
    op.drop_column("store_settings", "low_stock_threshold")
