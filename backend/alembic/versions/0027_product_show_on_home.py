"""Preserve existing homepage products; new products opt in."""
from alembic import op
import sqlalchemy as sa

revision = "0027_product_show_on_home"
down_revision = "0026_prelaunch_sanitation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("show_on_home", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute(sa.text("UPDATE products SET show_on_home = 1"))


def downgrade():
    with op.batch_alter_table("products") as batch:
        batch.drop_column("show_on_home")
