"""extend order and invoice persistence for the internal workflow

Revision ID: 0005_order_invoice_workflow
Revises: 0004_import_batches
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_order_invoice_workflow"
down_revision: Union[str, None] = "0004_import_batches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_order_unique_constraint() -> bool:
    return any(
        constraint.get("name") == "uq_invoices_order_id"
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints("invoices")
    )


def _has_replacement_invoice_history() -> bool:
    return op.get_bind().execute(
        sa.text("SELECT 1 FROM invoices GROUP BY order_id HAVING COUNT(*) > 1 LIMIT 1")
    ).first() is not None


def upgrade() -> None:
    # SQLite batch migrations replace tables; temporarily disable FK enforcement so an
    # existing invoice can continue to reference its order while that table is rebuilt.
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("orders") as batch:
        batch.alter_column("status", existing_type=sa.String(length=32), server_default="new")
        batch.add_column(
            sa.Column("source", sa.String(length=24), nullable=False, server_default="website")
        )
        batch.add_column(sa.Column("source_note", sa.String(length=250), nullable=True))
        batch.add_column(sa.Column("client_reference", sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(sa.Column("locked_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("completed_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("completed_by_admin_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_orders_completed_by_admin_id", "admin_users", ["completed_by_admin_id"], ["id"], ondelete="SET NULL"
        )

    # The previous UI issued invoices at confirmation. Retain active issued records as
    # completed legacy orders; all other statuses remain completion-eligible workflow states.
    op.execute("UPDATE orders SET status = 'new' WHERE status = 'pending'")
    op.execute("UPDATE orders SET status = 'reviewing' WHERE status IN ('confirmed', 'processing')")
    op.execute("UPDATE orders SET status = 'preparing' WHERE status = 'ready'")
    op.execute("UPDATE orders SET status = 'out_for_delivery' WHERE status = 'shipped'")
    op.execute("UPDATE orders SET status = 'out_for_delivery' WHERE status = 'delivered'")
    # The legacy generic manual method is no longer an accepted API enum. Preserve the
    # financial records by normalizing it to the closest supported offline method.
    op.execute("UPDATE orders SET payment_method = 'bank_transfer' WHERE payment_method = 'manual'")
    op.execute(
        "UPDATE orders SET status = 'completed', is_locked = 1, "
        "completed_at = (SELECT issued_at FROM invoices "
        "WHERE invoices.order_id = orders.id AND invoices.status = 'issued') "
        "WHERE EXISTS (SELECT 1 FROM invoices "
        "WHERE invoices.order_id = orders.id AND invoices.status = 'issued')"
    )
    op.create_index("ix_orders_source", "orders", ["source"], unique=False)
    op.create_index("ix_orders_client_reference", "orders", ["client_reference"], unique=True)
    op.create_index(
        "ix_orders_status_source_created_at", "orders", ["status", "source", "created_at"], unique=False
    )

    with op.batch_alter_table("order_items") as batch:
        batch.add_column(
            sa.Column("item_kind", sa.String(length=16), nullable=False, server_default="catalog")
        )
        batch.add_column(
            sa.Column("original_product_name", sa.String(length=250), nullable=False, server_default="")
        )
        batch.add_column(sa.Column("original_sku", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("original_variant_description", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("manual_description", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column(
                "original_unit_price", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0.00"
            )
        )
    op.execute(
        "UPDATE order_items SET original_product_name = product_name, original_sku = sku, "
        "original_variant_description = variant_description, original_unit_price = unit_price"
    )

    # An order may have several invoices once replacements exist, so the unique
    # constraint on invoices.order_id has to become a plain index. The order of
    # those two steps is not cosmetic on MySQL: 0003 created the table with the
    # foreign key and the unique constraint together, InnoDB backed the foreign
    # key with that unique index instead of building a second one, and MySQL
    # refuses to drop the last index a constraint can use:
    #
    #   (1553, "Cannot drop index 'uq_invoices_order_id':
    #           needed in a foreign key constraint")
    #
    # Creating the replacement index first gives the foreign key somewhere else
    # to rest, after which the unique index can go. SQLite never reached this
    # branch of the problem because batch_alter_table rebuilds the table rather
    # than issuing DROP INDEX, which is why the SQLite suite stayed green while
    # MySQL could not migrate at all.
    op.create_index("ix_invoices_order_id", "invoices", ["order_id"], unique=False)

    has_order_unique_constraint = _has_order_unique_constraint()
    with op.batch_alter_table("invoices") as batch:
        batch.alter_column("status", existing_type=sa.String(length=16), server_default="active")
        if has_order_unique_constraint:
            batch.drop_constraint("uq_invoices_order_id", type_="unique")
        batch.add_column(sa.Column("replacement_invoice_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("payment_status", sa.String(length=24), nullable=False, server_default="unpaid")
        )
        batch.add_column(
            sa.Column("paid_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0.00")
        )
        batch.add_column(
            sa.Column("refunded_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0.00")
        )
        batch.add_column(
            sa.Column("remaining_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0.00")
        )
        batch.add_column(sa.Column("payment_details", sa.Text(), nullable=True))
        batch.add_column(sa.Column("invoice_notes", sa.Text(), nullable=True))
        batch.add_column(sa.Column("source", sa.String(length=24), nullable=True))
        batch.create_foreign_key(
            "fk_invoices_replacement_invoice_id", "invoices", ["replacement_invoice_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_unique_constraint("uq_invoices_replacement_invoice_id", ["replacement_invoice_id"])

    op.execute("UPDATE invoices SET status = 'active' WHERE status = 'issued'")
    op.execute("UPDATE invoices SET payment_method = 'bank_transfer' WHERE payment_method = 'manual'")
    op.execute("UPDATE invoices SET remaining_amount = grand_total")
    op.execute("UPDATE invoices SET source = (SELECT source FROM orders WHERE orders.id = invoices.order_id)")
    with op.batch_alter_table("invoices") as batch:
        batch.alter_column("source", existing_type=sa.String(length=24), nullable=False)
    op.create_index("ix_invoices_source", "invoices", ["source"], unique=False)
    op.create_index(
        "ix_invoices_status_payment_created_at", "invoices", ["status", "payment_status", "created_at"], unique=False
    )

    with op.batch_alter_table("invoice_items") as batch:
        batch.add_column(
            sa.Column("item_kind", sa.String(length=16), nullable=False, server_default="catalog")
        )
        batch.add_column(sa.Column("manual_description", sa.Text(), nullable=True))

    op.create_table(
        "order_activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=True),
        sa.Column("actor_admin_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_admin_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_activities_order_id", "order_activities", ["order_id"], unique=False)
    op.create_index("ix_order_activities_invoice_id", "order_activities", ["invoice_id"], unique=False)
    op.create_index("ix_order_activities_created_at", "order_activities", ["created_at"], unique=False)
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    if _has_replacement_invoice_history():
        raise RuntimeError(
            "Cannot downgrade replacement invoice history without deleting invoices."
        )
    # Dropping the table removes its indexes with it. Dropping them individually
    # first raises MySQL 1553 on ix_order_activities_order_id and
    # ix_order_activities_invoice_id: InnoDB creates an index for each foreign key
    # when the table is built, then discards its own once these equivalent ones
    # appear, leaving them as the only indexes those constraints can use.
    op.drop_table("order_activities")

    with op.batch_alter_table("invoice_items") as batch:
        batch.drop_column("manual_description")
        batch.drop_column("item_kind")

    op.drop_index("ix_invoices_status_payment_created_at", table_name="invoices")
    op.drop_index("ix_invoices_source", table_name="invoices")
    # Mirror image of the upgrade hazard: dropping ix_invoices_order_id while it
    # is the only index behind the foreign key raises MySQL 1553 just the same.
    # Restore the unique constraint first, then remove the plain index. The
    # duplicate check at the top of this function has already established that
    # one invoice per order still holds, so the constraint can be satisfied.
    with op.batch_alter_table("invoices") as batch:
        batch.create_unique_constraint("uq_invoices_order_id", ["order_id"])
    op.drop_index("ix_invoices_order_id", table_name="invoices")
    op.execute("UPDATE invoices SET status = 'issued' WHERE status = 'active'")
    op.execute("UPDATE invoices SET status = 'cancelled' WHERE status = 'replaced'")
    with op.batch_alter_table("invoices") as batch:
        # The foreign key goes before the unique constraint it leans on. InnoDB
        # built an index for the constraint when it was created and dropped that
        # one again once the unique index appeared, so reversing these two raises
        # MySQL 1553 on uq_invoices_replacement_invoice_id.
        batch.drop_constraint("fk_invoices_replacement_invoice_id", type_="foreignkey")
        batch.drop_constraint("uq_invoices_replacement_invoice_id", type_="unique")
        batch.drop_column("invoice_notes")
        batch.drop_column("source")
        batch.drop_column("payment_details")
        batch.drop_column("remaining_amount")
        batch.drop_column("refunded_amount")
        batch.drop_column("paid_amount")
        batch.drop_column("payment_status")
        batch.drop_column("replacement_invoice_id")
        batch.alter_column("status", existing_type=sa.String(length=16), server_default=None)

    with op.batch_alter_table("order_items") as batch:
        batch.drop_column("original_unit_price")
        batch.drop_column("manual_description")
        batch.drop_column("original_variant_description")
        batch.drop_column("original_sku")
        batch.drop_column("original_product_name")
        batch.drop_column("item_kind")

    op.drop_index("ix_orders_status_source_created_at", table_name="orders")
    op.drop_index("ix_orders_client_reference", table_name="orders")
    op.drop_index("ix_orders_source", table_name="orders")
    op.execute("UPDATE orders SET status = 'pending' WHERE status = 'new'")
    op.execute("UPDATE orders SET status = 'confirmed' WHERE status = 'reviewing'")
    op.execute("UPDATE orders SET status = 'ready' WHERE status = 'preparing'")
    op.execute("UPDATE orders SET status = 'shipped' WHERE status = 'out_for_delivery'")
    op.execute("UPDATE orders SET status = 'delivered' WHERE status = 'completed'")
    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint("fk_orders_completed_by_admin_id", type_="foreignkey")
        batch.drop_column("completed_by_admin_id")
        batch.drop_column("completed_at")
        batch.drop_column("locked_at")
        batch.drop_column("is_locked")
        batch.drop_column("client_reference")
        batch.drop_column("source_note")
        batch.drop_column("source")
        batch.alter_column("status", existing_type=sa.String(length=32), server_default=None)
