"""Backfill deterministic category sibling order.

Revision ID: 0023_category_sibling_order
Revises: 0022_option_value_presentation
"""

from alembic import op
import sqlalchemy as sa


revision = "0023_category_sibling_order"
down_revision = "0022_option_value_presentation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    categories = sa.table(
        "categories",
        sa.column("id", sa.Integer()),
        sa.column("parent_id", sa.Integer()),
        sa.column("created_at", sa.DateTime()),
        sa.column("sort_order", sa.Integer()),
    )
    rows = connection.execute(
        sa.select(categories.c.id, categories.c.parent_id)
        .order_by(categories.c.parent_id, categories.c.created_at, categories.c.id)
    ).all()
    positions: dict[int | None, int] = {}
    for category_id, parent_id in rows:
        position = positions.get(parent_id, 0)
        connection.execute(
            categories.update().where(categories.c.id == category_id).values(sort_order=position)
        )
        positions[parent_id] = position + 1


def downgrade() -> None:
    pass
