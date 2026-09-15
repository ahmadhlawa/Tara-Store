"""add persistent admin media thumbnails

Revision ID: 0020_media_thumbnails
Revises: 0019_inventory_alerts
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_media_thumbnails"
down_revision: Union[str, None] = "0019_inventory_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("media_assets", sa.Column("thumbnail_url", sa.String(600), nullable=True))


def downgrade() -> None:
    op.drop_column("media_assets", "thumbnail_url")
