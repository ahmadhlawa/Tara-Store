"""make active-invoice marker validation NULL-safe

Revision ID: 0007_active_marker_null_safe
Revises: 0006_active_invoice_marker

The identifier is kept under 32 characters because Alembic stores it in
alembic_version.version_num, which is VARCHAR(32); a longer one is accepted by
SQLite and rejected by MySQL with error 1406 after the DDL has already run.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "0007_active_marker_null_safe"
down_revision: Union[str, None] = "0006_active_invoice_marker"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SINGLE_INVOICE_REVISIONS = {None, "0001_initial", "0002_instance_metadata", "0003_invoices", "0004_import_batches"}


def _blocks_legacy_downgrade() -> bool:
    if context.get_revision_argument() not in _SINGLE_INVOICE_REVISIONS:
        return False
    return op.get_bind().execute(
        sa.text("SELECT 1 FROM invoices GROUP BY order_id HAVING COUNT(*) > 1 LIMIT 1")
    ).first() is not None

_CHECK = (
    "(status = 'active' AND active_invoice_marker IS NOT NULL "
    "AND active_invoice_marker = 'active') "
    "OR (status <> 'active' AND active_invoice_marker IS NULL)"
)


def _has_multiple_active_invoices() -> bool:
    return op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM invoices WHERE status = 'active' "
            "GROUP BY order_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first() is not None


def upgrade() -> None:
    if _has_multiple_active_invoices():
        raise RuntimeError("Cannot make active-invoice validation NULL-safe with duplicate active invoices.")
    op.execute(
        "UPDATE invoices SET active_invoice_marker = 'active' "
        "WHERE status = 'active' AND active_invoice_marker IS NULL"
    )
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("invoices") as batch:
        batch.drop_constraint("ck_invoices_active_invoice_marker", type_="check")
        batch.alter_column(
            "active_invoice_marker", existing_type=sa.String(length=16), server_default="active"
        )
        batch.create_check_constraint("ck_invoices_active_invoice_marker", _CHECK)
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    if _blocks_legacy_downgrade():
        raise RuntimeError("Cannot downgrade replacement invoice history without deleting invoices.")
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("invoices") as batch:
        batch.drop_constraint("ck_invoices_active_invoice_marker", type_="check")
        batch.alter_column(
            "active_invoice_marker", existing_type=sa.String(length=16), server_default=None
        )
        batch.create_check_constraint(
            "ck_invoices_active_invoice_marker",
            "(status = 'active' AND active_invoice_marker = 'active') "
            "OR (status <> 'active' AND active_invoice_marker IS NULL)",
        )
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=ON")
