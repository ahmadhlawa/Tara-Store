"""Stored translations; migration never contacts a translation provider."""
from alembic import op
import sqlalchemy as sa

revision = "0025_translations"
down_revision = "0024_announcement_color"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("translations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("field", sa.String(100), nullable=False),
        sa.Column("locale", sa.String(8), nullable=False),
        sa.Column("translated_text", sa.Text(), nullable=True),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("retry_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("entity_type", "entity_id", "field", "locale", name="uq_translation_field_locale"))
    op.create_index("ix_translations_status", "translations", ["status"])


def downgrade():
    op.drop_table("translations")
