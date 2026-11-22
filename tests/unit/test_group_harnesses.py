"""The new harnesses must fail on a plugin forge-cli would refuse (not only pass good ones)."""

from __future__ import annotations

import argparse
import itertools
from typing import Any, Mapping, Sequence

import pytest

from fluid_sdk import AlertNotifier, AlertRoute, MaintenanceAction
from fluid_sdk.testing import (
    AlertNotifierTestHarness,
    CommandPluginTestHarness,
    MaintenanceActionTestHarness,
)

TABLE = "fluid.silver.orders"


def _fails(harness: Any, test: str) -> None:
    with pytest.raises(AssertionError):
        getattr(harness, test)()


class _Good(AlertNotifier):
    notifier = "acme.notifiers:Teams"

    def kwargs(self, route: AlertRoute, alert: Any) -> Mapping[str, Any]:
        return {"title": alert.title}


ROUTE = AlertRoute(name="r", kind="teams", connection="c", events=("failure",))


def _notifier(cls: type, **routes: Any) -> AlertNotifierTestHarness:
    class H(AlertNotifierTestHarness):
        notifier_class = cls
        sample_routes = routes.get("routes", [ROUTE])
        entry_point_name = routes.get("name", "teams")

    return H()


def test_notifier_path_is_checked() -> None:
    class Bad(_Good):
        notifier = "not a path"

    _fails(_notifier(Bad), "test_is_an_alert_kind_forge_accepts")


def test_builtin_name_is_reserved() -> None:
    _fails(_notifier(_Good, name="Slack"), "test_entry_point_name_is_a_valid_new_kind")


def test_requirement_is_checked() -> None:
    class Bad(_Good):
        requirements = ('acme"',)

    _fails(_notifier(Bad), "test_is_an_alert_kind_forge_accepts")


def test_kwargs_must_be_literals_deterministic_and_not_reserved() -> None:
    class NotLiteral(_Good):
        def kwargs(self, route: Any, alert: Any) -> Mapping[str, Any]:
            return {"x": object()}

    class Reserved(_Good):
        def kwargs(self, route: Any, alert: Any) -> Mapping[str, Any]:
            return {"context": "x"}

    class BadKey(_Good):
        def kwargs(self, route: Any, alert: Any) -> Mapping[str, Any]:
            return {"class": "x"}

    counter = itertools.count()

    class Flaky(_Good):
        def kwargs(self, route: Any, alert: Any) -> Mapping[str, Any]:
            return {"n": next(counter)}

    for cls in (NotLiteral, Reserved, BadKey, Flaky):
        _fails(_notifier(cls), "test_kwargs_are_deterministic_literals_for_every_event")


def test_route_needs_a_connection_and_a_served_event() -> None:
    no_conn = AlertRoute(name="r", kind="teams", events=("failure",))
    _fails(
        _notifier(_Good, routes=[no_conn]), "test_routes_are_served_events_and_name_a_connection"
    )

    class OnlyFailure(_Good):
        events = frozenset({"failure"})

    retry = AlertRoute(name="r", kind="teams", connection="c", events=("retry",))
    _fails(
        _notifier(OnlyFailure, routes=[retry]),
        "test_routes_are_served_events_and_name_a_connection",
    )


def test_no_sample_routes_is_refused() -> None:
    _fails(_notifier(_Good, routes=[]), "test_sample_routes_present")


class _Action(MaintenanceAction):
    def statements(self, table: str, options: Mapping[str, Any]) -> Sequence[str]:
        return [f"DELETE FROM {table} WHERE a = 1"]


def _maintenance(cls: type, **kw: Any) -> MaintenanceActionTestHarness:
    class H(MaintenanceActionTestHarness):
        action_class = cls
        sample_options = kw.get("ok", [{"a": 1}])
        bad_options = kw.get("bad", [])

    return H()


