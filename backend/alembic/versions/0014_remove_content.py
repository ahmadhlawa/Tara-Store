"""remove unused banners and articles

Revision ID: 0014_remove_content
Revises: 0013_package_components
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_remove_content"
down_revision: Union[str, None] = "0013_package_components"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # These tables have no external foreign keys.  Dropping the tables also drops
    # their table-local indexes on both SQLite and MySQL.
    op.drop_table("banners")
    op.drop_table("articles")


def downgrade() -> None:
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("slug", sa.String(length=260), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("featured_image_url", sa.String(length=500), nullable=True),
        sa.Column("category_label", sa.String(length=100), nullable=True),
        sa.Column("author_name", sa.String(length=150), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("seo_title", sa.String(length=200), nullable=True),
        sa.Column("seo_description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_articles_is_published", "articles", ["is_published"])
    op.create_index("ix_articles_slug", "articles", ["slug"], unique=True)
    op.create_table(
        "banners",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("placement", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("subtitle", sa.String(length=250), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("link_url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_banners_placement", "banners", ["placement"])
