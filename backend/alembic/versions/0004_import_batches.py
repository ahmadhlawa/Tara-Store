"""import batch ownership tracking

Two tables that record which rows a named dataset import created, so the same rows can
be removed again without touching owner-created content. No existing table is altered:
nothing in the commerce schema gains an import-origin column.

Column types are chosen to be identical on SQLite and MySQL 8 (String, Integer,
DateTime), matching the convention set by 0001.

Revision ID: 0004_import_batches
Revises: 0003_invoices
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_import_batches"
down_revision: Union[str, None] = "0003_invoices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_key", sa.String(length=64), nullable=False),
        sa.Column("source_label", sa.String(length=250), nullable=False),
        sa.Column("dataset_hash", sa.String(length=64), nullable=False),
        sa.Column("media_prefix", sa.String(length=200), nullable=False),
        sa.Column("seed_count", sa.Integer(), nullable=False),
        sa.Column("last_seeded_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_import_batches_batch_key"), "import_batches", ["batch_key"], unique=True
    )

    op.create_table(
        "import_batch_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("natural_key", sa.String(length=200), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id", "entity_type", "entity_id", name="uq_import_batch_record_entity"
        ),
    )
    op.create_index(
        op.f("ix_import_batch_records_batch_id"), "import_batch_records", ["batch_id"]
    )
    op.create_index(
        op.f("ix_import_batch_records_entity_type"), "import_batch_records", ["entity_type"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_import_batch_records_entity_type"), table_name="import_batch_records")
    op.drop_index(op.f("ix_import_batch_records_batch_id"), table_name="import_batch_records")
    op.drop_table("import_batch_records")
    op.drop_index(op.f("ix_import_batches_batch_key"), table_name="import_batches")
    op.drop_table("import_batches")
