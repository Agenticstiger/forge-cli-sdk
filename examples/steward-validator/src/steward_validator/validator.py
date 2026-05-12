"""Steward Validator — fails any contract missing a data-steward identifier.

Demonstrates the :class:`Validator` role:

* Inspects a contract.
* Emits :class:`Finding` records — info / warn / error / critical.
* The FLUID CLI uses these for ``fluid validate`` output and exit codes.

Convention this validator enforces:

* ``metadata.labels["principal.steward.id"]`` is required.
* ``metadata.labels["principal.steward.email"]`` is recommended (warning if missing).

Bundle authors and platform teams can fork this pattern to encode any
governance rule (data classification, owner email format, sovereignty,
cost guardrails, etc.).
"""

from __future__ import annotations

from typing import Any, List, Mapping

from fluid_sdk import (
    ContractHelper,
    Finding,
    PluginMetadata,
    Validator,
)


class StewardValidator(Validator):
    """Fails the contract validation if a steward identifier is missing."""

    name = "steward-required"

    @classmethod
    def get_plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name=cls.name,
            role=cls.role,
            display_name="Steward Required Validator",
            description="Enforces that every contract declares metadata.labels['principal.steward.id'].",
            version="0.1.0",
            author="FLUID SDK Examples",
            tags=["governance", "compliance"],
        )

    def plan(self, contract: Mapping[str, Any]) -> List[dict]:
        c = ContractHelper(contract)
        findings: List[Finding] = []

        labels = c.metadata.get("labels") or {}
        steward_id = labels.get("principal.steward.id")
        steward_email = labels.get("principal.steward.email")

        if not steward_id:
            findings.append(
                Finding(
                    severity="error",
                    code="STEWARD_ID_MISSING",
                    message=(
                        f"Contract {c.id!r} is missing the required label "
                        f"'principal.steward.id'."
                    ),
                    path='metadata.labels["principal.steward.id"]',
                    remediation=(
                        "Add metadata.labels['principal.steward.id'] with the "
                        "employee/user identifier of the data steward."
                    ),
                )
            )

        if steward_id and not steward_email:
            findings.append(
                Finding(
                    severity="warn",
                    code="STEWARD_EMAIL_MISSING",
                    message=(
                        f"Contract {c.id!r} declares a steward id but no email — "
                        "operations notifications will go nowhere."
                    ),
                    path='metadata.labels["principal.steward.email"]',
                    remediation=(
                        "Add metadata.labels['principal.steward.email'] with the "
                        "steward's email address."
                    ),
                )
            )

        return [f.to_action().to_dict() for f in findings]
