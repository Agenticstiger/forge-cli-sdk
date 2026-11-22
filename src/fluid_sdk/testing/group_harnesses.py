"""Conformance harnesses for the plain roles that serve forge-cli's newer plugin groups.

* :class:`AlertNotifierTestHarness` — ``fluid_build.alert_notifiers``
* :class:`MaintenanceActionTestHarness` — ``fluid_build.maintenance_actions``
* :class:`CommandPluginTestHarness` — ``fluid_build.commands``

These roles have no ``plan`` / ``apply``, so the harnesses do not extend
:class:`~fluid_sdk.testing.PluginTestHarness`. Each encodes the rules forge-cli applies when
it loads an entry point of the group. forge-cli is the authority: a plugin that passes can still
be refused there, since some of its rules (its redactor, the Spark SQL parse) cannot be carried
by a zero-dependency SDK. Subclass one, set the class attributes and pytest
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
import keyword
import os
import sys
import unittest
import warnings
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


def _configured(owner: Any, name: str) -> Any:
    """An attribute as set, not as Python would bind it: a plain function put on the class is
    the function, not a method of the harness. An instance attribute (set in ``setup_method``)
    wins over the class's."""
    if name in vars(owner):
        return vars(owner)[name]
    raw = inspect.getattr_static(type(owner), name)
    return raw.__func__ if isinstance(raw, staticmethod) else raw


def _build_kind(obj: Any) -> Any:
    """What forge-cli does with a loaded alert entry point: a class is built with no
    arguments, and so is a callable that is not itself a kind (a function that returns one)."""
    if isinstance(obj, type) or (callable(obj) and notifier_problem(obj)):
        return obj()
    return obj


def _build_action(obj: Any) -> Any:
    """What forge-cli does with a loaded maintenance entry point: a class, or a callable that
    has no ``statements``, is called with no arguments."""
    if isinstance(obj, type) or (callable(obj) and not callable(getattr(obj, "statements", None))):
        return obj()
    return obj


def _leaf_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _leaf_strings(item)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _leaf_strings(item)


def _alert_problems(found: Any) -> List[Any]:
    """An alert kind's ``check`` result: forge-cli accepts one sentence or a sequence of them."""
    return [found] if isinstance(found, str) else list(found or ())


def _action_problems(found: Any) -> List[Any]:
    """A maintenance action's ``check`` result: forge-cli takes a sequence of sentences, and
    refuses a non-empty str or any other non-sequence ("returned no list of problems")."""
    if not found:
        return []
    assert not isinstance(found, str) and isinstance(
        found, Sequence
    ), "check() must return a list of problems (forge-cli refuses a bare string)"
    return list(found)


def _skip(reason: str) -> None:
    raise unittest.SkipTest(reason)


# ---------------------------------------------------------------------------
# Alert notifier
# ---------------------------------------------------------------------------


