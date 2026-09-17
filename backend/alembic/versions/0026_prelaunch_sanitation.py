"""Permit the offline prelaunch CLI to delete activity within one transaction.

Normal SQL/ORM activity remains append-only. No data changes or trigger DDL are
performed by the MySQL sanitizer itself; MySQL DDL would implicitly commit.
"""
from alembic import op

revision = "0026_prelaunch_sanitation"
down_revision = "0025_translations"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "mysql":
        op.execute("DROP TRIGGER trg_order_activities_no_delete")
        op.execute(
            "CREATE TRIGGER trg_order_activities_no_delete BEFORE DELETE ON order_activities "
            "FOR EACH ROW BEGIN "
            "IF COALESCE(@tara_sanitize_transactions, 0) <> 1 "
            "OR COALESCE(IS_USED_LOCK(CONCAT('tara-prelaunch:', DATABASE())), 0) <> CONNECTION_ID() "
            "THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'order_activity_immutable'; "
            "END IF; END"
        )


def downgrade():
    if op.get_bind().dialect.name == "mysql":
        op.execute("DROP TRIGGER trg_order_activities_no_delete")
        op.execute(
            "CREATE TRIGGER trg_order_activities_no_delete BEFORE DELETE ON order_activities "
            "FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'order_activity_immutable'"
        )
