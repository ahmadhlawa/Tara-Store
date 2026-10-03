"""Normalize current order statuses; retain historical records and lock metadata."""

from alembic import op
import sqlalchemy as sa

revision = "0031_order_lifecycle"
down_revision = "0030_order_packaging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    orders = sa.table("orders", sa.column("status", sa.String()), sa.column("is_locked", sa.Boolean()))
    for old, new in (("confirmed", "ready"), ("delivered", "completed")):
        op.execute(orders.update().where(orders.c.status == old).values(status=new))
    # The obsolete flag must not block the approved workflow. Keep the column and
    # timestamps for read compatibility, without touching history or invoice rows.
    op.execute(orders.update().where(orders.c.is_locked == sa.true()).values(is_locked=False))


def downgrade() -> None:
    # Normalization loses provenance: reversing it would relabel canonical orders
    # that were already ready/completed. Preserve business data on downgrade.
    pass