class AlertNotifierTestHarness:
    """Conformance harness for an alert route kind (``fluid_build.alert_notifiers``).

    Required: ``notifier_class`` (a class built with no arguments, an instance, or a function
    that returns one, as forge-cli accepts). Recommended: ``sample_routes`` (routes of this kind
    as forge-cli hands them), and ``entry_point_name`` (the name the package registers the kind
    under).
    """

    notifier_class: ClassVar[Any]
    sample_routes: ClassVar[List[AlertRoute]] = []
    entry_point_name: ClassVar[Optional[str]] = None
    allow_no_sample_routes: ClassVar[bool] = False

    def get_notifier(self) -> Any:
        return _build_kind(_configured(self, "notifier_class"))

    def _passing(self) -> List[Tuple[int, AlertRoute]]:
        """The sample routes the kind's own ``check`` accepts, with their positions."""
        kind = self.get_notifier()
        check = getattr(kind, "check", None)
        return [
            (i, r)
            for i, r in enumerate(self.sample_routes)
            if not callable(check) or not _alert_problems(check(r))
        ]

    def test_builds_with_no_arguments(self) -> None:
        assert self.get_notifier() is not None

    def test_is_an_alert_kind_forge_accepts(self) -> None:
        problem = notifier_problem(self.get_notifier())
        assert not problem, f"forge-cli would refuse this kind: it is not an alert kind: {problem}"

    def test_subclasses_alert_notifier_when_it_can(self) -> None:
        """forge-cli reads attributes and does not need the SDK base class: a plain class or
        object is fine, and this test skips for it."""
        cls = _configured(self, "notifier_class")
        if not (isinstance(cls, type) and issubclass(cls, AlertNotifier)):
            _skip(
                "not an AlertNotifier subclass: forge-cli reads the same attributes from any object"
            )

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

    def test_sample_routes_pass_check(self) -> None:
        """A kind whose ``check`` refuses every sample route would leave the kwargs tests with
        nothing to run: at least one sample route must pass."""
        if not self.sample_routes:
            return
        assert self._passing(), (
            "the kind's check() refuses every sample route, so kwargs() is never exercised; "
            "provide a route it accepts"
        )

    def test_routes_are_served_events_and_name_a_connection(self) -> None:
        kind = self.get_notifier()
        served = set(getattr(kind, "events", EVENTS))
        for i, route in enumerate(self.sample_routes):
            missing = [e for e in route.events if e not in served]
            assert (
                not missing
            ), f"sample_routes[{i}] asks for {', '.join(missing)}, which this kind does not send"
            if getattr(kind, "requires_connection", True):
                assert (
                    route.connection
                ), f"sample_routes[{i}] must name a connection: the kind requires one"

    def test_sample_routes_have_the_shape_forge_reads(self) -> None:
        for i, route in enumerate(self.sample_routes):
            raw: Dict[str, Any] = {
                "name": route.name,
                "kind": route.kind,
                "events": list(route.events),
            }
            for key, value in (
                ("connection", route.connection),
                ("severity", route.severity),
                ("from", route.sender),
                ("format", route.format),
            ):
                if value is not None:
                    raw[key] = value
            if route.to:
                raw["to"] = list(route.to)
            if route.options:
                raw["options"] = dict(route.options)
            problems = check_alert_route(raw, f"sample_routes[{i}]")
            assert not problems, "forge-cli would not read this route: " + "; ".join(problems)

    def test_check_returns_sentences_and_does_not_raise(self) -> None:
        check = getattr(self.get_notifier(), "check", None)
        if not callable(check):
            return
        for route in self.sample_routes:
            found = _alert_problems(check(route))
            assert all(isinstance(p, str) for p in found), "check() must return sentences (str)"

    def test_kwargs_are_deterministic_literals_for_every_event(self) -> None:
        kind = self.get_notifier()
        for i, route in self._passing():
            for event in route.events:
                alert = sample_alert(event, severity=route.severity_for(event))
                first = dict(kind.kwargs(route, alert))
                second = dict(kind.kwargs(route, alert))
                assert first == second, (
                    f"kwargs() for sample_routes[{i}]/{event} is not deterministic: the DAG is "
                    "rendered from it, so the same input must give the same arguments"
                )
                for key, value in first.items():
                    assert (
                        isinstance(key, str) and key.isidentifier() and not keyword.iskeyword(key)
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
        for _, route in self._passing():
            before = copy.deepcopy(route)
            for event in route.events:
                kind.kwargs(route, sample_alert(event, severity=route.severity_for(event)))
            assert route == before, "kwargs() must not modify the route"


# ---------------------------------------------------------------------------
# Maintenance action
# ---------------------------------------------------------------------------


class MaintenanceActionTestHarness:
    """Conformance harness for a maintenance action (``fluid_build.maintenance_actions``).

    Required: ``action_class`` (a class, an instance, or a function that returns one) and
    ``sample_options`` (options a contract action may give; at least one that ``check``
    accepts). Recommended: ``bad_options`` (each ``check`` must refuse). ``table`` is the name
    forge-cli's runner reads the table by, catalog first.

    Without ``sqlglot`` the statement checks are text checks and a wrong-target or unparseable
    statement can pass; the harness warns when that is the case.
    """

    action_class: ClassVar[Any]
    sample_options: ClassVar[List[Mapping[str, Any]]] = []
    bad_options: ClassVar[List[Mapping[str, Any]]] = []
    table: ClassVar[str] = "fluid.silver.orders"
    entry_point_name: ClassVar[Optional[str]] = None

    def get_action(self) -> Any:
        return _build_action(_configured(self, "action_class"))

    def _check(self, options: Mapping[str, Any]) -> List[Any]:
        """The action's problems with ``options``; a missing ``check`` is none, as in forge-cli."""
        check = getattr(self.get_action(), "check", None)
        return _action_problems(check(dict(options))) if callable(check) else []

    def _accepted(self) -> List[Mapping[str, Any]]:
        return [o for o in self.sample_options if not self._check(o)]

    def test_builds_with_no_arguments(self) -> None:
        assert self.get_action() is not None

    def test_is_an_action_forge_accepts(self) -> None:
        action = self.get_action()
        assert callable(
            getattr(action, "statements", None)
        ), "forge-cli needs statements(table, options)"

    def test_subclasses_maintenance_action_when_it_can(self) -> None:
        """forge-cli calls the same methods on any object: a plain class or object is fine, and
        this test skips for it."""
        cls = _configured(self, "action_class")
        if not (isinstance(cls, type) and issubclass(cls, MaintenanceAction)):
            _skip(
                "not a MaintenanceAction subclass: forge-cli calls the same methods on any object"
            )

    def test_entry_point_name_is_plain(self) -> None:
        name = self.entry_point_name
        if name is None:
            return
        assert KIND_NAME.match(
            normalise_kind(name)
        ), f"entry point name {name!r} should be lower case letters, digits, '_' and '-'"

    def test_some_sample_options_are_accepted(self) -> None:
        assert self._accepted(), "set sample_options with at least one mapping that check() accepts"

    def test_check_returns_a_list_of_sentences_and_does_not_raise(self) -> None:
        for options in [*self.sample_options, *self.bad_options]:
            assert all(
                isinstance(p, str) for p in self._check(options)
            ), "check() must return sentences (str)"

    def test_check_refuses_bad_options_without_echoing_values(self) -> None:
        """Refusing is forge-cli's rule. Not quoting a value is this SDK's own: forge-cli
        prints the first problem (cut at 300 characters) as the action returns it, so a value
        a check quotes is printed."""
        for options in self.bad_options:
            found = self._check(options)
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
            first = list(action.statements(self.table, dict(options)))
            second = list(action.statements(self.table, dict(options)))
            assert first == second, (
                "statements() is not deterministic: the statements are compiled into the plan "
                "digest, so the same table and options must give the same SQL"
            )

    def test_statements_are_a_list_of_accepted_writes(self) -> None:
        try:
            import sqlglot  # noqa: F401
        except ImportError:
            warnings.warn(
                "sqlglot is not installed: the statements are checked by text only, so a "
                "statement for another table, or one Spark SQL would not parse, can pass here "
                "and be refused by forge-cli. Install sqlglot for the parse.",
                stacklevel=2,
            )
        action = self.get_action()
        for options in self._accepted():
            found = action.statements(self.table, dict(options))
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
            given = dict(options)
            before = copy.deepcopy(given)
            action.statements(self.table, given)
            assert given == before, "statements() must not modify the options"


# ---------------------------------------------------------------------------
# Command plugin
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _quiet() -> Iterator[Tuple[io.StringIO, io.StringIO]]:
    """Capture stdout and stderr and keep the cwd and environment as they were."""
    out, err = io.StringIO(), io.StringIO()
    cwd, env = os.getcwd(), dict(os.environ)
    moved = changed = False
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            yield out, err
    finally:
        # Restored even when the body raises, so a failing plugin cannot leak into later tests.
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
    """How forge-cli calls ``func``: ``fn(args, logger)`` when it has a ``*args`` or at least two
    positional parameters, else ``fn(args)``. A third positional parameter must have a default."""
    try:
        params = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return True
    positional = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    varargs = any(p.kind == p.VAR_POSITIONAL for p in params)
    if varargs:
        return True
    if len(positional) >= 2:
        return sum(1 for p in positional if p.default is p.empty) <= 2
    return len(positional) == 1


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
        return _configured(self, "command_entry_point")

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

    def test_registering_adds_a_command_quietly_and_leaves_the_process_alone(self) -> None:
        _, _, added = self._register()
        assert added, "registering added no subcommand"
        # (Printing, a changed cwd or a changed environment fail inside _register.)
        if self.expected_commands:
            assert sorted(added) == sorted(self.expected_commands)

    def test_command_names_are_not_reserved(self) -> None:
        _, _, added = self._register()
        for name in added:
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
        if module_name == "__main__":
            _skip("the entry point is defined in __main__, which cannot be imported again")
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
