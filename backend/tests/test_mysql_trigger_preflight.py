from __future__ import annotations

from types import SimpleNamespace

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory


class Result:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one(self) -> object:
        return self.value

    def one(self) -> object:
        return self.value

    def scalars(self) -> "Result":
        return self

    def all(self) -> object:
        return self.value


class Bind:
    def __init__(self, responses: dict[str, object], dialect: str = "mysql") -> None:
        self.dialect = SimpleNamespace(name=dialect)
        self.responses = responses
        self.statements: list[str] = []

    def execute(self, statement: object) -> Result:
        sql = str(statement)
        self.statements.append(sql)
        for fragment, response in self.responses.items():
            if fragment in sql:
                if isinstance(response, Exception):
                    raise response
                return Result(response)
        raise AssertionError(f"unexpected SQL: {sql}")


@pytest.fixture()
def migration():
    return ScriptDirectory.from_config(Config("alembic.ini")).get_revision(
        "0008_order_activity_triggers"
    ).module


def test_preflight_allows_triggers_when_binary_log_trust_is_enabled(migration) -> None:
    bind = Bind({"SELECT DATABASE()": "vista_migr_audit", "@@GLOBAL.log_bin": (1, 1)})

    migration._assert_mysql_trigger_preflight(bind)

    assert not any("SHOW GRANTS" in sql for sql in bind.statements)


def test_preflight_blocks_when_binary_logging_would_reject_trigger(migration) -> None:
    bind = Bind(
        {
            "SELECT DATABASE()": "vista_migr_audit",
            "@@GLOBAL.log_bin": (1, 0),
            "SHOW GRANTS": ["GRANT TRIGGER ON `vista_migr_audit`.* TO `app`@`%`"],
        }
    )

    with pytest.raises(RuntimeError, match="deployment/DBA account"):
        migration._assert_mysql_trigger_preflight(bind)


def test_preflight_allows_readable_combined_global_and_schema_grants(migration) -> None:
    bind = Bind(
        {
            "SELECT DATABASE()": "vista_migr_audit",
            "@@GLOBAL.log_bin": (1, 0),
            "SHOW GRANTS": [
                "GRANT SUPER, PROCESS ON *.* TO `app`@`%`",
                "GRANT SELECT, TRIGGER ON `vista_migr_audit`.* TO `app`@`%`",
            ],
        }
    )

    migration._assert_mysql_trigger_preflight(bind)


def test_preflight_allows_triggers_when_binary_logging_is_disabled(migration) -> None:
    bind = Bind({"SELECT DATABASE()": "vista_migr_audit", "@@GLOBAL.log_bin": (0, 0)})

    migration._assert_mysql_trigger_preflight(bind)


def test_preflight_does_not_need_unreadable_grants_when_trust_proves_safety(migration) -> None:
    bind = Bind({"SELECT DATABASE()": "vista_migr_audit", "@@GLOBAL.log_bin": (1, 1)})

    migration._assert_mysql_trigger_preflight(bind)


def test_preflight_fails_closed_when_grants_are_unreadable(migration) -> None:
    bind = Bind(
        {
            "SELECT DATABASE()": "vista_migr_audit",
            "@@GLOBAL.log_bin": (1, 0),
            "SHOW GRANTS": RuntimeError("access denied"),
        }
    )

    with pytest.raises(RuntimeError, match="could not establish trigger viability"):
        migration._assert_mysql_trigger_preflight(bind)


def test_preflight_is_a_sqlite_no_op(migration) -> None:
    bind = Bind({}, dialect="sqlite")

    migration._assert_mysql_trigger_preflight(bind)

    assert bind.statements == []


def test_preflight_allows_any_schema_when_binary_log_trust_is_enabled(migration) -> None:
    bind = Bind({"SELECT DATABASE()": "commerce_ci", "@@GLOBAL.log_bin": (1, 1)})

    migration._assert_mysql_trigger_preflight(bind)
