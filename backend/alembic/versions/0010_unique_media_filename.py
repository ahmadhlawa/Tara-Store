"""enforce one Media Library asset per original filename

Revision ID: 0010_unique_media_filename
Revises: 0009_invoice_issuer_snapshot
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_unique_media_filename"
down_revision: Union[str, None] = "0009_invoice_issuer_snapshot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_media_assets_original_filename"

# Reported in full, but a corrupt library could hold thousands; the message stays readable.
MAX_REPORTED_DUPLICATES = 20


def _duplicate_filenames() -> list[tuple[str, int, str]]:
    """(filename, count, ids) for every name held by more than one asset.

    Grouped by the database, not by Python, so the comparison is the one the unique
    index will use: binary on SQLite, the column's collation on MySQL — where the
    default is case-insensitive and `Photo.png` and `photo.png` are the same name.
    A preflight done in Python would pass a database the index then rejects.
    """
    bind = op.get_bind()
    ids = sa.func.group_concat(sa.column("id"))
    if bind.dialect.name == "mysql":
        ids = sa.func.group_concat(sa.column("id").cast(sa.String(20)))
    rows = bind.execute(
        sa.select(sa.column("original_filename"), sa.func.count().label("n"), ids.label("ids"))
        .select_from(sa.table("media_assets"))
        .group_by(sa.column("original_filename"))
        .having(sa.func.count() > 1)
        .order_by(sa.column("original_filename"))
    ).all()
    return [(row[0], row[1], str(row[2])) for row in rows]


def upgrade() -> None:
    # Runs before any DDL: a database with duplicates is left exactly as it was, still
    # on the previous revision. Which row to keep is the owner's decision — a migration
    # that deleted, renamed or merged media would destroy catalog references silently.
    duplicates = _duplicate_filenames()
    if duplicates:
        listed = "; ".join(
            f"{name!r} x{count} (ids {ids})"
            for name, count, ids in duplicates[:MAX_REPORTED_DUPLICATES]
        )
        if len(duplicates) > MAX_REPORTED_DUPLICATES:
            listed += f"; and {len(duplicates) - MAX_REPORTED_DUPLICATES} more"
        raise RuntimeError(
            "media_assets.original_filename must be unique before this migration can run. "
            f"Delete or rename the duplicates by hand, then upgrade again: {listed}"
        )

    with op.batch_alter_table("media_assets", schema=None) as batch_op:
        batch_op.create_index(batch_op.f(INDEX_NAME), ["original_filename"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("media_assets", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f(INDEX_NAME))
