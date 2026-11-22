"""The :class:`MaintenanceAction` role: a step of an Iceberg table's maintenance.

forge-cli 0.38.0 lets a contract declare, per Iceberg expose, what keeps the table healthy
(``exposes[].iceberg.maintenance``): compaction, manifests, snapshot expiry, orphan removal and
a package's own actions, such as an erasure of the rows a request names. An action's ``kind``
is the name of a package's entry point in the ``fluid_build.maintenance_actions`` group. That is
this role.

An action returns SQL. forge-cli compiles the statements into the job config the plan binds,
and its Spark runner executes them in order, before compaction. Each statement must be one
``DELETE``, ``UPDATE`` or ``MERGE`` whose target is the action's own table; forge-cli parses
them (Spark SQL, through ``sqlglot``) and ships its own rendering of what it checked.

The role has no ``plan`` / ``apply``: forge-cli calls :meth:`MaintenanceAction.check` and
:meth:`MaintenanceAction.statements` on any object that has them, so this class does not
subclass :class:`fluid_sdk.base.BasePlugin`, and a package may write the same two methods
without an SDK dependency.

Example::

    from fluid_sdk import MaintenanceAction, sql_literal

    class ErasePurpose(MaintenanceAction):
        def check(self, options):
            if not isinstance(options.get("purpose"), str):
                return ["options.purpose must be a string"]
            return []

        def statements(self, table, options):
            return [f"DELETE FROM {table} WHERE purpose = {sql_literal(options['purpose'])}"]

Register via entry-point (the name is the action's ``kind``)::

    [project.entry-points."fluid_build.maintenance_actions"]
    erase-purpose = "acme_pack.maintenance:ErasePurpose"
"""

from __future__ import annotations

from typing import Any, List, Mapping, Sequence, Tuple

#: Entry-point group of maintenance actions (read by name, loaded when an action names the kind).
ACTIONS_GROUP = "fluid_build.maintenance_actions"

#: The writes an action's statement may be.
WRITES: Tuple[str, ...] = ("DELETE", "UPDATE", "MERGE")

#: The longest statement forge-cli accepts.
MAX_STATEMENT_LENGTH = 20_000

# Control characters but tab, newline and carriage return, as forge-cli reads them.
_CONTROL = frozenset(chr(c) for c in range(32) if chr(c) not in "\t\n\r") | {chr(127)}


def normalise_kind(name: str) -> str:
    """The spelling a kind is compared in: lower case, ``-`` for ``_``."""
    return str(name).strip().lower().replace("_", "-")


class MaintenanceAction:
    """Base class of a maintenance action kind: the typed surface of
    ``fluid_build.maintenance_actions``.

    forge-cli builds the entry point's class with no arguments (an instance, or a function that
    returns one, work too) and calls the two methods below.
    """

    #: Canonical role tag (not read by forge-cli; used by tooling and the harness).
    role = "maintenance_action"

    def check(self, options: Mapping[str, Any]) -> Sequence[str]:
        """Problems with the action's ``options``, each a sentence; none when it can run.

        Never quote a value that may be a secret.
        """
        return ()

    def statements(self, table: str, options: Mapping[str, Any]) -> Sequence[str]:
        """The SQL to run on ``table``, named as the runner's catalog holds it
        (``fluid.<database>.<table>``).

        Each one ``DELETE``, ``UPDATE`` or ``MERGE`` with that table as its target, which may
        read others. Called when the job config is compiled (``fluid plan`` and ``fluid apply``):
        the statements are part of the config, which the plan binds, so the same table and
        options must give the same statements. A statement holds no comment and no backslash;
        write an option's value into it with :func:`sql_literal`.
        """
        raise NotImplementedError(f"{type(self).__name__}.statements")


def sql_literal(value: str) -> str:
    """``value`` as a Spark SQL string literal a maintenance statement may carry.

    Spark reads ``''`` as two literals side by side, not as an escaped quote, and a backslash
    escape is read differently by ``sqlglot``, so a value holding ``'`` or a backslash cannot be
    written safely and is refused, as are a control character, ``${`` and a comment marker.

    Raises:
        ValueError: ``value`` cannot be written as such a literal.
    """
    if not isinstance(value, str):
        raise ValueError("a literal is a string")
    if any(ch in _CONTROL or ch in "\t\n\r" for ch in value):
        raise ValueError("a literal holds no control character or line break")
    for mark in ("'", "\\", "${", "--", "/*"):
        if mark in value:
            raise ValueError(f"a literal holds no {mark!r}")
    return f"'{value}'"


