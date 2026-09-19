"""Add privacy-preserving first-party storefront analytics."""

from alembic import op
import sqlalchemy as sa

revision = "0029_storefront_analytics"
down_revision = "0028_admin_login_throttles"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analytics_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_token_hash", sa.String(length=64), nullable=False),
        sa.Column("visitor_hash", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("raw_city", sa.String(length=120), nullable=True),
        sa.Column("raw_region", sa.String(length=120), nullable=True),
        sa.Column("location_label", sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token_hash", name="uq_analytics_sessions_token_hash"),
    )
    op.create_index("ix_analytics_sessions_started_at", "analytics_sessions", ["started_at"], unique=False)
    op.create_index(
        "ix_analytics_sessions_visitor_last_activity",
        "analytics_sessions",
        ["visitor_hash", "last_activity_at"],
        unique=False,
    )
    op.create_index(
        "ix_analytics_sessions_location_started",
        "analytics_sessions",
        ["location_label", "started_at"],
        unique=False,
    )

    op.create_table(
        "analytics_product_views",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("product_slug_snapshot", sa.String(length=260), nullable=False),
        sa.Column("product_name_snapshot", sa.String(length=250), nullable=False),
        sa.Column("viewed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["analytics_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_product_views_viewed_at", "analytics_product_views", ["viewed_at"], unique=False)
    op.create_index(
        "ix_analytics_product_views_product_viewed",
        "analytics_product_views",
        ["product_id", "viewed_at"],
        unique=False,
    )
    op.create_index(
        "ix_analytics_product_views_session_product_viewed",
        "analytics_product_views",
        ["session_id", "product_id", "viewed_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_analytics_product_views_session_product_viewed", table_name="analytics_product_views")
    op.drop_index("ix_analytics_product_views_product_viewed", table_name="analytics_product_views")
    op.drop_index("ix_analytics_product_views_viewed_at", table_name="analytics_product_views")
    op.drop_table("analytics_product_views")
    op.drop_index("ix_analytics_sessions_location_started", table_name="analytics_sessions")
    op.drop_index("ix_analytics_sessions_visitor_last_activity", table_name="analytics_sessions")
    op.drop_index("ix_analytics_sessions_started_at", table_name="analytics_sessions")
    op.drop_table("analytics_sessions")
