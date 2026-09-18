"""Persist progressive admin-login cooldowns across workers and restarts."""

from alembic import op
import sqlalchemy as sa

revision = "0028_admin_login_throttles"
down_revision = "0027_product_show_on_home"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_login_throttles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cooldown_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocked_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "key_hash", name="uq_admin_login_throttle_scope_key"),
    )


def downgrade():
    op.drop_table("admin_login_throttles")
