"""Permit explicit Admin stock corrections without changing other constraints or data."""

from alembic import context, op
import sqlalchemy as sa

revision = "0032_admin_stock_override"
down_revision = "0031_order_lifecycle"
branch_labels = None
depends_on = None

STOCK_CHECKS = (
    ("products", "ck_products_stock_non_negative"),
    ("product_variants", "ck_variants_stock_non_negative"),
)


def _change_sqlite_checks(*, restore: bool) -> None:
    # PRAGMA foreign_keys cannot change inside a transaction. Batch recreation
    # drops the old table, so enforcement would cascade-delete dependent rows or
    # clear historical catalog references. Restore the connection setting even
    # when a batch operation fails.
    foreign_keys = op.get_bind().exec_driver_sql("PRAGMA foreign_keys").scalar_one()
    with op.get_context().autocommit_block():
        op.execute("PRAGMA foreign_keys=OFF")
        try:
            for table, name in STOCK_CHECKS:
                with op.batch_alter_table(table) as batch:
                    if restore:
                        batch.create_check_constraint(name, "stock_quantity >= 0")
                    else:
                        batch.drop_constraint(name, type_="check")
        finally:
            op.execute(f"PRAGMA foreign_keys={int(foreign_keys)}")


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        _change_sqlite_checks(restore=False)
        return
    for table, name in STOCK_CHECKS:
        op.drop_constraint(name, table, type_="check")


def downgrade() -> None:
    # Check BOTH tables before any DDL: MySQL DDL cannot be rolled back. Never
    # silently change business data to make an older schema fit.
    if context.is_offline_mode():
        raise RuntimeError("Cannot restore stock checks offline; preflight negative stock online first.")
    connection = op.get_bind()
    for table, _ in STOCK_CHECKS:
        if connection.execute(sa.text(f"SELECT 1 FROM {table} WHERE stock_quantity < 0 LIMIT 1")).first() is not None:
            raise RuntimeError(f"Cannot restore stock checks: {table} contains negative stock. Correct it explicitly before downgrade.")
    if connection.dialect.name == "sqlite":
        _change_sqlite_checks(restore=True)
        return
    for table, name in STOCK_CHECKS:
        op.create_check_constraint(name, table, "stock_quantity >= 0")
