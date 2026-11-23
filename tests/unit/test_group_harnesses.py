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

    _fails(
        _command(adds_nothing),
        "test_registering_adds_a_command_quietly_and_leaves_the_process_alone",
    )
    _fails(_command(prints), "test_registering_adds_a_command_quietly_and_leaves_the_process_alone")
    _fails(_command(no_func), "test_every_command_has_a_runnable_func")
    _fails(_command(bad_arity), "test_every_command_has_a_runnable_func")
    _fails(_command(reserved, reserved=("plan",)), "test_command_names_are_not_reserved")


def test_register_must_not_touch_the_environment() -> None:
    import os

    def sets_env(sp: Any) -> None:
        os.environ["ACME_PLUGIN_LOADED"] = "1"
        sp.add_parser("envy").set_defaults(func=lambda args: 0)

    try:
        _fails(
            _command(sets_env),
            "test_registering_adds_a_command_quietly_and_leaves_the_process_alone",
        )
    finally:
        os.environ.pop("ACME_PLUGIN_LOADED", None)


def test_argparse_import_is_used() -> None:
    assert argparse.ArgumentParser


# ── a plain object, a function factory, a missing check ──────────────────────


class _PlainKind:
    notifier = "acme.notifiers:Teams"

    def kwargs(self, route: Any, alert: Any) -> Mapping[str, Any]:
        return {"title": alert.title}


def _skipped(harness: Any, test: str) -> None:
    import unittest

    with pytest.raises(unittest.SkipTest):
        getattr(harness, test)()


def test_a_plain_kind_skips_the_subclass_test_and_needs_no_check() -> None:
    h = _notifier(_PlainKind)
    _skipped(h, "test_subclasses_alert_notifier_when_it_can")
    for name in dir(h):
        if name.startswith("test_") and name != "test_subclasses_alert_notifier_when_it_can":
            getattr(h, name)()


def test_a_function_factory_builds_the_kind_as_forge_does() -> None:
    def factory() -> Any:
        return _PlainKind()

    h = _notifier(factory)
    assert isinstance(h.get_notifier(), _PlainKind)
    h.test_is_an_alert_kind_forge_accepts()

    class H(MaintenanceActionTestHarness):
        action_class = lambda: _Action()  # noqa: E731 - a function, not a method
        sample_options = [{"a": 1}]

    assert isinstance(H().get_action(), _Action)
    H().test_statements_are_a_list_of_accepted_writes()


def test_a_plain_action_without_check_skips_and_passes() -> None:
    class Plain:
        def statements(self, table: str, options: Mapping[str, Any]) -> Sequence[str]:
            return [f"DELETE FROM {table} WHERE a = 1"]

    h = _maintenance(Plain)
    _skipped(h, "test_subclasses_maintenance_action_when_it_can")
    for name in dir(h):
        if name.startswith("test_") and name != "test_subclasses_maintenance_action_when_it_can":
            getattr(h, name)()


def test_action_check_must_return_a_list() -> None:
    class Str(_Action):
        def check(self, options: Mapping[str, Any]) -> Any:
            return "a problem"

    _fails(_maintenance(Str), "test_check_returns_a_list_of_sentences_and_does_not_raise")


def test_a_kind_whose_check_refuses_every_sample_route_fails() -> None:
    class Refuses(_Good):
        def check(self, route: AlertRoute) -> Sequence[str]:
            return ["no"]

    _fails(_notifier(Refuses), "test_sample_routes_pass_check")


def test_assertions_name_a_position_not_a_route_value() -> None:
    secret = "tok_do_not_echo"
    odd = AlertRoute(name=secret, kind="teams", events=("failure",))
    with pytest.raises(AssertionError) as exc:
        _notifier(_Good, routes=[odd]).test_routes_are_served_events_and_name_a_connection()
    assert "sample_routes[0]" in str(exc.value) and secret not in str(exc.value)


def test_built_in_only_keys_are_exercised() -> None:
    bad = AlertRoute(
        name="r", kind="teams", connection="c", events=("failure",), to=("a@b.example",)
    )
    _fails(_notifier(_Good, routes=[bad]), "test_sample_routes_have_the_shape_forge_reads")
    fmt = AlertRoute(name="r", kind="teams", connection="c", events=("failure",), format="zenduty")
    _fails(_notifier(_Good, routes=[fmt]), "test_sample_routes_have_the_shape_forge_reads")


def test_no_sqlglot_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real = builtins.__import__

    def refuse(name: str, *a: Any, **k: Any) -> Any:
        if name.split(".")[0] == "sqlglot":
            raise ImportError(name)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", refuse)
    with pytest.warns(UserWarning, match="sqlglot"):
        _maintenance(_Action).test_statements_are_a_list_of_accepted_writes()


def test_the_text_check_rejects_a_similar_table_name() -> None:
    class Archive(_Action):
        def statements(self, table: str, options: Mapping[str, Any]) -> Sequence[str]:
            return [f"DELETE FROM {table}_archive WHERE a = 1"]

    _fails(_maintenance(Archive), "test_statements_are_a_list_of_accepted_writes")


# ── command plugin ───────────────────────────────────────────────────────────


def test_command_names_have_no_pattern_beyond_not_reserved() -> None:
    def odd_name(sp: Any) -> None:
        sp.add_parser("Acme_Tool.v2").set_defaults(func=lambda args: 0)

    _command(odd_name).test_command_names_are_not_reserved()


