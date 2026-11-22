from __future__ import annotations

import pytest
from acme_alerts import ChatNotifier, default_routes

from fluid_sdk import AlertRoute, check_alert_route
from fluid_sdk.roles.alert_notifier import sample_alert
from fluid_sdk.testing import AlertNotifierTestHarness


class TestChatNotifier(AlertNotifierTestHarness):
    notifier_class = ChatNotifier
    entry_point_name = "acme-chat"
    sample_routes = [
        AlertRoute(
            name="chat",
            kind="acme-chat",
            connection="acme_chat_team",
            events=("failure", "retry", "success", "sla_miss"),
            options={"channel": "data-team"},
        ),
        AlertRoute(name="plain", kind="acme-chat"),  # falls back to the default connection
    ]


def test_kwargs_use_the_connection_and_channel() -> None:
    route = AlertRoute(
        name="chat", kind="acme-chat", connection="acme_chat_team", options={"channel": "x1"}
    )
    kwargs = dict(ChatNotifier().kwargs(route, sample_alert("failure")))
    assert kwargs["chat_conn_id"] == "acme_chat_team" and kwargs["channel"] == "x1"
    assert "{{ ti.task_id }}" in kwargs["message"]  # Jinja for Airflow to render


def test_default_connection_when_a_route_names_none() -> None:
    kwargs = ChatNotifier().kwargs(AlertRoute(name="p", kind="acme-chat"), sample_alert("success"))
    assert kwargs["chat_conn_id"] == "acme_chat_default"


@pytest.mark.parametrize("options", [{"channel": "Bad Name"}, {"channel": 3}, {"x": 1}])
def test_check_refuses_bad_options(options: dict) -> None:
    route = AlertRoute(name="p", kind="acme-chat", connection="c", options=options)
    assert ChatNotifier().check(route)


def test_default_routes_have_the_shape_forge_reads() -> None:
    routes = default_routes()
    assert [r["name"] for r in routes] == ["org-oncall"]
    for route in routes:
        assert check_alert_route(route) == []
