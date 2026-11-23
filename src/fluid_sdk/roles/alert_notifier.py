"""The :class:`AlertNotifier` role: a route kind for the alerts of generated DAGs.

forge-cli 0.38.0 writes the DAGs of ``fluid generate schedule`` with alert routes a contract
declares (``alerts.routes``): who hears about a failed task, a retry, a success or a missed
SLA, and how. A route's ``kind`` is ``email``, ``slack``, ``webhook``, ``pagerduty`` or the kind
of a package that registers one under the ``fluid_build.alert_notifiers`` entry-point group.
That is this role.

Unlike the other roles, an alert notifier has no ``plan`` / ``apply``: it is a small
description of an Airflow notifier. forge-cli reads a handful of attributes and calls
:meth:`AlertNotifier.kwargs` once per event, then writes ``Notifier(**kwargs)`` into the DAG.
The class therefore does not subclass :class:`fluid_sdk.base.BasePlugin`. Its attribute names,
defaults and method signatures are forge-cli's own, and forge-cli reads them from any object, so
a package that does not want an SDK dependency can write the same attributes by hand.

Example::

    from fluid_sdk import Alert, AlertNotifier, AlertRoute

    class TeamsNotifier(AlertNotifier):
        notifier = "acme_alerts.notifiers:TeamsNotifier"
        requirements = ("acme-alerts>=1.2",)
        default_connection = "teams_default"

        def kwargs(self, route: AlertRoute, alert: Alert):
            return {
                "title": alert.title,
                "text": alert.text,
                "teams_conn_id": route.connection,   # the route's own, else the default
            }

Register via entry-point (the name is the route's ``kind``)::

    [project.entry-points."fluid_build.alert_notifiers"]
    teams = "acme_alerts.forge:TeamsNotifier"

A route needs to name a connection only when the kind's ``requires_connection`` is true and its
``default_connection`` is ``None``. When a route names none, forge-cli hands :meth:`check` and
:meth:`kwargs` the kind's ``default_connection`` as ``route.connection``, so a kind needs no
fallback of its own; a connection the route names wins. (forge-cli 0.39.0; 0.38.0 refused a route
with no connection whenever ``requires_connection`` was true.)

The default routes of an organisation go through a second group,
``fluid_build.alert_defaults``; see :func:`alert_route`.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

from ._forge_secrets import looks_like_secret, secret_option_key

#: Entry-point group of route kinds (read by name, loaded when a route names the kind).
NOTIFIER_GROUP = "fluid_build.alert_notifiers"

#: Entry-point group of an organisation's default routes (loaded when a DAG is rendered).
DEFAULTS_GROUP = "fluid_build.alert_defaults"

#: Every event a route can alert on, in the order a DAG wires them.
EVENTS: Tuple[str, ...] = ("failure", "retry", "success", "sla_miss")

#: The events a route alerts on when it names none.
DEFAULT_EVENTS: Tuple[str, ...] = ("failure",)

#: The severities a route can set, most severe first (PagerDuty's).
SEVERITIES: Tuple[str, ...] = ("critical", "error", "warning", "info")

#: The severity an event alerts with when its route sets none. A success is always ``info``.
EVENT_SEVERITY: Mapping[str, str] = {
    "failure": "critical",
    "retry": "warning",
    "sla_miss": "warning",
    "success": "info",
}

#: The names of the kinds forge-cli ships. A plugin may not take one: it adds a kind and never
#: replaces one. Names are compared lower case with ``-`` for ``_``.
BUILTIN_KINDS: Tuple[str, ...] = ("email", "slack", "webhook", "pagerduty")

#: Route keys only a built-in kind reads, so a route of another kind may not set them.
BUILTIN_ONLY_KEYS: Mapping[str, FrozenSet[str]] = {
    "to": frozenset({"email"}),
    "from": frozenset({"email"}),
    "format": frozenset({"webhook"}),
}

#: ``module.path:ClassName`` of an Airflow notifier: dotted identifiers only, because
#: forge-cli writes it into the DAG as an import.
NOTIFIER_PATH = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*:[A-Za-z_][A-Za-z0-9_]*\Z"
)

#: A pip requirement as the DAG's documentation lists it: no quote, backslash or newline.
REQUIREMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._\-\[\],<>=!~ ]{0,119}\Z")

#: The spelling of a route's ``kind`` (and so of the entry-point name, once normalised).
KIND_NAME = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")

#: The spelling of a route's ``name``.
ROUTE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_-]{0,63}\Z")

#: Airflow connection ids, in the characters every secrets backend keeps.
CONNECTION_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,249}\Z")

_KEY_SHAPED = re.compile(
    r"(?:[0-9a-fA-F]{20,}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{12})\Z"
)
_MIN_TOKEN = 24
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_EMAIL = re.compile(r"[A-Za-z0-9._+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63})+\Z")
_OPTION_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
_MAX_TEXT = 1000
_MAX_ITEMS = 50
_MAX_DEPTH = 4
_ROUTE_KEYS = frozenset(
    {"name", "kind", "events", "connection", "to", "from", "format", "severity", "options"}
)


def normalise_kind(name: str) -> str:
    """The spelling a kind is compared in: lower case, ``-`` for ``_``."""
    return str(name).strip().lower().replace("_", "-")


# ---------------------------------------------------------------------------
# The values forge-cli hands a kind
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AlertRoute:
    """One route, as forge-cli hands it to a kind (checked before :meth:`AlertNotifier.kwargs`).

    ``connection`` is the Airflow connection id, never a URL or a key. A kind's ``check`` and
    ``kwargs`` see the kind's ``default_connection`` here when the contract's route names none
    (:func:`with_default_connection`). ``to`` and ``sender``
    are email addresses. ``options`` holds a plugin kind's own settings: JSON values whose
    strings carry no template syntax, no URL and no secret. ``origin`` says where the route
    came from: ``contract`` or ``org default <entry point name>``.
    """

    name: str
    kind: str
    events: Tuple[str, ...] = DEFAULT_EVENTS
    connection: Optional[str] = None
    to: Tuple[str, ...] = ()
    sender: Optional[str] = None
    format: Optional[str] = None
    severity: Optional[str] = None
    options: Mapping[str, Any] = field(default_factory=dict, hash=False)
    origin: str = "contract"

    def severity_for(self, event: str) -> str:
        """The severity this route alerts ``event`` with."""
        if event == "success":
            return "info"
        return self.severity or EVENT_SEVERITY.get(event, "critical")


@dataclass(frozen=True)
class Alert:
    """What one notifier call reports: one event of one DAG, as forge-cli words it.

    ``title`` and ``text`` are Jinja templates the notifier renders with Airflow's context when
    the event happens. They are forge-cli's own text around validated ids, so a kind may pass
    them on as they are. ``dedup_key`` is the same for every event of one DAG. ``sla_seconds``
    is set for ``sla_miss``.
    """

    event: str
    dag_id: str
    product_id: str
    severity: str
    title: str
    text: str
    dedup_key: str
    sla_seconds: Optional[int] = None


@dataclass(frozen=True)
class NotifierCall:
    """One notifier the DAG instantiates for an event: ``module.name(**kwargs)``."""

    module: str
    name: str
    kwargs: Mapping[str, Any]
    route: str
    supports_async: bool = False


_TASK_TEXT = "Run {{ ti.run_id }}, try {{ ti.try_number }}. Log: {{ ti.log_url }}"
_SLA_TEXT = (
    "{% if task_list is defined %}Not done in time: {{ task_list }}"
    "{% else %}Run {{ dag_run.dag_run_id }} was not done by {{ deadline.deadline_time }}"
    "{% endif %}"
)


def _duration_words(seconds: int) -> str:
    parts = []
    remaining = int(seconds)
    for size, unit in ((86400, "d"), (3600, "h"), (60, "m"), (1, "s")):
        count, remaining = divmod(remaining, size)
        if count:
            parts.append(f"{count}{unit}")
    return "".join(parts) or "0s"


def sample_alert(
    event: str,
    *,
    severity: str = "critical",
    dag_id: str = "fluid.validate",
    product_id: str = "fluid.validate",
    sla_seconds: Optional[int] = 3600,
) -> Alert:
    """An :class:`Alert` worded as forge-cli's ``make_alert`` words it, for tests.

    The titles, texts, dedup key and ``sla_seconds`` follow forge-cli (``sla_seconds`` is set
    for every event when an SLA is planned, as it is there). forge-cli checks a kind by calling
    :meth:`AlertNotifier.kwargs` with ``dag_id="fluid.validate"`` at ``fluid validate``; the
    same ids are the default here. forge-cli's wording is the authority and may change.
    """
    if event == "failure":
        title, text = f"fluid: {dag_id}: task {{{{ ti.task_id }}}} failed", _TASK_TEXT
    elif event == "retry":
        title = f"fluid: {dag_id}: task {{{{ ti.task_id }}}} failed and will retry"
        text = _TASK_TEXT
    elif event == "success":
        title, text = f"fluid: {dag_id} succeeded", "Run {{ run_id }}."
    elif event == "sla_miss":
        title = f"fluid: {dag_id} missed its SLA of {_duration_words(int(sla_seconds or 0))}"
        text = _SLA_TEXT
    else:
        raise ValueError(f"unknown alert event {event!r}; expected one of {', '.join(EVENTS)}")
    return Alert(
        event=event,
        dag_id=dag_id,
        product_id=product_id,
        severity=severity,
        title=title,
        text=text,
        dedup_key=f"fluid/{dag_id}",
        sla_seconds=int(sla_seconds) if sla_seconds else None,
    )


# ---------------------------------------------------------------------------
# The role
# ---------------------------------------------------------------------------


class AlertNotifier:
    """Base class of an alert route kind: the typed surface of ``fluid_build.alert_notifiers``.

    A subclass sets :attr:`notifier` and implements :meth:`kwargs`; the rest has defaults.
    forge-cli builds the entry point's class with no arguments (an instance, or a function that
    returns one, work too), reads the attributes below and never runs the notifier itself: it
    writes ``Notifier(**kwargs)`` into the DAG. The notifier is an ordinary Airflow
    ``BaseNotifier`` subclass in a package the Airflow workers, the scheduler's DAG processor
    (and, for deadline alerts, the triggerer) can import.
    """

    #: Canonical role tag (not read by forge-cli; used by tooling and the harness).
    role = "alert_notifier"

    #: ``"<module>:<class>"`` of the Airflow notifier the DAG imports.
    notifier: str = ""

    #: The pip requirements the Airflow environment needs for :attr:`notifier`.
    requirements: Tuple[str, ...] = ()

    #: Whether the notifier implements ``async_notify``. Airflow 3 has no SLAs: an ``sla_miss``
    #: route alerts there through a deadline alert, which runs the notifier in the triggerer.
    supports_async: bool = False

    #: What the triggerer needs for ``async_notify`` when it is newer than :attr:`requirements`.
    async_requirements: Tuple[str, ...] = ()

    #: The events this kind can send. A route that asks for another is refused.
    events: FrozenSet[str] = frozenset(EVENTS)

    #: Whether a route of this kind must name an Airflow connection. A kind that also has a
    #: :attr:`default_connection` never does: a route needs to name a connection only when
    #: ``requires_connection`` is true and ``default_connection`` is ``None``.
    requires_connection: bool = True

    #: The Airflow connection a route that names none uses: a plain connection id (a provider's
    #: own default, such as ``slack_default``). :meth:`check` and :meth:`kwargs` get it as the
    #: route's ``connection``, so the kind needs no fallback of its own. A connection the route
    #: names wins.
    default_connection: Optional[str] = None

    def check(self, route: AlertRoute) -> Sequence[str]:
        """Problems with ``route`` this kind cannot render, each a sentence; none when it can.

        Called before :meth:`kwargs`, at ``fluid validate`` and when a DAG is rendered. Never
        quote a route value that may be a secret.
        """
        return ()

    def kwargs(self, route: AlertRoute, alert: Alert) -> Mapping[str, Any]:
        """The notifier's keyword arguments for ``alert``: literals only.

        A string may hold Jinja for Airflow's context (``{{ ti.task_id }}``): the notifier
        renders its template fields when it sends. Keys must be Python identifiers and may not
        be ``context``, which Airflow passes itself.
        """
        raise NotImplementedError(f"{type(self).__name__}.kwargs")


# ---------------------------------------------------------------------------
# Rules forge-cli applies; the harness and the helpers below share them
# ---------------------------------------------------------------------------


def key_shaped(value: str) -> bool:
    """Whether ``value`` looks like a key, not a name: hex, a UUID or a random token."""
    if _KEY_SHAPED.match(value):
        return True
    if len(value) < _MIN_TOKEN or not value.isascii() or not value.isalnum():
        return False
    pairs = list(zip(value, value[1:], strict=False))
    digit_switches = sum(1 for a, b in pairs if a.isdigit() != b.isdigit())
    case_switches = sum(
        1 for a, b in pairs if a.isalpha() and b.isalpha() and a.isupper() != b.isupper()
    )
    return digit_switches >= 8 or case_switches >= 0.45 * len(value)


def connection_required(kind: Any) -> bool:
    """Whether a route of ``kind`` must name a connection: the kind requires one and has no
    ``default_connection`` (forge-cli's rule). ``kind`` is a kind object or class."""
    return bool(getattr(kind, "requires_connection", True)) and (
        getattr(kind, "default_connection", None) is None
    )


def with_default_connection(kind: Any, route: AlertRoute) -> AlertRoute:
    """``route`` as forge-cli hands it to ``kind``: when the route names no connection, its
    ``connection`` is the kind's ``default_connection``; a connection it names is kept."""
    default = getattr(kind, "default_connection", None)
    if route.connection or not isinstance(default, str) or not default:
        return route
    return replace(route, connection=default)


def connection_problem(value: Any) -> str:
    """Why ``value`` is not an Airflow connection id a route may name, or ``""``."""
    if not isinstance(value, str) or not CONNECTION_ID.match(value):
        return (
            "is not an Airflow connection id (letters, digits, '_', '.' and '-'); a URL, an "
            "address or a key belongs IN that connection, which the route names"
        )
    if key_shaped(value) or looks_like_secret(value):
        return "looks like a key, not a connection id; put the key in an Airflow connection"
    return ""


def notifier_problem(obj: Any) -> str:
    """Why ``obj`` is not a route kind forge-cli accepts, or ``""`` when it is one.

    The same checks forge-cli runs on what an entry point loads: the ``notifier`` path, a
    callable ``kwargs``, plain pip requirements, a plain default connection id, and ``events``
    drawn from :data:`EVENTS`.
    """
    path = getattr(obj, "notifier", None)
    if not isinstance(path, str) or not NOTIFIER_PATH.match(path):
        return "its `notifier` is not a '<module>:<class>' path of an Airflow notifier"
    if not callable(getattr(obj, "kwargs", None)):
        return "it has no `kwargs(route, alert)` method"
    for attr in ("requirements", "async_requirements"):
        values = getattr(obj, attr, ())
        if not isinstance(values, (list, tuple)) or not all(
            isinstance(v, str) and REQUIREMENT.match(v) for v in values
        ):
            return f"its `{attr}` is not a list of plain pip requirements"
    default = getattr(obj, "default_connection", None)
    if default is not None and connection_problem(default):
        return "its `default_connection` is not a plain Airflow connection id"
    events = getattr(obj, "events", EVENTS)
    try:
        unknown = sorted(set(events) - set(EVENTS))
    except TypeError:
        return "its `events` is not a set of event names"
    if unknown:
        return f"its `events` names unknown events ({', '.join(map(str, unknown))})"
    return ""


def kwargs_problem(value: Any, depth: int = 0) -> str:
    """Why a notifier keyword argument cannot be written into a DAG as a literal, or ``""``."""
    if depth > 8:
        return "is nested too deep"
    if value is None or isinstance(value, (bool, int, str)):
        return ""
    if isinstance(value, float):
        return "" if math.isfinite(value) else "is not a finite number"
    if isinstance(value, (list, tuple)):
        for item in value:
            problem = kwargs_problem(item, depth + 1)
            if problem:
                return problem
        return ""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                return "has a key that is not a string"
            problem = kwargs_problem(item, depth + 1)
            if problem:
                return problem
        return ""
    return f"holds a {type(value).__name__}, which is not a literal"


def _text_problem(value: str) -> str:
    if len(value) > _MAX_TEXT:
        return f"is longer than {_MAX_TEXT} characters"
    if "{" in value or "}" in value:
        return "holds '{' or '}', which Airflow's templates would read"
    if _CONTROL.search(value):
        return "holds a control character"
    if "://" in value:
        return "holds a URL; a URL belongs in the Airflow connection the route names"
    if looks_like_secret(value):
        return "holds what looks like a secret; secrets belong in the Airflow connection"
    return ""


def _option_problems(value: Any, where: str, depth: int = 0) -> List[str]:
    if depth > _MAX_DEPTH:
        return [f"{where} is nested deeper than {_MAX_DEPTH} levels"]
    if value is None or isinstance(value, (bool, int)):
        return []
    if isinstance(value, float):
        return [] if math.isfinite(value) else [f"{where} is not a finite number"]
    if isinstance(value, str):
        problem = _text_problem(value)
        return [f"{where} {problem} (value not shown)"] if problem else []
    if isinstance(value, (list, tuple)):
        if len(value) > _MAX_ITEMS:
            return [f"{where} has more than {_MAX_ITEMS} items"]
        out: List[str] = []
        for index, item in enumerate(value):
            out += _option_problems(item, f"{where}[{index}]", depth + 1)
        return out
    if isinstance(value, Mapping):
        if len(value) > _MAX_ITEMS:
            return [f"{where} has more than {_MAX_ITEMS} keys"]
        out = []
        for key, item in value.items():
            if not isinstance(key, str) or not _OPTION_KEY.match(key):
                out.append(f"{where} has a key that is not a plain name (value not shown)")
            elif secret_option_key(key):
                out.append(
                    f"{where}.{key} is named like a secret; a kind's secret belongs in the "
                    "Airflow connection the route names (value not shown)"
                )
            else:
                out += _option_problems(item, f"{where}.{key}", depth + 1)
        return out
    return [f"{where} is a {type(value).__name__}, not a JSON value"]


def check_alert_route(raw: Any, where: str = "route") -> List[str]:
    """Problems with one route written as a contract writes it; none when forge-cli reads it.

    Checks the route's shape the way forge-cli does when it reads an ``alerts.routes`` entry or
    an ``fluid_build.alert_defaults`` entry: the keys, ``name``, ``kind``, ``events``,
    ``connection``, ``to`` / ``from`` (built-in ``email`` only), ``severity`` and ``options``
    (JSON values with no template syntax, no URL and no secret-named key). A message never
    quotes a value. Strings are also refused when they look like a secret, by the redactor's
    patterns forge-cli uses (vendored in part). forge-cli is the authority and may refuse more:
    it also asks the route's kind, which this cannot do without loading the kind, and its
    redactor has rules this SDK cannot carry.

    It does not require a ``connection``: whether a route must name one depends on its kind (see
    :func:`connection_required`), and a kind with a ``default_connection`` fills it in.
    """
    if not isinstance(raw, Mapping):
        return [f"{where} is not a mapping"]
    errors: List[str] = []
    unknown = sorted(str(k) for k in raw if k not in _ROUTE_KEYS)
    if unknown:
        errors.append(
            f"{where} has keys a route does not read: {', '.join(unknown)} (a route reads "
            f"{', '.join(sorted(_ROUTE_KEYS))})"
        )
    name = raw.get("name")
    if (
        not isinstance(name, str)
        or not ROUTE_NAME.match(name)
        or key_shaped(name)
        or looks_like_secret(name)
    ):
        errors.append(
            f"{where}.name must be a plain name (a letter or '_', then letters, digits, '_' "
            "and '-', at most 64) (value not shown)"
        )
    kind = raw.get("kind")
    if not isinstance(kind, str) or not KIND_NAME.match(kind) or looks_like_secret(kind):
        errors.append(
            f"{where}.kind must name a kind: {', '.join(BUILTIN_KINDS)}, or a plugin's "
            "(lower case letters, digits, '_' and '-') (value not shown)"
        )
        kind = ""
    events = raw.get("events", list(DEFAULT_EVENTS))
    if (
        not isinstance(events, (list, tuple))
        or not events
        or not all(isinstance(e, str) and e in EVENTS for e in events)
        or len(set(events)) != len(events)
    ):
        errors.append(f"{where}.events must be a list of distinct events from {', '.join(EVENTS)}")
    connection = raw.get("connection")
    if connection is not None:
        problem = connection_problem(connection)
        if problem:
            errors.append(f"{where}.connection {problem} (value not shown)")
    to = raw.get("to", [])
    if not isinstance(to, (list, tuple)) or len(to) > _MAX_ITEMS:
        errors.append(f"{where}.to must be a list of at most {_MAX_ITEMS} email addresses")
    elif not all(isinstance(a, str) and _EMAIL.match(a) for a in to):
        errors.append(f"{where}.to holds something that is not a plain email address")
    sender = raw.get("from")
    if sender is not None and not (isinstance(sender, str) and _EMAIL.match(sender)):
        errors.append(f"{where}.from must be a plain email address")
    fmt = raw.get("format")
    if fmt is not None and (not isinstance(fmt, str) or _text_problem(fmt)):
        errors.append(f"{where}.format must be a plain word (value not shown)")
    severity = raw.get("severity")
    if severity is not None and severity not in SEVERITIES:
        errors.append(f"{where}.severity must be one of {', '.join(SEVERITIES)}")
    options = raw.get("options", {})
    if not isinstance(options, Mapping):
        errors.append(f"{where}.options must be a mapping")
        options = {}
    else:
        errors += _option_problems(options, f"{where}.options")
    normal = normalise_kind(kind) if kind else ""
    for key, kinds in BUILTIN_ONLY_KEYS.items():
        if key in raw and normal and normal not in kinds:
            errors.append(f"{where}.{key} is read by a {' or '.join(sorted(kinds))} route only")
    if options and normal in BUILTIN_KINDS:
        errors.append(f"{where}.options is read by a plugin's kind only, not by {normal!r}")
    return errors


def alert_route(
    name: str,
    kind: str,
    *,
    events: Optional[Sequence[str]] = None,
    connection: Optional[str] = None,
    severity: Optional[str] = None,
    to: Optional[Sequence[str]] = None,
    sender: Optional[str] = None,
    format: Optional[str] = None,  # noqa: A002 - the contract's own key
    options: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """One default route, written as a contract writes it, checked against forge-cli's shape.

    For an ``fluid_build.alert_defaults`` entry point, which loads to a list of routes or to a
    function that returns one::

        from fluid_sdk import alert_route

        def default_routes():
            return [
                alert_route("oncall", "pagerduty", connection="pagerduty_oncall",
                            events=["failure", "sla_miss"]),
            ]

        # pyproject.toml
        # [project.entry-points."fluid_build.alert_defaults"]
        # acme = "acme_pack.alerts:default_routes"

    Raises:
        ValueError: the route is not one forge-cli reads; the message lists each problem and
            quotes no value.
    """
    route: Dict[str, Any] = {"name": name, "kind": kind}
    if events is not None:
        route["events"] = list(events)
    if connection is not None:
        route["connection"] = connection
    if severity is not None:
        route["severity"] = severity
    if to is not None:
        route["to"] = list(to)
    if sender is not None:
        route["from"] = sender
    if format is not None:
        route["format"] = format
    if options is not None:
        route["options"] = dict(options)
    problems = check_alert_route(route)
    if problems:
        raise ValueError("; ".join(problems))
    return route


__all__ = [
    "Alert",
    "AlertNotifier",
    "AlertRoute",
    "BUILTIN_KINDS",
    "DEFAULTS_GROUP",
    "DEFAULT_EVENTS",
    "EVENTS",
    "EVENT_SEVERITY",
    "NOTIFIER_GROUP",
    "NotifierCall",
    "SEVERITIES",
    "alert_route",
    "check_alert_route",
    "connection_required",
    "normalise_kind",
    "notifier_problem",
    "sample_alert",
    "with_default_connection",
]
