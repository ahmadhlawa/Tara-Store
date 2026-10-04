"""Persist minimal anonymous funnel events; history starts with deployment."""

from alembic import op
import sqlalchemy as sa

revision = "0033_analytics_events"
down_revision = "0032_admin_stock_override"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["analytics_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "event_type IN ('add_to_cart', 'checkout_reached', 'order_completed')",
            name="ck_analytics_events_type",
        ),
        sa.UniqueConstraint("dedupe_key", name="uq_analytics_events_dedupe_key"),
    )
    op.create_index(
        "ix_analytics_events_type_time", "analytics_events", ["event_type", "occurred_at"], unique=False
    )
    op.create_index(
        "ix_analytics_events_session_time", "analytics_events", ["session_id", "occurred_at"], unique=False
    )


def downgrade():
    op.drop_index("ix_analytics_events_session_time", table_name="analytics_events")
    op.drop_index("ix_analytics_events_type_time", table_name="analytics_events")
    op.drop_table("analytics_events")
