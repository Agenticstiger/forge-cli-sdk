"""Typed value domains for the FLUID plugin SDK.

Three closed string domains that previously travelled as bare ``str`` and were
therefore typo-prone:

* :class:`Severity` — a finding's severity (``info`` / ``warn`` / ``error`` /
  ``critical``).
* :class:`ActionStatus` — a per-action execution status.
* :class:`Phase` — an action's execution-phase grouping.

Each is a ``str``-mixed enum (the canonical *pre-3.11* ``StrEnum`` recipe), so a
member **is** its string value::

    Severity.ERROR == "error"              # True
    json.dumps(Severity.ERROR) == '"error"'  # True

We deliberately avoid :class:`enum.StrEnum` (Python 3.11+) and the
``backports.strenum`` dependency to preserve the SDK's **stdlib-only** contract;
the explicit ``__str__`` override reproduces ``StrEnum``'s value-returning
semantics on Python 3.10. (Pattern: CPython enum HOWTO ``StrEnum`` recipe —
https://docs.python.org/3/howto/enum.html#strenum.)

Borrowed model: dbt-core's closed severity/status vocabularies and its
"normalise unknown values loudly, never silently downgrade" posture
(https://github.com/dbt-labs/dbt-core).

**Why ``coerce`` fails safe.** A misspelled severity must never let a *failing*
finding slip past the failure tally. :meth:`Severity.coerce` maps known aliases
and, for an unrecognised non-empty value, returns the configured ``unknown``
default — :attr:`Severity.ERROR` — so a typo surfaces as a failure rather than
silently passing. :meth:`ActionStatus.coerce` is conservative the same way
(unknown → :attr:`ActionStatus.FAILED`); :class:`Phase` has no safety dimension,
so unknown phases fall back to :attr:`Phase.DEFAULT`.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, FrozenSet

try:  # Literal is stdlib since 3.8; guarded purely for defensiveness.
    from typing import Literal

    SeverityLiteral = Literal["info", "warn", "error", "critical"]
    ActionStatusLiteral = Literal[
        "ok", "created", "updated", "unchanged", "skipped", "reported", "failed"
    ]
    PhaseLiteral = Literal[
        "infrastructure",
        "iam",
        "build",
        "expose",
        "schedule",
        "validate",
        "scaffold",
        "catalog",
        "default",
    ]
except ImportError:  # pragma: no cover - Literal always present on supported Pythons
    SeverityLiteral = str  # type: ignore[misc,assignment]
    ActionStatusLiteral = str  # type: ignore[misc,assignment]
    PhaseLiteral = str  # type: ignore[misc,assignment]


class _StrEnum(str, Enum):
    """``str``-mixed enum whose ``str()`` returns its value (pre-3.11 StrEnum).

    The ``str`` mix-in makes members compare equal to and serialise as their
    value; the ``__str__`` override fixes the one place a bare ``(str, Enum)``
    diverges from :class:`enum.StrEnum` — ``str(member)`` would otherwise return
    ``"ClassName.MEMBER"`` instead of the value.
    """

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)

    @classmethod
    def _missing_(cls, value: object) -> "_StrEnum | None":
        # Tolerate case and surrounding whitespace on direct construction so
        # ``Severity("ERROR ")`` resolves; genuinely unknown values still raise
        # (use ``coerce`` for graceful, fail-safe normalisation).
        if isinstance(value, str):
            needle = value.strip().lower()
            for member in cls:
                if member.value == needle:
                    return member
        return None


class Severity(_StrEnum):
    """A finding's severity. ``error`` and ``critical`` are *failing*."""

    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"

    @property
    def is_failing(self) -> bool:
        """True if a finding at this severity should fail the run."""
        return self in FAILING_SEVERITIES

    @classmethod
    def is_known(cls, value: object) -> bool:
        """True if ``value`` is a recognised severity value or alias.

        Lets callers distinguish a clean severity from one that ``coerce``
        will fail-safe (so they can warn about the typo).
        """
        if isinstance(value, Severity):
            return True
        s = ("" if value is None else str(value)).strip().lower()
        return bool(s) and (s in _SEVERITY_BY_VALUE or s in _SEVERITY_ALIASES)

    @classmethod
    def coerce(cls, value: object, *, unknown: "Severity | None" = None) -> "Severity":
        """Normalise ``value`` to a :class:`Severity`, failing safe.

        * Known value or alias → the canonical member.
        * Empty / ``None`` → :attr:`INFO` (an absent finding is informational).
        * Unrecognised non-empty value → ``unknown`` (default :attr:`ERROR`),
          so a typo can never downgrade a failing finding to passing.
        """
        if isinstance(value, Severity):
            return value
        s = ("" if value is None else str(value)).strip().lower()
        if not s:
            return cls.INFO
        if s in _SEVERITY_BY_VALUE:
            return _SEVERITY_BY_VALUE[s]
        if s in _SEVERITY_ALIASES:
            return _SEVERITY_ALIASES[s]
        return unknown if unknown is not None else cls.ERROR


