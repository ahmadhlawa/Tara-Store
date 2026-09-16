"""Add the storefront announcement bar color override."""
from alembic import op
import sqlalchemy as sa

revision = "0024_announcement_color"
down_revision = "0023_category_sibling_order"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("store_settings", sa.Column("theme_announcement_background", sa.String(7), nullable=True))


def downgrade() -> None:
    op.drop_column("store_settings", "theme_announcement_background")
