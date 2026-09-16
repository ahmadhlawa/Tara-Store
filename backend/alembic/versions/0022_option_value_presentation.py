"""Add option-value presentation metadata and galleries.

Revision ID: 0022_option_value_presentation
Revises: 0021_category_banner_image
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_option_value_presentation"
down_revision = "0021_category_banner_image"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_options",
        sa.Column("drives_presentation", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "product_option_values",
        sa.Column("presentation_title", sa.String(length=200), nullable=True),
    )
    op.create_table(
        "product_option_value_images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "option_value_id",
            sa.Integer(),
            sa.ForeignKey("product_option_values.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("alt_text", sa.String(length=250), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_product_option_value_images_option_value_id",
        "product_option_value_images",
        ["option_value_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_option_value_images_option_value_id",
        table_name="product_option_value_images",
    )
    op.drop_table("product_option_value_images")
    op.drop_column("product_option_values", "presentation_title")
    op.drop_column("product_options", "drives_presentation")
