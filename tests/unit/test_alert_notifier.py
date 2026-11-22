"""The AlertNotifier role, its rules and the alert_defaults route helper."""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from fluid_sdk import Alert, AlertNotifier, AlertRoute, alert_route, check_alert_route
from fluid_sdk.roles.alert_notifier import (
    connection_problem,
    kwargs_problem,
    notifier_problem,
    sample_alert,
)
from fluid_sdk.testing import AlertNotifierTestHarness


class Teams(AlertNotifier):
    notifier = "acme_alerts.notifiers:TeamsNotifier"
    requirements = ("acme-alerts>=1.2",)
    default_connection = "teams_default"

    def kwargs(self, route: AlertRoute, alert: Alert) -> Mapping[str, Any]:
        return {"title": alert.title, "conn_id": route.connection or self.default_connection}


class TestTeams(AlertNotifierTestHarness):
    notifier_class = Teams
    entry_point_name = "teams"
    sample_routes = [
        AlertRoute(name="oncall", kind="teams", connection="teams_oncall", events=("failure",)),
        AlertRoute(
            name="all",
            kind="teams",
            connection="teams_all",
            events=("failure", "retry", "success", "sla_miss"),
            severity="warning",
        ),
    ]


def test_defaults_match_forge() -> None:
    kind = AlertNotifier()
    assert kind.notifier == "" and kind.requirements == () and kind.requires_connection is True
    assert kind.supports_async is False and kind.default_connection is None
    assert kind.events == frozenset({"failure", "retry", "success", "sla_miss"})
    assert kind.check(AlertRoute(name="x", kind="y")) == ()
    with pytest.raises(NotImplementedError):
        kind.kwargs(AlertRoute(name="x", kind="y"), sample_alert("failure"))


def test_severity_for() -> None:
    assert AlertRoute(name="a", kind="k").severity_for("failure") == "critical"
    assert AlertRoute(name="a", kind="k").severity_for("retry") == "warning"
    assert AlertRoute(name="a", kind="k", severity="error").severity_for("failure") == "error"
    assert AlertRoute(name="a", kind="k", severity="error").severity_for("success") == "info"


@pytest.mark.parametrize(
    "path, ok",
    [
        ("pkg.mod:Cls", True),
        ("pkg:Cls", True),
        ("pkg.mod.Cls", False),
        ("pkg.mod:Cls; import os", False),
        ("pkg..mod:Cls", False),
        ("", False),
    ],
)
def test_notifier_path_rule(path: str, ok: bool) -> None:
    class K:
        notifier = path

        def kwargs(self, route: Any, alert: Any) -> dict:
            return {}

    assert (notifier_problem(K()) == "") is ok


def test_notifier_problem_other_attributes() -> None:
    class Bad(Teams):
        requirements = ("acme'; rm -rf /",)

    assert "requirements" in notifier_problem(Bad())

    class BadEvents(Teams):
        events = frozenset({"failure", "exploded"})

    assert "unknown events" in notifier_problem(BadEvents())

    class BadConn(Teams):
        default_connection = "https://hooks.example.com/abc"

    assert "default_connection" in notifier_problem(BadConn())

    class NoKwargs:
        notifier = "a.b:C"
        kwargs = None

    assert "kwargs" in notifier_problem(NoKwargs())
    assert notifier_problem(Teams()) == ""


def test_kwargs_problem() -> None:
    assert kwargs_problem({"a": [1, 2.0, "x", None, True]}) == ""
    assert "literal" in kwargs_problem({"a": object()})
    assert "finite" in kwargs_problem(float("nan"))
    assert "key" in kwargs_problem({1: "x"})


def test_connection_problem_never_quotes() -> None:
    secret = "abcdef0123456789abcdef0123456789"
    assert "key" in connection_problem(secret)
    assert secret not in connection_problem(secret)
    assert connection_problem("zenduty_oncall") == ""
    assert connection_problem("https://x.example/hook")


def test_alert_route_builds_a_contract_shaped_mapping() -> None:
    route = alert_route(
        "oncall", "pagerduty", connection="pagerduty_oncall", events=["failure", "sla_miss"]
    )
    assert route == {
        "name": "oncall",
        "kind": "pagerduty",
        "events": ["failure", "sla_miss"],
        "connection": "pagerduty_oncall",
    }
    assert alert_route("team", "email", to=["data@acme.example"])["to"] == ["data@acme.example"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "bad name", "kind": "teams"},
        {"name": "ok", "kind": "Teams!"},
        {"name": "ok", "kind": "teams", "events": ["exploded"]},
        {"name": "ok", "kind": "teams", "events": []},
        {"name": "ok", "kind": "teams", "connection": "https://hooks.example/x"},
        {"name": "ok", "kind": "teams", "severity": "fatal"},
        {"name": "ok", "kind": "teams", "to": ["a@b.example"]},
        {"name": "ok", "kind": "email", "options": {"x": 1}},
        {"name": "ok", "kind": "teams", "options": {"api_key": "x"}},
        {"name": "ok", "kind": "teams", "options": {"url": "https://x.example"}},
        {"name": "ok", "kind": "teams", "options": {"t": "{{ x }}"}},
    ],
)
def test_alert_route_refuses_what_forge_refuses(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        alert_route(**kwargs)


def test_alert_route_never_quotes_a_value() -> None:
    secret = "https://hooks.example.com/services/T000/B000/XXXXXXXX"
    with pytest.raises(ValueError) as exc:
        alert_route("ok", "teams", connection=secret)
    assert secret not in str(exc.value)


def test_check_alert_route_unknown_key_and_non_mapping() -> None:
    assert check_alert_route([]) == ["route is not a mapping"]
    assert any("keys a route does not read" in p for p in check_alert_route({"name": "a", "x": 1}))
