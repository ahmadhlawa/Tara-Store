"""enforce one active invoice per order without removing replacement history

Revision ID: 0006_active_invoice_marker
Revises: 0005_order_invoice_workflow
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "0006_active_invoice_marker"
down_revision: Union[str, None] = "0005_order_invoice_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SINGLE_INVOICE_REVISIONS = {None, "0001_initial", "0002_instance_metadata", "0003_invoices", "0004_import_batches"}


def _blocks_legacy_downgrade() -> bool:
    if context.get_revision_argument() not in _SINGLE_INVOICE_REVISIONS:
        return False
    return op.get_bind().execute(
        sa.text("SELECT 1 FROM invoices GROUP BY order_id HAVING COUNT(*) > 1 LIMIT 1")
    ).first() is not None


def _has_multiple_active_invoices() -> bool:
    return op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM invoices WHERE status = 'active' "
            "GROUP BY order_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first() is not None


def upgrade() -> None:
    if _has_multiple_active_invoices():
        raise RuntimeError("Cannot enforce one active invoice while duplicate active invoices exist.")
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("invoices") as batch:
        batch.add_column(
            sa.Column("active_invoice_marker", sa.String(length=16), nullable=True, server_default="active")
        )
    op.execute(
        "UPDATE invoices SET active_invoice_marker = "
        "CASE WHEN status = 'active' THEN 'active' ELSE NULL END"
    )
    with op.batch_alter_table("invoices") as batch:
        batch.create_check_constraint(
            "ck_invoices_active_invoice_marker",
            "(status = 'active' AND active_invoice_marker IS NOT NULL "
            "AND active_invoice_marker = 'active') "
            "OR (status <> 'active' AND active_invoice_marker IS NULL)",
        )
        batch.create_unique_constraint(
            "uq_invoices_order_active_marker", ["order_id", "active_invoice_marker"]
        )
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    if _blocks_legacy_downgrade():
        raise RuntimeError("Cannot downgrade replacement invoice history without deleting invoices.")
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("invoices") as batch:
        # order_id is the leftmost column of this constraint and carries a foreign
        # key, so MySQL would refuse the drop if this were the only index it could
        # use. It is safe because 0005 leaves ix_invoices_order_id in place until
        # its own downgrade runs, which is after this one. Anything that moves that
        # index drop earlier brings back MySQL error 1553 here.
        batch.drop_constraint("uq_invoices_order_active_marker", type_="unique")
        batch.drop_constraint("ck_invoices_active_invoice_marker", type_="check")
        batch.drop_column("active_invoice_marker")
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=ON")
