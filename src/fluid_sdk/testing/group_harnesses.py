"""Conformance harnesses for the plain roles that serve forge-cli's newer plugin groups.

* :class:`AlertNotifierTestHarness` — ``fluid_build.alert_notifiers``
* :class:`MaintenanceActionTestHarness` — ``fluid_build.maintenance_actions``
* :class:`CommandPluginTestHarness` — ``fluid_build.commands``

These roles have no ``plan`` / ``apply``, so the harnesses do not extend
:class:`~fluid_sdk.testing.PluginTestHarness`. Each encodes the rules forge-cli applies when
it loads an entry point of the group (forge-cli is the authority and refuses what these let
through if its own checks are stricter). Subclass one, set the class attributes and pytest
discovers every ``test_*`` method.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import importlib
import inspect
import io
import json
import os
import re
import sys
from typing import Any, Callable, ClassVar, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from ..roles.alert_notifier import (
    BUILTIN_KINDS,
    EVENTS,
    KIND_NAME,
    AlertNotifier,
    AlertRoute,
    check_alert_route,
    kwargs_problem,
    normalise_kind,
    notifier_problem,
    sample_alert,
)
from ..roles.maintenance_action import MaintenanceAction, statement_problem

_RESERVED_KWARGS = frozenset({"context"})


def _build(obj: Any) -> Any:
    """What forge-cli does with a loaded entry point: a class is built with no arguments."""
    return obj() if isinstance(obj, type) else obj


def _leaf_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _leaf_strings(item)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _leaf_strings(item)


def _problems(found: Any) -> List[Any]:
    """forge-cli accepts one sentence or a sequence of them."""
    return [found] if isinstance(found, str) else list(found or ())


# ---------------------------------------------------------------------------
# Alert notifier
# ---------------------------------------------------------------------------


class AlertNotifierTestHarness:
    """Conformance harness for an alert route kind (``fluid_build.alert_notifiers``).

    Required: ``notifier_class`` (a class built with no arguments, or an instance).
    Recommended: ``sample_routes`` (routes of this kind as forge-cli hands them), and
    ``entry_point_name`` (the name the package registers the kind under).
    """

    notifier_class: ClassVar[Any]
    sample_routes: ClassVar[List[AlertRoute]] = []
    entry_point_name: ClassVar[Optional[str]] = None
    allow_no_sample_routes: ClassVar[bool] = False

    def get_notifier(self) -> Any:
        return _build(self.notifier_class)

    def test_builds_with_no_arguments(self) -> None:
        assert self.get_notifier() is not None

    def test_is_an_alert_kind_forge_accepts(self) -> None:
        problem = notifier_problem(self.get_notifier())
        assert not problem, f"forge-cli would refuse this kind: it is not an alert kind: {problem}"

    def test_subclasses_alert_notifier_when_it_can(self) -> None:
        """Informational: forge-cli reads attributes and does not need the SDK base class."""
        if isinstance(self.notifier_class, type):
            assert issubclass(
                self.notifier_class, AlertNotifier
            ), f"{self.notifier_class.__name__} should subclass AlertNotifier"

    def test_entry_point_name_is_a_valid_new_kind(self) -> None:
        name = self.entry_point_name
        if name is None:
            return
        assert KIND_NAME.match(
            normalise_kind(name)
        ), f"entry point name {name!r} is not a kind name (lower case, digits, '_' and '-')"
        assert normalise_kind(name) not in BUILTIN_KINDS, (
            f"entry point name {name!r} is a built-in kind's name "
            f"({', '.join(BUILTIN_KINDS)}): a plugin adds a kind and never replaces one"
        )

    def test_sample_routes_present(self) -> None:
        assert self.sample_routes or self.allow_no_sample_routes, (
            f"{type(self).__name__} sets no sample_routes, so check() and kwargs() would be "
            "exercised on nothing; provide a route or set allow_no_sample_routes = True"
        )

    def test_routes_are_served_events_and_name_a_connection(self) -> None:
        kind = self.get_notifier()
        served = set(getattr(kind, "events", EVENTS))
        for route in self.sample_routes:
            missing = [e for e in route.events if e not in served]
            assert not missing, (
                f"sample route {route.name!r} asks for {', '.join(missing)}, which this kind "
                "does not send"
            )
            if getattr(kind, "requires_connection", True):
                assert (
                    route.connection
                ), f"sample route {route.name!r} must name a connection: the kind requires one"

    def test_sample_routes_have_the_shape_forge_reads(self) -> None:
        for route in self.sample_routes:
            raw: Dict[str, Any] = {
                "name": route.name,
                "kind": route.kind,
                "events": list(route.events),
            }
            if route.connection is not None:
                raw["connection"] = route.connection
            if route.severity is not None:
                raw["severity"] = route.severity
            if route.options:
                raw["options"] = dict(route.options)
            problems = check_alert_route(raw, f"route {route.name!r}")
            assert not problems, "forge-cli would not read this route: " + "; ".join(problems)

    def test_check_returns_sentences_and_does_not_raise(self) -> None:
        kind = self.get_notifier()
        check = getattr(kind, "check", None)
        if not callable(check):
            return
        for route in self.sample_routes:
            found = _problems(check(route))
            assert all(isinstance(p, str) for p in found), "check() must return sentences (str)"

    def test_kwargs_are_deterministic_literals_for_every_event(self) -> None:
        kind = self.get_notifier()
        for route in self.sample_routes:
            if _problems(kind.check(route)):
                continue
            for event in route.events:
                alert = sample_alert(event, severity=route.severity_for(event))
                first = dict(kind.kwargs(route, alert))
                second = dict(kind.kwargs(route, alert))
                assert first == second, (
                    f"kwargs() for {route.name!r}/{event} is not deterministic: the DAG is "
                    "rendered from it, so the same input must give the same arguments"
                )
                for key, value in first.items():
                    assert (
                        isinstance(key, str) and key.isidentifier() and not _is_keyword(key)
                    ), f"kwargs() returned {key!r}, which is not a Python identifier"
                    assert key not in _RESERVED_KWARGS, (
                        f"kwargs() sets {key!r}, which Airflow passes itself "
                        "(a deadline alert passes it)"
                    )
                    problem = kwargs_problem(value)
                    assert not problem, f"kwargs() argument {key!r} {problem}"
                json.dumps(first, sort_keys=True)

    def test_kwargs_do_not_modify_the_route(self) -> None:
        kind = self.get_notifier()
        for route in self.sample_routes:
            if _problems(kind.check(route)):
                continue
            before = copy.deepcopy(route)
            for event in route.events:
                kind.kwargs(route, sample_alert(event, severity=route.severity_for(event)))
            assert route == before, "kwargs() must not modify the route"


def _is_keyword(name: str) -> bool:
    import keyword

    return keyword.iskeyword(name)


# ---------------------------------------------------------------------------
# Maintenance action
# ---------------------------------------------------------------------------


class MaintenanceActionTestHarness:
    """Conformance harness for a maintenance action (``fluid_build.maintenance_actions``).

    Required: ``action_class`` and ``sample_options`` (options a contract action may give; at
    least one that ``check`` accepts). Recommended: ``bad_options`` (each ``check`` must
    refuse, naming the problem without echoing a value). ``table`` is the name forge-cli's
    runner reads the table by, catalog first.
    """

    action_class: ClassVar[Any]
    sample_options: ClassVar[List[Mapping[str, Any]]] = []
    bad_options: ClassVar[List[Mapping[str, Any]]] = []
    table: ClassVar[str] = "fluid.silver.orders"
    entry_point_name: ClassVar[Optional[str]] = None

    def get_action(self) -> Any:
        return _build(self.action_class)

    def _accepted(self) -> List[Mapping[str, Any]]:
        action = self.get_action()
        return [o for o in self.sample_options if not _problems(action.check(o))]

    def test_builds_with_no_arguments(self) -> None:
        assert self.get_action() is not None

    def test_is_an_action_forge_accepts(self) -> None:
        action = self.get_action()
        assert callable(
            getattr(action, "statements", None)
        ), "forge-cli needs statements(table, options)"

    def test_subclasses_maintenance_action_when_it_can(self) -> None:
        if isinstance(self.action_class, type):
            assert issubclass(
                self.action_class, MaintenanceAction
            ), f"{self.action_class.__name__} should subclass MaintenanceAction"

    def test_entry_point_name_is_plain(self) -> None:
        name = self.entry_point_name
        if name is None:
            return
        assert re.fullmatch(
            r"[a-z][a-z0-9_-]{0,63}", normalise_kind(name)
        ), f"entry point name {name!r} should be lower case letters, digits, '_' and '-'"

    def test_some_sample_options_are_accepted(self) -> None:
        assert self._accepted(), "set sample_options with at least one mapping that check() accepts"

    def test_check_returns_sentences_and_does_not_raise(self) -> None:
        action = self.get_action()
        check = getattr(action, "check", None)
        if not callable(check):
            return
        for options in [*self.sample_options, *self.bad_options]:
            found = _problems(check(options))
            assert all(isinstance(p, str) for p in found), "check() must return sentences (str)"

    def test_check_refuses_bad_options_without_echoing_values(self) -> None:
        action = self.get_action()
        for options in self.bad_options:
            found = _problems(action.check(options))
            assert found, f"check() accepted options it should refuse: keys {sorted(options)}"
            text = "\n".join(str(p) for p in found)
            for value in _leaf_strings(options):
                if len(value) >= 4:
                    assert value not in text, (
                        "check() quoted an option value in its message; a value may be a "
                        "secret, so name the option, never its value"
                    )

    def test_statements_are_deterministic(self) -> None:
        action = self.get_action()
        for options in self._accepted():
            first = list(action.statements(self.table, options))
            second = list(action.statements(self.table, options))
            assert first == second, (
                "statements() is not deterministic: the statements are compiled into the plan "
                "digest, so the same table and options must give the same SQL"
            )

    def test_statements_are_a_list_of_accepted_writes(self) -> None:
        action = self.get_action()
        for options in self._accepted():
            found = action.statements(self.table, options)
            assert not isinstance(found, str) and isinstance(
                found, Sequence
            ), "statements() must return a list of SQL statements"
            assert found, "statements() returned no statement: forge-cli refuses an empty list"
            for index, sql in enumerate(found):
                problem = statement_problem(sql, self.table)
                assert not problem, f"statement {index} {problem}"

    def test_statements_do_not_modify_the_options(self) -> None:
        action = self.get_action()
        for options in self._accepted():
            before = copy.deepcopy(options)
            action.statements(self.table, options)
            assert options == before, "statements() must not modify the options"


# ---------------------------------------------------------------------------
# Command plugin
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _quiet() -> Iterator[Tuple[io.StringIO, io.StringIO]]:
    """Capture stdout and stderr and keep the cwd and environment as they were."""
    out, err = io.StringIO(), io.StringIO()
    cwd, env = os.getcwd(), dict(os.environ)
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err
    moved, changed = os.getcwd() != cwd, dict(os.environ) != env
    if moved:
        os.chdir(cwd)
    if changed:
        os.environ.clear()
        os.environ.update(env)
    assert not moved, "it changed the working directory"
    assert not changed, "it changed the environment"


def _leaf_parsers(parser: argparse.ArgumentParser) -> Iterator[argparse.ArgumentParser]:
    yield parser
    for action in getattr(parser, "_actions", []):
        if isinstance(action, argparse._SubParsersAction):
            for sub in action.choices.values():
                yield from _leaf_parsers(sub)


def _accepts_one_or_two(fn: Callable[..., Any]) -> bool:
    """forge-cli calls ``fn(args, logger)``, or ``fn(args)`` when ``fn`` takes one positional."""
    try:
        params = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return True
    positional = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    varargs = any(p.kind == p.VAR_POSITIONAL for p in params)
    return varargs or len(positional) in (1, 2)


class CommandPluginTestHarness:
    """Conformance harness for a CLI subcommand plugin (``fluid_build.commands``).

    Required: ``command_entry_point``: the object the entry point names, which forge-cli
    loads and calls with the CLI's subparsers (a function, or an instance of
    :class:`~fluid_sdk.CommandPlugin`; not the class). Optional: ``expected_commands`` (the
    subcommand names it adds) and ``reserved_command_names`` (the CLI's own commands, which a
    plugin must not add again).
    """

    command_entry_point: ClassVar[Any]
    expected_commands: ClassVar[Tuple[str, ...]] = ()
    reserved_command_names: ClassVar[Tuple[str, ...]] = ()

    def _entry_point(self) -> Any:
        """The configured object, undisturbed by Python's method binding of a plain function."""
        raw = inspect.getattr_static(type(self), "command_entry_point")
        return raw.__func__ if isinstance(raw, staticmethod) else raw

    def _register(self) -> Tuple[argparse.ArgumentParser, Any, List[str]]:
        root = argparse.ArgumentParser(prog="fluid")
        sp = root.add_subparsers(dest="cmd")
        before = set(sp.choices)
        with _quiet() as (out, err):
            self._entry_point()(sp)
        assert not out.getvalue() and not err.getvalue(), "registering printed something"
        return root, sp, [n for n in sp.choices if n not in before]

    def test_entry_point_is_callable_not_a_class(self) -> None:
        target = self._entry_point()
        assert callable(target), "forge-cli calls entry_point.load()(subparsers)"
        assert not isinstance(target, type), (
            "the entry point must name a function or an instance: forge-cli would call the "
            "class with the subparsers as its argument"
        )

    def test_registering_adds_a_command_and_nothing_else(self) -> None:
        _, _, added = self._register()
        assert added, "registering added no subcommand"
        if self.expected_commands:
            assert sorted(added) == sorted(self.expected_commands)

    def test_command_names_are_plain_and_not_reserved(self) -> None:
        _, _, added = self._register()
        for name in added:
            assert re.fullmatch(
                r"[a-z][a-z0-9-]*", name
            ), f"command {name!r} should be lower case letters, digits and '-'"
            assert (
                name not in self.reserved_command_names
            ), f"command {name!r} is one of the CLI's own commands"

    def test_every_command_has_a_runnable_func(self) -> None:
        _, sp, added = self._register()
        for name in added:
            for parser in _leaf_parsers(sp.choices[name]):
                fn = parser._defaults.get("func")
                has_children = any(
                    isinstance(a, argparse._SubParsersAction) for a in parser._actions
                )
                if fn is None and has_children:
                    continue
                assert callable(fn), f"{name}: a parser with no callable func default"
                assert _accepts_one_or_two(
                    fn
                ), f"{name}: func must take (args) or (args, logger), as forge-cli calls it"

    def test_help_exits_cleanly_without_side_effects(self) -> None:
        root, _, added = self._register()
        for name in added:
            with _quiet():
                try:
                    root.parse_args([name, "--help"])
                except SystemExit as exc:
                    assert exc.code in (0, None), f"{name} --help exited {exc.code!r}"
                else:  # pragma: no cover - argparse always exits on --help
                    raise AssertionError(f"{name} --help did not exit")

    def test_importing_the_module_has_no_side_effects(self) -> None:
        """Importing it prints nothing and leaves the cwd and environment alone.

        forge-cli imports the module only when its command runs, but it must still be safe to
        import (``fluid describe --commands`` imports every plugin).
        """
        target = self._entry_point()
        module_name = getattr(target, "__module__", None) or type(target).__module__
        saved = {k: v for k, v in sys.modules.items() if k == module_name}
        sys.modules.pop(module_name, None)
        try:
            with _quiet() as (out, err):
                importlib.import_module(module_name)
            assert not out.getvalue() and not err.getvalue(), "importing the module printed"
        finally:
            sys.modules.pop(module_name, None)
            sys.modules.update(saved)


__all__ = [
    "AlertNotifierTestHarness",
    "CommandPluginTestHarness",
    "MaintenanceActionTestHarness",
]