def test_arity_matches_how_forge_calls_func() -> None:
    def three_with_default(sp: Any) -> None:
        def run(args: Any, logger: Any, extra: Any = None) -> int:
            return 0

        sp.add_parser("three").set_defaults(func=run)

    def three_required(sp: Any) -> None:
        def run(args: Any, logger: Any, extra: Any) -> int:
            return 0

        sp.add_parser("three").set_defaults(func=run)

    def varargs(sp: Any) -> None:
        sp.add_parser("va").set_defaults(func=lambda *a: 0)

    _command(three_with_default).test_every_command_has_a_runnable_func()
    _command(varargs).test_every_command_has_a_runnable_func()
    _fails(_command(three_required), "test_every_command_has_a_runnable_func")


def test_a_failing_register_still_restores_the_process() -> None:
    import os

    cwd = os.getcwd()

    def breaks(sp: Any) -> None:
        os.environ["ACME_LEAK"] = "1"
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        _command(breaks)._register()
    assert "ACME_LEAK" not in os.environ and os.getcwd() == cwd


def test_sample_alert_follows_forge_wording() -> None:
    from fluid_sdk.roles.alert_notifier import sample_alert

    sla = sample_alert("sla_miss", sla_seconds=14400)
    assert sla.title.endswith("missed its SLA of 4h") and "task_list" in sla.text
    assert sample_alert("failure").sla_seconds == 3600
    assert "ti.log_url" in sample_alert("retry").text


def test_an_instance_attribute_set_in_setup_method_is_seen() -> None:
    class H(AlertNotifierTestHarness):
        sample_routes = [ROUTE]

        def setup_method(self) -> None:
            self.notifier_class = _Good

    h = H()
    h.setup_method()
    assert isinstance(h.get_notifier(), _Good)

    class M(MaintenanceActionTestHarness):
        sample_options = [{"a": 1}]

        def setup_method(self) -> None:
            self.action_class = _Action

    m = M()
    m.setup_method()
    assert isinstance(m.get_action(), _Action)


def test_an_entry_point_in_main_skips_the_import_test() -> None:
    def in_main(sp: Any) -> None:
        sp.add_parser("m").set_defaults(func=lambda args: 0)

    in_main.__module__ = "__main__"
    _skipped(_command(in_main), "test_importing_the_module_has_no_side_effects")


# --- a kind's default_connection satisfies requires_connection (forge-cli 0.39.0) ---------


def test_a_route_without_a_connection_needs_a_kind_with_a_default() -> None:
    bare = AlertRoute(name="r", kind="teams", events=("failure",))

    # requires_connection is True and there is no default: the route must name one.
    _fails(_notifier(_Good, routes=[bare]), "test_routes_are_served_events_and_name_a_connection")

    class WithDefault(_Good):
        default_connection = "teams_default"

        def kwargs(self, route: AlertRoute, alert: Any) -> Mapping[str, Any]:
            assert route.connection == "teams_default"
            return {"title": alert.title, "conn": route.connection}

    for test in (
        "test_routes_are_served_events_and_name_a_connection",
        "test_sample_routes_pass_check",
        "test_check_returns_sentences_and_does_not_raise",
        "test_kwargs_are_deterministic_literals_for_every_event",
        "test_kwargs_do_not_modify_the_route",
    ):
        getattr(_notifier(WithDefault, routes=[bare]), test)()


def test_a_named_connection_wins_over_the_default() -> None:
    from fluid_sdk.roles.alert_notifier import connection_required, with_default_connection

    class WithDefault(_Good):
        default_connection = "teams_default"

    kind = WithDefault()
    assert with_default_connection(kind, ROUTE).connection == "c"
    assert not connection_required(kind)
    assert connection_required(_Good())

    class NoConnectionNeeded(_Good):
        requires_connection = False

    assert not connection_required(NoConnectionNeeded())


# --- core command names (forge-cli 0.39.0) ------------------------------------------------


def _registers(*names: str) -> Any:
    def entry(sp: Any) -> None:
        for n in names:
            sp.add_parser(n).set_defaults(func=lambda args: 0)

    return entry


def test_a_core_command_name_or_alias_fails_the_harness_by_default() -> None:
    for name in ("validate", "dmm"):
        with pytest.raises(AssertionError, match="core forge-cli command"):
            _command(_registers(name)).test_command_names_are_not_reserved()
    _command(_registers("acme-hello")).test_command_names_are_not_reserved()


def test_extra_reserved_names_add_to_the_core_list() -> None:
    _fails(
        _command(_registers("acme-hello"), reserved=("acme-hello",)),
        "test_command_names_are_not_reserved",
    )
    _fails(
        _command(_registers("plan"), reserved=("acme-hello",)),
        "test_command_names_are_not_reserved",
    )


def test_the_core_check_can_be_turned_off_for_an_older_forge() -> None:
    harness = _command(_registers("validate"))
    type(harness).check_core_command_names = False
    harness.test_command_names_are_not_reserved()


def test_the_vendored_core_list_has_the_pipeline_commands() -> None:
    from fluid_sdk.roles._forge_commands import FORGE_CORE_COMMANDS

    assert {"validate", "plan", "apply", "init", "forge", "dmm", "opds"} <= FORGE_CORE_COMMANDS
