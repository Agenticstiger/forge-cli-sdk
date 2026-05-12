"""Unit tests for ``fluid_sdk.roles.validator``."""

from __future__ import annotations

from fluid_sdk import Finding, Validator


def test_finding_to_action() -> None:
    f = Finding(
        severity="error",
        code="STEWARD_MISSING",
        message="Missing steward",
        path="metadata.steward",
        remediation="Add metadata.steward",
    )
    a = f.to_action()
    assert a.op == "emit_finding"
    assert a.resource_id == "STEWARD_MISSING"
    assert a.params["severity"] == "error"
    assert a.params["code"] == "STEWARD_MISSING"
    assert a.params["message"] == "Missing steward"
    assert a.params["path"] == "metadata.steward"
    assert a.params["remediation"] == "Add metadata.steward"


# ---------------------------------------------------------------------------
# Toy Validator subclass
# ---------------------------------------------------------------------------


class _ToyValidator(Validator):
    name = "toy-validator"

    def plan(self, contract):
        findings = []
        metadata = contract.get("metadata") or {}
        if not metadata.get("owner"):
            findings.append(
                Finding(
                    severity="error",
                    code="OWNER_MISSING",
                    message="No owner declared",
                    path="metadata.owner",
                )
            )
        if not contract.get("description"):
            findings.append(
                Finding(
                    severity="warn",
                    code="NO_DESCRIPTION",
                    message="Missing description",
                    path="description",
                )
            )
        return [f.to_action().to_dict() for f in findings]


def test_validator_role_is_set() -> None:
    assert _ToyValidator.role == "validator"


def test_validator_default_apply_summarises_findings() -> None:
    val = _ToyValidator()
    # No owner, no description → both findings emitted.
    actions = val.plan({"metadata": {}})
    assert len(actions) == 2
    result = val.apply(actions)
    assert result.applied == 1  # the warning
    assert result.failed == 1  # the error
    assert result.role == "validator"


def test_validator_clean_contract() -> None:
    val = _ToyValidator()
    actions = val.plan({"metadata": {"owner": "team-x"}, "description": "x"})
    assert actions == []
    result = val.apply(actions)
    assert result.applied == 0
    assert result.failed == 0
