"""add nullable storefront theme overrides

Revision ID: 0012_storefront_theme_overrides
Revises: 0011_social_visibility
"""
from __future__ import annotations

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0012_storefront_theme_overrides"
down_revision: Union[str, None] = "0011_social_visibility"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FIELDS = ("theme_primary_color", "theme_secondary_color", "theme_soft_color", "theme_nav_strip_background", "theme_nav_strip_text", "theme_footer_background", "theme_footer_text", "theme_footer_muted_text", "theme_button_primary_background", "theme_button_primary_text")

def upgrade() -> None:
    with op.batch_alter_table("store_settings") as batch:
        for name in _FIELDS:
            batch.add_column(sa.Column(name, sa.String(length=7), nullable=True))

def downgrade() -> None:
    with op.batch_alter_table("store_settings") as batch:
        for name in reversed(_FIELDS):
            batch.drop_column(name)
