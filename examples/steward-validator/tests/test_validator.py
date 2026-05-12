"""Tests for steward-validator."""

from __future__ import annotations

from steward_validator.validator import StewardValidator

from fluid_sdk.testing import PluginTestHarness

# A contract missing the steward → expects 1 error finding
MISSING_STEWARD_CONTRACT = {
    "fluidVersion": "0.7.4",
    "kind": "DataProduct",
    "id": "missing-steward-product",
    "name": "Missing Steward Product",
    "metadata": {
        "owner": {"team": "x", "email": "x@example.com"},
        "labels": {},
    },
}

# A contract with steward id but no email → expects 1 warning
NO_STEWARD_EMAIL_CONTRACT = {
    "fluidVersion": "0.7.4",
    "kind": "DataProduct",
    "id": "no-email-product",
    "name": "No Email Product",
    "metadata": {
        "owner": {"team": "x", "email": "x@example.com"},
        "labels": {"principal.steward.id": "emp-12345"},
    },
}

# A fully-compliant contract → expects 0 findings
COMPLIANT_CONTRACT = {
    "fluidVersion": "0.7.4",
    "kind": "DataProduct",
    "id": "good-product",
    "name": "Good Product",
    "metadata": {
        "owner": {"team": "x", "email": "x@example.com"},
        "labels": {
            "principal.steward.id": "emp-12345",
            "principal.steward.email": "steward@example.com",
        },
    },
}


class TestStewardValidator(PluginTestHarness):
    # Validators are safe to ``apply()`` against test contracts (no side effects).
    skip_apply = False
    """Inherits ~13 conformance tests + adds domain-specific assertions below."""

    plugin_class = StewardValidator
    # Used by inherited harness tests — must include all the shapes we care about.
    sample_contracts = [
        MISSING_STEWARD_CONTRACT,
        NO_STEWARD_EMAIL_CONTRACT,
        COMPLIANT_CONTRACT,
    ]

    # ── domain-specific assertions ──────────────────────────────

    def test_missing_steward_emits_error(self) -> None:
        plugin = self.get_plugin()
        actions = plugin.plan(MISSING_STEWARD_CONTRACT)
        assert len(actions) == 1
        assert actions[0]["params"]["severity"] == "error"
        assert actions[0]["params"]["code"] == "STEWARD_ID_MISSING"
        # Result counts failed for error severity
        result = plugin.apply(actions)
        assert result.failed == 1
        assert result.applied == 0

    def test_missing_email_emits_warning_only(self) -> None:
        plugin = self.get_plugin()
        actions = plugin.plan(NO_STEWARD_EMAIL_CONTRACT)
        assert len(actions) == 1
        assert actions[0]["params"]["severity"] == "warn"
        result = plugin.apply(actions)
        assert result.failed == 0
        assert result.applied == 1

    def test_compliant_contract_produces_no_findings(self) -> None:
        plugin = self.get_plugin()
        actions = plugin.plan(COMPLIANT_CONTRACT)
        assert actions == []
        result = plugin.apply(actions)
        assert result.failed == 0
        assert result.applied == 0

    def test_remediation_is_helpful(self) -> None:
        plugin = self.get_plugin()
        actions = plugin.plan(MISSING_STEWARD_CONTRACT)
        remediation = actions[0]["params"]["remediation"]
        assert "steward" in remediation.lower()
        assert "metadata.labels" in remediation
