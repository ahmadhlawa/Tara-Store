"""persist storefront social visibility preferences

Revision ID: 0011_social_visibility
Revises: 0010_unique_media_filename
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_social_visibility"
down_revision: Union[str, None] = "0010_unique_media_filename"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("store_settings") as batch:
        for name in ("instagram_visible", "facebook_visible", "tiktok_visible", "youtube_visible"):
            batch.add_column(sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table("store_settings") as batch:
        for name in ("youtube_visible", "tiktok_visible", "facebook_visible", "instagram_visible"):
            batch.drop_column(name)
