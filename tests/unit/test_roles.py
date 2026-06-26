"""Conformance + capability tests for all four roles.

The ``Test*`` harness subclasses below are collected by pytest, which then runs
every inherited ``test_*`` conformance method against the toy plugins — proving
the per-role harnesses are real and green, not just importable.
"""

from __future__ import annotations

from fluid_sdk import (
    CatalogAdapter,
    CustomScaffold,
    ExecutionResult,
    InfraProvider,
    PluginCapabilities,
    Validator,
    catalog_entry_action,
    provision_action,
)
from fluid_sdk.roles import Finding
from fluid_sdk.testing import (
    LOCAL_CONTRACT,
    MINIMAL_CONTRACT,
    CatalogAdapterTestHarness,
    InfraProviderTestHarness,
    ValidatorTestHarness,
)

# ---------------------------------------------------------------------------
# Toy plugins
# ---------------------------------------------------------------------------


class _ToyProvider(InfraProvider):
    name = "toy-cloud"

    def plan(self, contract):
        return [
            provision_action(
                op="create_dataset",
                resource_type="dataset",
                resource_id=str(contract.get("id", "ds")),
                params={"location": "us"},
            ).to_dict()
        ]

    def apply(self, actions):  # in-memory, never touches a cloud
        actions = list(actions)
        return ExecutionResult(plugin=self.name, role=self.role, applied=len(actions))


class _ToyCatalog(CatalogAdapter):
    name = "toy-catalog"

    def plan(self, contract):
        return [
            catalog_entry_action(
                entry_id=str(contract.get("id", "entry")),
                properties={"description": contract.get("description", "")},
            ).to_dict()
        ]

    def apply(self, actions):
        actions = list(actions)
        return ExecutionResult(plugin=self.name, role=self.role, applied=len(actions))


class _ToyValidator(Validator):
    name = "toy-rule"

    def plan(self, contract):
        if not (contract.get("metadata") or {}).get("owner"):
            return [
                Finding(severity="error", code="OWNER", message="no owner").to_action().to_dict()
            ]
        return [Finding(severity="info", code="OK", message="ok").to_action().to_dict()]


# ---------------------------------------------------------------------------
# Harness subclasses — pytest runs the full conformance suite on each
# ---------------------------------------------------------------------------


class TestToyProviderConformance(InfraProviderTestHarness):
    plugin_class = _ToyProvider
    sample_contracts = [MINIMAL_CONTRACT, LOCAL_CONTRACT]


class TestToyCatalogConformance(CatalogAdapterTestHarness):
    plugin_class = _ToyCatalog
    sample_contracts = [MINIMAL_CONTRACT, LOCAL_CONTRACT]


class TestToyValidatorConformance(ValidatorTestHarness):
    plugin_class = _ToyValidator
    sample_contracts = [MINIMAL_CONTRACT, LOCAL_CONTRACT]


# ---------------------------------------------------------------------------
# Capabilities defaults per role
# ---------------------------------------------------------------------------


def test_role_capability_defaults() -> None:
    assert CustomScaffold.capabilities() == PluginCapabilities(render=True)
    assert InfraProvider.capabilities() == PluginCapabilities(auth=True, dry_run=True)
    assert CatalogAdapter.capabilities() == PluginCapabilities(auth=True)
    # Validator inherits the conservative base default (read-only).
    assert Validator.capabilities().render is False
    assert Validator.capabilities().auth is False


def test_provider_apply_is_abstract_so_forgetting_it_fails_loudly() -> None:
    import pytest

    class _Broken(InfraProvider):
        name = "broken"

        def plan(self, contract):
            return []

        # no apply() → still abstract

    with pytest.raises(TypeError):
        _Broken()  # cannot instantiate an ABC with an unimplemented method
