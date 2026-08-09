"""enforce append-only order activity at the database layer

Revision ID: 0008_order_activity_triggers
Revises: 0007_active_marker_null_safe

The identifier is kept under 32 characters to fit alembic_version.version_num;
see 0007 for what happens on MySQL when it does not.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "0008_order_activity_triggers"
down_revision: Union[str, None] = "0007_active_marker_null_safe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SINGLE_INVOICE_REVISIONS = {None, "0001_initial", "0002_instance_metadata", "0003_invoices", "0004_import_batches"}


def _blocks_legacy_downgrade() -> bool:
    if context.get_revision_argument() not in _SINGLE_INVOICE_REVISIONS:
        return False
    return op.get_bind().execute(
        sa.text("SELECT 1 FROM invoices GROUP BY order_id HAVING COUNT(*) > 1 LIMIT 1")
    ).first() is not None

_UPDATE_TRIGGER = "trg_order_activities_no_update"
_DELETE_TRIGGER = "trg_order_activities_no_delete"
def _trigger_deployment_error(detail: str) -> RuntimeError:
    return RuntimeError(
        "MySQL trigger deployment preflight failed: "
        f"{detail}. Run migrations through a sufficiently privileged deployment/DBA "
        "account, or have the host temporarily enable "
        "log_bin_trust_function_creators=1; do not apply revision 0008 until then."
    )


def _has_privilege(grants: list[str], privilege: str, schema: str) -> bool:
    for grant in grants:
        normalized = grant.upper().replace("`", "")
        privileges, _, scope = normalized.partition(" ON ")
        if privileges == "GRANT ALL PRIVILEGES" and scope.startswith("*.*"):
            return True
        if privilege == "SUPER" and "SUPER" in privileges and scope.startswith("*.*"):
            return True
        if privilege == "TRIGGER" and (
            "TRIGGER" in privileges
            and (scope.startswith("*.*") or scope.startswith(f"{schema.upper()}.*"))
        ):
            return True
    return False


def _assert_mysql_trigger_preflight(bind: sa.Connection) -> None:
    """Fail before either trigger DDL if this server/account cannot create them."""
    if bind.dialect.name != "mysql":
        return

    schema = bind.execute(sa.text("SELECT DATABASE()")).scalar_one()
    try:
        log_bin, trust_creators = bind.execute(
            sa.text("SELECT @@GLOBAL.log_bin, @@GLOBAL.log_bin_trust_function_creators")
        ).one()
    except Exception as exc:
        raise _trigger_deployment_error(
            "could not read binary-log prerequisites to establish trigger viability safely"
        ) from exc

    if not log_bin or trust_creators:
        return

    try:
        grants = [str(grant) for grant in bind.execute(sa.text("SHOW GRANTS")).scalars().all()]
    except Exception as exc:
        raise _trigger_deployment_error("could not establish trigger viability because effective grants are unreadable") from exc

    if not _has_privilege(grants, "TRIGGER", schema):
        raise _trigger_deployment_error("the migration account lacks TRIGGER privilege on the selected schema")
    if not _has_privilege(grants, "SUPER", schema):
        raise _trigger_deployment_error(
            "binary logging is enabled, trust is disabled, and the migration account lacks SUPER"
        )


def _create_trigger(name: str, operation: str) -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute(
            f"CREATE TRIGGER {name} BEFORE {operation} ON order_activities "
            "FOR EACH ROW BEGIN SELECT RAISE(ABORT, 'order_activity_immutable'); END"
        )
    elif dialect == "mysql":
        op.execute(
            f"CREATE TRIGGER {name} BEFORE {operation} ON order_activities "
            "FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'order_activity_immutable'"
        )
    else:
        raise RuntimeError(f"Order activity triggers are not implemented for {dialect}.")


def _drop_trigger(name: str) -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {name}")


def upgrade() -> None:
    _assert_mysql_trigger_preflight(op.get_bind())
    _create_trigger(_UPDATE_TRIGGER, "UPDATE")
    _create_trigger(_DELETE_TRIGGER, "DELETE")


def downgrade() -> None:
    if _blocks_legacy_downgrade():
        raise RuntimeError("Cannot downgrade replacement invoice history without deleting invoices.")
    _drop_trigger(_DELETE_TRIGGER)
    _drop_trigger(_UPDATE_TRIGGER)
