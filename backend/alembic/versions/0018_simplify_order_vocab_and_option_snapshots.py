"""simplify order vocabulary and snapshot selected options

Revision ID: 0018_simplify_order_vocab
Revises: 0017_category_home_showcase
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_simplify_order_vocab"
down_revision: Union[str, None] = "0017_category_home_showcase"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "order_items",
        sa.Column("selected_option_value_ids", sa.JSON(), nullable=False, server_default="[]"),
    )
    status_map = {
        "pending": "confirmed", "reviewing": "confirmed",
        "processing": "ready", "preparing": "ready",
        "shipped": "delivered", "out_for_delivery": "delivered",
    }
    source_map = {"phone": "other", "walk_in": "other", "social": "other"}
    payment_map = {"partially_paid": "unpaid", "partially_refunded": "refunded"}
    for old, new in status_map.items():
        op.execute(sa.text("UPDATE orders SET status=:new WHERE status=:old").bindparams(old=old, new=new))
    for old, new in source_map.items():
        op.execute(sa.text("UPDATE orders SET source=:new WHERE source=:old").bindparams(old=old, new=new))
    for old, new in payment_map.items():
        op.execute(sa.text("UPDATE invoices SET payment_status=:new WHERE payment_status=:old").bindparams(old=old, new=new))


def downgrade() -> None:
    op.drop_column("order_items", "selected_option_value_ids")
