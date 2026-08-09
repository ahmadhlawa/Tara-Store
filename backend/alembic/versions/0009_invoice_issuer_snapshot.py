"""snapshot immutable invoice issuer identity

Revision ID: 0009_invoice_issuer_snapshot
Revises: 0008_order_activity_triggers
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "0009_invoice_issuer_snapshot"
down_revision: Union[str, None] = "0008_order_activity_triggers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SINGLE_INVOICE_REVISIONS = {
    None,
    "0001_initial",
    "0002_instance_metadata",
    "0003_invoices",
    "0004_import_batches",
}


def _has_replacement_invoice_history() -> bool:
    return op.get_bind().execute(
        sa.text("SELECT 1 FROM invoices GROUP BY order_id HAVING COUNT(*) > 1 LIMIT 1")
    ).first() is not None


def _targets_single_invoice_schema() -> bool:
    return context.get_revision_argument() in _SINGLE_INVOICE_REVISIONS


def upgrade() -> None:
    with op.batch_alter_table("invoices") as batch:
        # No foreign key: this snapshot must survive account deletion.
        batch.add_column(sa.Column("issued_by_admin_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("issued_by_admin_name", sa.String(length=150), nullable=True))
        batch.add_column(sa.Column("issued_by_admin_email", sa.String(length=255), nullable=True))


def downgrade() -> None:
    if _targets_single_invoice_schema() and _has_replacement_invoice_history():
        raise RuntimeError(
            "Cannot downgrade replacement invoice history without deleting invoices."
        )
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("invoices") as batch:
        batch.drop_column("issued_by_admin_email")
        batch.drop_column("issued_by_admin_name")
        batch.drop_column("issued_by_admin_id")
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=ON")
