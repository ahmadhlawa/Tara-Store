"""Add a dedicated root-category banner image.

Revision ID: 0021_category_banner_image
Revises: 0020_media_thumbnails
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_category_banner_image"
down_revision = "0020_media_thumbnails"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("banner_image_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("categories", "banner_image_url")