def test_statements_must_be_writes_on_the_own_table() -> None:
    class Drop(_Action):
        def statements(self, table: str, options: Mapping[str, Any]) -> Sequence[str]:
            return [f"DROP TABLE {table}"]

    class Other(_Action):
        def statements(self, table: str, options: Mapping[str, Any]) -> Sequence[str]:
            return ["DELETE FROM fluid.silver.other WHERE a = 1"]

    class Empty(_Action):
        def statements(self, table: str, options: Mapping[str, Any]) -> Sequence[str]:
            return []

    class Bare(_Action):
        def statements(self, table: str, options: Mapping[str, Any]) -> Sequence[str]:
            return f"DELETE FROM {table} WHERE a = 1"  # type: ignore[return-value]

    for cls in (Drop, Other, Empty, Bare):
        _fails(_maintenance(cls), "test_statements_are_a_list_of_accepted_writes")


def test_statements_must_be_deterministic() -> None:
    counter = itertools.count()

    class Flaky(_Action):
        def statements(self, table: str, options: Mapping[str, Any]) -> Sequence[str]:
            return [f"DELETE FROM {table} WHERE a = {next(counter)}"]

    _fails(_maintenance(Flaky), "test_statements_are_deterministic")


def test_check_must_refuse_and_not_echo() -> None:
    class Lax(_Action):
        pass

    _fails(
        _maintenance(Lax, bad=[{"purpose": "marketing-secret"}]),
        "test_check_refuses_bad_options_without_echoing_values",
    )

    class Echo(_Action):
        def check(self, options: Mapping[str, Any]) -> Sequence[str]:
            return [f"purpose {options['purpose']} is not allowed"]

    _fails(
        _maintenance(Echo, bad=[{"purpose": "marketing-secret"}]),
        "test_check_refuses_bad_options_without_echoing_values",
    )


def test_statements_must_not_modify_options() -> None:
    class Mutates(_Action):
        def statements(self, table: str, options: Any) -> Sequence[str]:
            options["seen"] = True
            return super().statements(table, options)

    _fails(_maintenance(Mutates), "test_statements_do_not_modify_the_options")


def _command(entry: Any, **kw: Any) -> CommandPluginTestHarness:
    class H(CommandPluginTestHarness):
        command_entry_point = entry
        reserved_command_names = kw.get("reserved", ())

    return H()


def test_a_class_is_not_an_entry_point() -> None:
    from fluid_sdk import CommandPlugin

    class C(CommandPlugin):
        name = "c"

    _fails(_command(C), "test_entry_point_is_callable_not_a_class")


def test_register_must_add_a_command_quietly_with_a_func() -> None:
    def adds_nothing(sp: Any) -> None:
        return None

    def prints(sp: Any) -> None:
        print("loading")
        sp.add_parser("noisy").set_defaults(func=lambda args: 0)

    def no_func(sp: Any) -> None:
        sp.add_parser("nofunc")

    def bad_arity(sp: Any) -> None:
        sp.add_parser("arity").set_defaults(func=lambda: 0)

    def reserved(sp: Any) -> None:
        sp.add_parser("plan").set_defaults(func=lambda args: 0)

    _fails(_command(adds_nothing), "test_registering_adds_a_command_and_nothing_else")
    _fails(_command(prints), "test_registering_adds_a_command_and_nothing_else")
    _fails(_command(no_func), "test_every_command_has_a_runnable_func")
    _fails(_command(bad_arity), "test_every_command_has_a_runnable_func")
    _fails(_command(reserved, reserved=("plan",)), "test_command_names_are_plain_and_not_reserved")


def test_register_must_not_touch_the_environment() -> None:
    import os

    def sets_env(sp: Any) -> None:
        os.environ["ACME_PLUGIN_LOADED"] = "1"
        sp.add_parser("envy").set_defaults(func=lambda args: 0)

    try:
        _fails(_command(sets_env), "test_registering_adds_a_command_and_nothing_else")
    finally:
        os.environ.pop("ACME_PLUGIN_LOADED", None)


def test_argparse_import_is_used() -> None:
    assert argparse.ArgumentParser
