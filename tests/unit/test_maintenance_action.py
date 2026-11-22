"""The MaintenanceAction role and the statement rules it shares with forge-cli."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import pytest

from fluid_sdk import MaintenanceAction, sql_literal
from fluid_sdk.roles.maintenance_action import (
    _text_problem,
    checked_statements,
    statement_problem,
)
from fluid_sdk.testing import MaintenanceActionTestHarness

TABLE = "fluid.silver.orders"


class ErasePurpose(MaintenanceAction):
    def check(self, options: Mapping[str, Any]) -> Sequence[str]:
        if not isinstance(options.get("purpose"), str):
            return ["options.purpose must be a string"]
        return []

    def statements(self, table: str, options: Mapping[str, Any]) -> Sequence[str]:
        return [f"DELETE FROM {table} WHERE purpose = {sql_literal(options['purpose'])}"]


class TestErasePurpose(MaintenanceActionTestHarness):
    action_class = ErasePurpose
    sample_options = [{"purpose": "marketing"}]
    bad_options = [{"purpose": 42}]


def test_statements_is_abstract_and_check_has_a_default() -> None:
    base = MaintenanceAction()
    assert base.check({}) == ()
    with pytest.raises(NotImplementedError):
        base.statements(TABLE, {})


def test_sql_literal() -> None:
    assert sql_literal("gdpr") == "'gdpr'"
    for bad in ("it's", "a\\b", "${x}", "a--b", "a/*b", "a\nb", "a\x00b"):
        with pytest.raises(ValueError):
            sql_literal(bad)
    with pytest.raises(ValueError):
        sql_literal(5)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "sql",
    [
        f"DELETE FROM {TABLE} WHERE id = 1",
        f"UPDATE {TABLE} SET a = 1 WHERE id = 2",
        f"DELETE FROM {TABLE} WHERE id IN (SELECT id FROM fluid.silver.requests)",
        f"MERGE INTO {TABLE} t USING fluid.silver.src s ON t.id = s.id WHEN MATCHED THEN DELETE",
    ],
)
def test_accepted_statements(sql: str) -> None:
    assert statement_problem(sql, TABLE) == ""


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "   ",
        None,
        5,
        f"DROP TABLE {TABLE}",
        f"DELETE FROM {TABLE}; DELETE FROM {TABLE}",
        f"DELETE FROM {TABLE} WHERE a = '${{x}}'",
        f"DELETE FROM {TABLE} -- all",
        f"DELETE FROM {TABLE} /* all */",
        f"DELETE FROM {TABLE} WHERE a = 'x\\y'",
        f"DELETE FROM {TABLE} WHERE a = 1\x00",
        "DELETE FROM fluid.silver.other WHERE id = 1",
        "DELETE FROM " + "x" * 21000,
    ],
)
def test_refused_statements(sql: Any) -> None:
    assert statement_problem(sql, TABLE) != ""


def test_text_stand_in_is_used_without_sqlglot() -> None:
    assert _text_problem(f"DELETE FROM {TABLE} WHERE a = 'x;y'", TABLE) == ""
    assert _text_problem(f"DELETE FROM {TABLE};", TABLE) == ""
    assert "one statement" in _text_problem(f"DELETE FROM {TABLE}; DELETE FROM {TABLE}", TABLE)
    assert "own table" in _text_problem("DELETE FROM other WHERE a = 1", TABLE)
    assert "DELETE" in _text_problem("SELECT 1", TABLE)


def test_checked_statements() -> None:
    assert checked_statements([f"DELETE FROM {TABLE} WHERE a = 1"], TABLE)
    with pytest.raises(ValueError, match="no statement"):
        checked_statements([], TABLE)
    with pytest.raises(ValueError, match="not a list"):
        checked_statements(f"DELETE FROM {TABLE}", TABLE)
    with pytest.raises(ValueError, match="statement 1"):
        checked_statements([f"DELETE FROM {TABLE} WHERE a = 1", "SELECT 1"], TABLE)
