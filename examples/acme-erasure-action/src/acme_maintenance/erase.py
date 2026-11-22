"""Delete the rows a request table names, before the table is compacted."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from fluid_sdk import MaintenanceAction, sql_literal

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
_TABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\.[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
_OPTIONS = {"requests", "key", "status"}


class EraseRequested(MaintenanceAction):
    """``kind: acme-erase``.

    Options: ``requests`` (``<database>.<table>`` holding the requests, required), ``key`` (the
    column the table and the requests share, default ``customer_id``) and ``status`` (only
    requests with this status count, default ``approved``).
    """

    def check(self, options: Mapping[str, Any]) -> Sequence[str]:
        problems = []
        unknown = sorted(set(options) - _OPTIONS)
        if unknown:
            problems.append(
                f"options reads {', '.join(sorted(_OPTIONS))}, not {', '.join(unknown)}"
            )
        requests = options.get("requests")
        if not isinstance(requests, str) or not _TABLE.match(requests):
            problems.append("options.requests must be a '<database>.<table>' name")
        key = options.get("key", "customer_id")
        if not isinstance(key, str) or not _IDENT.match(key):
            problems.append("options.key must be a column name")
        status = options.get("status", "approved")
        try:
            sql_literal(status)
        except ValueError:
            problems.append("options.status must be a plain string")
        return problems

    def statements(self, table: str, options: Mapping[str, Any]) -> Sequence[str]:
        key = options.get("key", "customer_id")
        status = sql_literal(options.get("status", "approved"))
        return [
            f"DELETE FROM {table} WHERE {key} IN "
            f"(SELECT {key} FROM fluid.{options['requests']} WHERE status = {status})"
        ]
