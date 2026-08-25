"""persist immutable package fulfillment snapshots

Revision ID: 0013_package_components
Revises: 0012_storefront_theme_overrides
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_package_components"
down_revision: Union[str, None] = "0012_storefront_theme_overrides"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("package_items") as batch:
        batch.add_column(sa.Column("included_variant_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_package_items_included_variant_id_product_variants",
            "product_variants",
            ["included_variant_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_package_items_included_variant_id", ["included_variant_id"])

    op.create_table(
        "order_item_package_components",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=False),
        sa.Column("source_product_id", sa.Integer(), nullable=True),
        sa.Column("source_variant_id", sa.Integer(), nullable=True),
        sa.Column("product_name", sa.String(length=250), nullable=False),
        sa.Column("variant_description", sa.String(length=200), nullable=True),
        sa.Column("sku", sa.String(length=64), nullable=True),
        sa.Column("quantity_per_package", sa.Integer(), nullable=False),
        sa.Column("package_quantity", sa.Integer(), nullable=False),
        sa.Column("total_quantity", sa.Integer(), nullable=False),
        sa.Column("tracks_inventory", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("quantity_per_package > 0", name="ck_package_component_quantity_positive"),
        sa.CheckConstraint("package_quantity > 0", name="ck_package_component_package_quantity_positive"),
        sa.CheckConstraint("total_quantity > 0", name="ck_package_component_total_quantity_positive"),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_variant_id"], ["product_variants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_item_package_components_order_item_id", "order_item_package_components", ["order_item_id"])
    op.create_index("ix_order_item_package_components_source_product_id", "order_item_package_components", ["source_product_id"])
    op.create_index("ix_order_item_package_components_source_variant_id", "order_item_package_components", ["source_variant_id"])


def downgrade() -> None:
    op.drop_index("ix_order_item_package_components_source_variant_id", table_name="order_item_package_components")
    op.drop_index("ix_order_item_package_components_source_product_id", table_name="order_item_package_components")
    op.drop_index("ix_order_item_package_components_order_item_id", table_name="order_item_package_components")
    op.drop_table("order_item_package_components")
    with op.batch_alter_table("package_items") as batch:
        batch.drop_index("ix_package_items_included_variant_id")
        batch.drop_constraint("fk_package_items_included_variant_id_product_variants", type_="foreignkey")
        batch.drop_column("included_variant_id")
