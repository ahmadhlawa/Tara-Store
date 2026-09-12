"""add category home showcase flag

Revision ID: 0017_category_home_showcase
Revises: 0016_simple_product_choices
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_category_home_showcase"
down_revision: Union[str, None] = "0016_simple_product_choices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("show_on_home", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("categories", "show_on_home")
