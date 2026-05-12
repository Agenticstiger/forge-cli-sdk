"""The :class:`Validator` role — contract-inspection plugins.

Validators inspect a fluid contract and emit findings — they don't change
infrastructure or write files. Examples:

* Custom governance rules ("every product must declare a steward")
* Compliance checks ("data residency must match deployment region")
* Cost guardrails ("warn if cluster size exceeds threshold")
* Schema cross-references ("every consume must resolve to a known produce")

Findings are :class:`Finding` records; the FLUID CLI surfaces them in
``fluid validate`` output and respects severity for exit codes.

Example::

    from fluid_sdk.roles import Validator, Finding

    class StewardRequiredValidator(Validator):
        name = "steward-required"

        def plan(self, contract):
            findings = self.check(contract)
            return [f.to_action() for f in findings]

        def check(self, contract):
            steward = (contract.get("metadata") or {}).get("steward")
            if not steward:
                return [Finding(
                    severity="error",
                    code="STEWARD_MISSING",
                    message="Contract is missing metadata.steward",
                    path="metadata.steward",
                )]
            return []

Register via entry-point::

    [project.entry-points."fluid_build.validators"]
    steward-required = "my_pkg.rules:StewardRequiredValidator"
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

from ..action import PHASE_VALIDATE, PluginAction
from ..base import BasePlugin
from ..result import ExecutionResult

# ---------------------------------------------------------------------------
# Finding — typed inspection result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """A single validation finding.

    Fields:
        severity: One of ``"info"``, ``"warn"``, ``"error"``, ``"critical"``.
            The CLI exits non-zero for ``error`` / ``critical`` by default.
        code: Stable, machine-readable identifier (e.g. ``"PII_LEAK"``).
        message: Human-readable explanation.
        path: JSON-path (or label-path) into the contract pinpointing the
            offending field. Optional.
        remediation: Optional suggested fix.
    """

    severity: str
    code: str
    message: str
    path: Optional[str] = None
    remediation: Optional[str] = None
    tags: Mapping[str, str] = field(default_factory=dict)

    def to_action(self) -> PluginAction:
        """Convert the finding into a planning action.

        The action's ``op`` is ``"emit_finding"``. The CLI's validate flow
        translates these back into displayable findings.
        """
        return PluginAction(
            op="emit_finding",
            resource_type="finding",
            resource_id=self.code,
            params={
                "severity": self.severity,
                "code": self.code,
                "message": self.message,
                "path": self.path,
                "remediation": self.remediation,
            },
            phase=PHASE_VALIDATE,
            idempotent=True,
            tags=dict(self.tags),
        )


# ---------------------------------------------------------------------------
# Validator ABC
# ---------------------------------------------------------------------------


class Validator(BasePlugin):
    """Contract-validation plugin role.

    Provides default :meth:`apply` that simply summarises findings produced
    by :meth:`plan` — there's no "execution" of a validator beyond reporting.
    Override if your validator needs side effects (writing audit logs, etc).
    """

    role = "validator"

    def apply(self, actions: Iterable[Mapping[str, Any]]) -> ExecutionResult:
        """Default: count findings by severity, return ExecutionResult."""
        started = time.monotonic()
        counts: Dict[str, int] = {"info": 0, "warn": 0, "error": 0, "critical": 0}
        results: List[Dict[str, Any]] = []

        for action in actions:
            params = action.get("params") or {}
            severity = str(params.get("severity", "info"))
            counts[severity] = counts.get(severity, 0) + 1
            results.append(
                {
                    "op": action.get("op", ""),
                    "resource_id": action.get("resource_id", ""),
                    "status": "reported",
                    "severity": severity,
                    "message": params.get("message"),
                }
            )

        failed = counts.get("error", 0) + counts.get("critical", 0)
        return ExecutionResult(
            plugin=self.name,
            role=self.role,
            applied=sum(counts.values()) - failed,
            failed=failed,
            duration_sec=round(time.monotonic() - started, 4),
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            results=results,
        )


__all__ = ["Validator", "Finding"]
