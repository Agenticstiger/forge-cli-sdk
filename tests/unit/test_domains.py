"""Unit tests for ``fluid_sdk.domains`` — the typed value domains.

Includes the regression test for the *severity footgun*: a misspelled severity
must be counted as a failure, never silently dropped from the failure tally.
"""

from __future__ import annotations

import json

from fluid_sdk import FAILING_SEVERITIES, ActionStatus, Finding, Phase, Severity, Validator
from fluid_sdk.action import PHASE_BUILD, PHASE_DEFAULT

# ---------------------------------------------------------------------------
# StrEnum semantics (zero-dep, pre-3.11 recipe)
# ---------------------------------------------------------------------------


def test_member_equals_its_string_value() -> None:
    assert Severity.ERROR == "error"
    assert ActionStatus.FAILED == "failed"
    assert Phase.BUILD == "build"


def test_str_returns_value_not_enum_repr() -> None:
    # The whole point of the __str__ override (vs a bare ``(str, Enum)``).
    assert str(Severity.ERROR) == "error"
    assert str(Phase.SCAFFOLD) == "scaffold"
    assert f"{Severity.CRITICAL}" == "critical"


def test_json_serialises_to_value() -> None:
    assert json.dumps(Severity.WARN) == '"warn"'
    assert json.dumps({"phase": Phase.CATALOG}) == '{"phase": "catalog"}'


def test_phase_constants_are_enum_members_and_back_compatible() -> None:
    assert PHASE_BUILD is Phase.BUILD
    assert PHASE_DEFAULT == "default"
    assert PHASE_BUILD == "build"


# ---------------------------------------------------------------------------
# Severity.coerce — fail-safe normalisation
# ---------------------------------------------------------------------------


def test_coerce_known_values_and_case_insensitive() -> None:
    assert Severity.coerce("error") is Severity.ERROR
    assert Severity.coerce("ERROR") is Severity.ERROR
    assert Severity.coerce("  Critical ") is Severity.CRITICAL


def test_coerce_aliases() -> None:
    assert Severity.coerce("warning") is Severity.WARN
    assert Severity.coerce("fatal") is Severity.CRITICAL
    assert Severity.coerce("failure") is Severity.ERROR


def test_coerce_empty_is_info() -> None:
    assert Severity.coerce("") is Severity.INFO
    assert Severity.coerce(None) is Severity.INFO


def test_coerce_unknown_fails_safe_to_error() -> None:
    # A typo must escalate to a failing severity, never silently pass.
    assert Severity.coerce("errror") is Severity.ERROR
    assert Severity.coerce("definitely-not-a-severity") is Severity.ERROR
    assert Severity.coerce("nope", unknown=Severity.CRITICAL) is Severity.CRITICAL


def test_is_known_distinguishes_typos() -> None:
    assert Severity.is_known("error") is True
    assert Severity.is_known("warning") is True  # alias
    assert Severity.is_known("errror") is False
    assert Severity.is_known("") is False


def test_is_failing_and_failing_set() -> None:
    assert Severity.ERROR.is_failing is True
    assert Severity.CRITICAL.is_failing is True
    assert Severity.WARN.is_failing is False
    assert Severity.INFO.is_failing is False
    assert FAILING_SEVERITIES == frozenset({Severity.ERROR, Severity.CRITICAL})


# ---------------------------------------------------------------------------
# ActionStatus + Phase coercion
# ---------------------------------------------------------------------------


def test_action_status_coerce_conservative() -> None:
    assert ActionStatus.coerce("success") is ActionStatus.OK
    assert ActionStatus.coerce("written") is ActionStatus.CREATED
    assert ActionStatus.coerce("error") is ActionStatus.FAILED
    # Unknown is treated as a failure, never as success.
    assert ActionStatus.coerce("???") is ActionStatus.FAILED
    assert ActionStatus.FAILED.is_failure is True
    assert ActionStatus.OK.is_failure is False


def test_phase_coerce_unknown_is_default() -> None:
    assert Phase.coerce("build") is Phase.BUILD
    assert Phase.coerce("not-a-phase") is Phase.DEFAULT


# ---------------------------------------------------------------------------
# Finding normalisation
# ---------------------------------------------------------------------------


def test_finding_normalises_severity_on_construction() -> None:
    assert Finding(severity="warning", code="X", message="m").severity is Severity.WARN
    # Typo fails safe to ERROR.
    assert Finding(severity="errror", code="X", message="m").severity is Severity.ERROR


# ---------------------------------------------------------------------------
# THE FOOTGUN REGRESSION: a typo'd severity must still fail the run
# ---------------------------------------------------------------------------


class _TypoValidator(Validator):
    name = "typo-validator"

    def plan(self, contract):
        # A plugin author hand-builds an action dict with a misspelled severity,
        # bypassing the Finding helper entirely.
        return [
            {
                "op": "emit_finding",
                "resource_id": "TYPO",
                "params": {"severity": "errror", "message": "boom"},
            }
        ]


def test_typo_severity_is_counted_as_failure_not_passing() -> None:
    val = _TypoValidator()
    result = val.apply(val.plan({}))
    assert result.failed == 1, "a misspelled failing severity must not escape the failure tally"
    assert result.applied == 0
    assert result.is_success is False
    assert any("unrecognised severity" in w for w in result.warnings)
