"""The secret rules the SDK vendors from forge-cli, pinned to forge-cli's own outcomes.

The expected values below were produced by running forge-cli as of forge-cli PR #1063
(released in forge-cli 0.38.0): ``secret_option_key`` and ``_redacted`` of ``fluid_build.alerts.routes``, and
``canonical_statement`` of ``fluid_build.maintenance.statements``. forge-cli is the authority:
a value the SDK passes may still be refused there. Tokens are assembled at run time so no
token-shaped literal sits in the repository.
"""

from __future__ import annotations

import pytest

from fluid_sdk.roles._forge_secrets import looks_like_secret, secret_option_key
from fluid_sdk.roles.alert_notifier import check_alert_route
from fluid_sdk.roles.maintenance_action import _text_problem, statement_problem

KEYS = {
    "private_key": True,
    "signingKey": True,
    "integration_key": True,
    "genie_key": True,
    "hmac_key": True,
    "auth": True,
    "authorization": True,
    "oauth": True,
    "bearer": True,
    "jwt": True,
    "jaas": True,
    "passphrase": True,
    "key": True,
    "pwd": True,
    "sig": True,
    "accesskey": True,
    "conn_str": True,
    "connection_string": True,
    "connection_url": True,
    "max_tokens": False,
    "tokens": False,
    "tokenizer": False,
    "tokenize": False,
    "secretary": False,
    "secretariat": False,
    "api_key": True,
    "apiKey": True,
    "routing-key": True,
    "password2": True,
    "tokenvalue": True,
    "author": False,
    "channel": False,
    "monkey": False,
    "primary_key": False,
    "signature": False,
    "secret_access_key": True,
    "dbpassword": True,
    "webhook_url": False,
    "Token": True,
}


@pytest.mark.parametrize("key, secret", sorted(KEYS.items()))
def test_option_key_matches_forge(key: str, secret: bool) -> None:
    assert secret_option_key(key) is secret


def test_key_table_covers_what_review_found() -> None:
    assert len(KEYS) >= 30
    for refused in ("private_key", "signingKey", "auth", "key", "pwd", "sig", "conn_str"):
        assert KEYS[refused] is True
    for allowed in ("max_tokens", "tokens", "tokenizer", "secretary", "secretariat"):
        assert KEYS[allowed] is False


def _t(prefix: str, body: str, n: int, suffix: str = "") -> str:
    return prefix + body * n + suffix


# (value, forge refuses it). Built at run time.
VALUES = [
    (_t("ghp_", "a", 36), True),
    (_t("github_pat_", "a", 30), True),
    (_t("sk-ant-", "a", 40), True),
    (_t("sk-", "a", 24), True),
    (_t("AKIA", "A", 16), True),
    (_t("ASIA", "A", 16), True),
    (_t("AIza", "a", 35), True),
    (_t("xoxb-1234567890-", "abcdef", 1), True),
    ("Bearer abc123", True),
    ("password=hunter2", True),
    ("api_key: abc", True),
    ("-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----", True),
    ("postgres://u:pw@h/x", True),
    ("https://hooks.slack.com/services/T000/B000/XXXXXXXX", True),
    ("https://events.zenduty.com/integration/abcd1234/generic/", True),
    ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdefghij", True),
    ("ops-alerts", False),
    ("ops-oncall", False),
    ("orders table", False),
    ("channel", False),
]


@pytest.mark.parametrize("value, refused", VALUES)
def test_value_shapes_match_forge(value: str, refused: bool) -> None:
    assert looks_like_secret(value) is refused


@pytest.mark.parametrize("value", [v for v, refused in VALUES if refused])
def test_secret_values_are_refused_in_every_string_a_route_gives(value: str) -> None:
    route = {"name": "ok", "kind": "acme-chat", "connection": "c", "options": {"x": value}}
    for field in ("name", "kind", "connection", "format"):
        problems = check_alert_route({**route, field: value})
        assert problems, field
        assert all(value not in p for p in problems)
    problems = check_alert_route(route)
    assert problems and all(value not in p for p in problems)
    assert not check_alert_route({"name": "ok", "kind": "acme-chat", "connection": "c"})


STATEMENTS = {
    "DELETE FROM fluid.silver.orders WHERE a = 1": True,
    "UPDATE fluid.silver.orders SET a = 1 WHERE b = 2": True,
    "MERGE INTO fluid.silver.orders t USING fluid.silver.src s ON t.id = s.id WHEN MATCHED THEN DELETE": True,
    "WITH r AS (SELECT 1 AS id) DELETE FROM fluid.silver.orders WHERE id IN (SELECT id FROM r)": True,
    "DELETE FROM `fluid`.`silver`.`orders` WHERE a = 1": True,
    "DELETE FROM fluid . silver . orders WHERE a = 1": True,
    "DELETE FROM FLUID.Silver.Orders WHERE a = 1": True,
    "DELETE FROM fluid.silver.orders AS o WHERE a = 1": True,
    "DELETE FROM fluid.silver.orders_archive WHERE a = 1": False,
    "DELETE FROM fluid.silver.other WHERE a IN (SELECT a FROM fluid.silver.orders)": False,
    "DELETE FROM silver.orders WHERE a = 1": False,
    "DELETE FROM `fluid.silver`.orders WHERE a = 1": False,
    "DELETE FROM fluid.silver.orders.x WHERE a = 1": False,
    "DELETE fluid.silver.orders WHERE a = 1": False,
    "DROP TABLE fluid.silver.orders": False,
    "SELECT 1": False,
    "DELETE FROM fluid.silver.orders WHERE a = 1; DELETE FROM fluid.silver.orders WHERE a = 2": False,
    "WITH r AS (SELECT 1) DELETE FROM fluid.silver.other WHERE a IN (SELECT a FROM fluid.silver.orders)": False,
}


@pytest.mark.parametrize("sql, accepted", sorted(STATEMENTS.items()))
def test_statement_target_matches_forge(sql: str, accepted: bool) -> None:
    table = "fluid.silver.orders"
    assert (_text_problem(sql, table) == "") is accepted
    assert (statement_problem(sql, table) == "") is accepted


def test_text_check_without_sqlglot_is_a_text_check(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real = builtins.__import__

    def refuse(name: str, *a: object, **k: object) -> object:
        if name.split(".")[0] == "sqlglot":
            raise ImportError(name)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", refuse)
    assert (
        statement_problem("DELETE FROM fluid.silver.orders WHERE a = 1", "fluid.silver.orders")
        == ""
    )
    assert statement_problem("DELETE FROM fluid.silver.orders_archive", "fluid.silver.orders")
