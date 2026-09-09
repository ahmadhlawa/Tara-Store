"""add simple product choice pricing

Revision ID: 0016_simple_product_choices
Revises: 0015_hero_targets
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0016_simple_product_choices"
down_revision: Union[str, None] = "0015_hero_targets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("product_options", sa.Column("affects_price", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("product_option_values", sa.Column("price_override", sa.Numeric(12, 2), nullable=True))

def downgrade() -> None:
    op.drop_column("product_option_values", "price_override")
    op.drop_column("product_options", "affects_price")
