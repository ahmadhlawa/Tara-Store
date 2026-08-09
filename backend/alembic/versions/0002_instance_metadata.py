"""instance metadata

Records which template release and profile an instance was initialized from. Single row,
no tenancy: nothing else in the schema references it.

Revision ID: 0002_instance_metadata
Revises: 0001_initial
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_instance_metadata"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "instance_metadata",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instance_slug", sa.String(length=40), nullable=False),
        sa.Column("template_version", sa.String(length=32), nullable=False),
        sa.Column("profile_schema_version", sa.Integer(), nullable=False),
        sa.Column("profile_hash", sa.String(length=64), nullable=False),
        sa.Column("enabled_features", sa.JSON(), nullable=False),
        sa.Column("initialized_at", sa.DateTime(), nullable=False),
        sa.Column("last_bootstrap_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_instance_metadata_instance_slug"),
        "instance_metadata",
        ["instance_slug"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_instance_metadata_instance_slug"), table_name="instance_metadata")
    op.drop_table("instance_metadata")