class ActionStatus(_StrEnum):
    """A per-action execution status in :class:`fluid_sdk.ExecutionResult`."""

    OK = "ok"
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    SKIPPED = "skipped"
    REPORTED = "reported"
    FAILED = "failed"

    @property
    def is_failure(self) -> bool:
        return self is ActionStatus.FAILED

    @classmethod
    def coerce(cls, value: object, *, unknown: "ActionStatus | None" = None) -> "ActionStatus":
        """Normalise ``value`` to an :class:`ActionStatus`, conservatively.

        Unrecognised values map to ``unknown`` (default :attr:`FAILED`) so a
        bogus status is never mistaken for success.
        """
        if isinstance(value, ActionStatus):
            return value
        s = ("" if value is None else str(value)).strip().lower()
        if not s:
            return unknown if unknown is not None else cls.FAILED
        if s in _STATUS_BY_VALUE:
            return _STATUS_BY_VALUE[s]
        if s in _STATUS_ALIASES:
            return _STATUS_ALIASES[s]
        return unknown if unknown is not None else cls.FAILED


class Phase(_StrEnum):
    """An action's execution-phase grouping (ordering hint, not safety)."""

    INFRASTRUCTURE = "infrastructure"
    IAM = "iam"
    BUILD = "build"
    EXPOSE = "expose"
    SCHEDULE = "schedule"
    VALIDATE = "validate"
    SCAFFOLD = "scaffold"
    CATALOG = "catalog"
    DEFAULT = "default"

    @classmethod
    def coerce(cls, value: object, *, unknown: "Phase | None" = None) -> "Phase":
        """Normalise ``value`` to a :class:`Phase`; unknown → :attr:`DEFAULT`."""
        if isinstance(value, Phase):
            return value
        s = ("" if value is None else str(value)).strip().lower()
        if s in _PHASE_BY_VALUE:
            return _PHASE_BY_VALUE[s]
        return unknown if unknown is not None else cls.DEFAULT


# ── Lookup tables + alias maps (module-level so they aren't enum members) ──

FAILING_SEVERITIES: FrozenSet[Severity] = frozenset({Severity.ERROR, Severity.CRITICAL})

_SEVERITY_BY_VALUE: Dict[str, Severity] = {m.value: m for m in Severity}
_SEVERITY_ALIASES: Dict[str, Severity] = {
    "information": Severity.INFO,
    "informational": Severity.INFO,
    "notice": Severity.INFO,
    "debug": Severity.INFO,
    "trace": Severity.INFO,
    "warning": Severity.WARN,
    "low": Severity.WARN,
    "err": Severity.ERROR,
    "failure": Severity.ERROR,
    "fail": Severity.ERROR,
    "high": Severity.ERROR,
    "fatal": Severity.CRITICAL,
    "crit": Severity.CRITICAL,
    "severe": Severity.CRITICAL,
    "blocker": Severity.CRITICAL,
}

_STATUS_BY_VALUE: Dict[str, ActionStatus] = {m.value: m for m in ActionStatus}
_STATUS_ALIASES: Dict[str, ActionStatus] = {
    "success": ActionStatus.OK,
    "succeeded": ActionStatus.OK,
    "done": ActionStatus.OK,
    "applied": ActionStatus.OK,
    "written": ActionStatus.CREATED,
    "wrote": ActionStatus.CREATED,
    "create": ActionStatus.CREATED,
    "update": ActionStatus.UPDATED,
    "modified": ActionStatus.UPDATED,
    "noop": ActionStatus.UNCHANGED,
    "no-op": ActionStatus.UNCHANGED,
    "skip": ActionStatus.SKIPPED,
    "ignored": ActionStatus.SKIPPED,
    "reported": ActionStatus.REPORTED,
    "error": ActionStatus.FAILED,
    "errored": ActionStatus.FAILED,
    "fail": ActionStatus.FAILED,
    "failure": ActionStatus.FAILED,
}

_PHASE_BY_VALUE: Dict[str, Phase] = {m.value: m for m in Phase}


__all__ = [
    "Severity",
    "ActionStatus",
    "Phase",
    "FAILING_SEVERITIES",
    "SeverityLiteral",
    "ActionStatusLiteral",
    "PhaseLiteral",
]