def statement_problem(sql: Any, table: str) -> str:
    """Why ``sql`` may not run as an action on ``table``, or ``""``.

    Applies forge-cli's rules for what an action may return. Always checked: a non-empty
    string, at most :data:`MAX_STATEMENT_LENGTH` characters, no ``${...}``, no control
    character, no comment marker and no backslash. When ``sqlglot`` is installed (forge-cli
    depends on it; this SDK does not) the statement is also parsed as Spark SQL and must be
    exactly one ``DELETE``, ``UPDATE`` or ``MERGE`` that writes ``table`` (given catalog
    first, ``fluid.silver.orders``); without it, a text check stands in: one statement that
    starts with one of those words and names the table. forge-cli remains the authority.
    """
    if not isinstance(sql, str) or not sql.strip():
        return "is not a SQL statement"
    if len(sql) > MAX_STATEMENT_LENGTH:
        return f"is longer than {MAX_STATEMENT_LENGTH:,} characters"
    if "${" in sql:
        return "holds a ${...} variable"
    if any(ch in _CONTROL for ch in sql):
        return "holds a control character"
    if "--" in sql or "/*" in sql:
        return (
            "holds '--' or '/*': a statement carries no comment, not even inside a string "
            "(Spark and sqlglot end some comments in different places)"
        )
    if "\\" in sql:
        return (
            "holds a backslash: Spark and sqlglot read some escapes differently, so a literal "
            "is written without one (sql_literal)"
        )
    try:
        import sqlglot  # noqa: F401
    except ImportError:
        return _text_problem(sql, table)
    return _parsed_problem(sql, table)


def _target_parts(expression: Any) -> Tuple[str, ...]:
    from sqlglot import exp

    table = expression.this if not isinstance(expression, exp.Table) else expression
    if not isinstance(table, exp.Table):
        return ()
    return tuple(str(p).lower() for p in (table.catalog, table.db, table.name) if p)


def _parse_one(sql: str) -> Tuple[Any, str]:
    import sqlglot
    from sqlglot import exp
    from sqlglot.errors import SqlglotError

    try:
        parsed = [e for e in sqlglot.parse(sql, read="spark") if e is not None]
    except (SqlglotError, RecursionError):
        return None, "is not SQL Spark reads"
    if len(parsed) != 1:
        return None, "must be exactly one statement"
    (statement,) = parsed
    if not isinstance(statement, (exp.Delete, exp.Update, exp.Merge)):
        return None, f"must be one of {', '.join(WRITES)}"
    return statement, ""


def _parsed_problem(sql: str, table: str) -> str:
    wanted = tuple(table.lower().split("."))
    statement, why = _parse_one(sql)
    if statement is None:
        return why
    if _target_parts(statement) != wanted:
        return f"must write the action's own table, named {table}"
    shipped = statement.sql(dialect="spark", comments=False)
    again, why = _parse_one(shipped)
    unsafe = any(mark in shipped for mark in ("${", "--", "/*", "\\"))
    if again is None or _target_parts(again) != wanted or unsafe:
        return "does not read back as the statement it was checked as"
    return ""


def _text_problem(sql: str, table: str) -> str:
    """The dependency-free stand-in for the parse: one write statement naming ``table``."""
    body = sql.strip()
    quote = ""
    cut = -1
    for index, ch in enumerate(body):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "'\"`":
            quote = ch
        elif ch == ";":
            cut = index
            break
    if cut != -1:
        if body[cut + 1 :].strip():
            return "must be exactly one statement"
        body = body[:cut]
    words = body.split(None, 1)
    if not words or words[0].upper() not in WRITES:
        return f"must be one of {', '.join(WRITES)}"
    if table.lower() not in body.lower():
        return f"must write the action's own table, named {table}"
    return ""


def checked_statements(statements: Any, table: str) -> List[str]:
    """``statements`` as a list, at least one, each passing :func:`statement_problem`.

    Raises:
        ValueError: naming the first problem by its position (the SQL itself is never quoted).
    """
    if isinstance(statements, str) or not isinstance(statements, Sequence):
        raise ValueError("the action's statements are not a list of SQL statements")
    if not statements:
        raise ValueError(
            "the action returned no statement; its statements are compiled into the plan, "
            "so they are the SQL that runs every time"
        )
    for index, sql in enumerate(statements):
        problem = statement_problem(sql, table)
        if problem:
            raise ValueError(f"statement {index} {problem}")
    return list(statements)


__all__ = [
    "ACTIONS_GROUP",
    "MAX_STATEMENT_LENGTH",
    "MaintenanceAction",
    "WRITES",
    "checked_statements",
    "normalise_kind",
    "sql_literal",
    "statement_problem",
]
