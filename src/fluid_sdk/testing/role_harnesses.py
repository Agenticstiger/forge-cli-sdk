"""Role-specific conformance harnesses — one per role.

Each adds checks beyond the universal :class:`PluginTestHarness`:

* :class:`CustomScaffoldTestHarness` — byte-identical determinism, idempotency
  of repeated apply, path-traversal safety on every ``write_file`` action.
* :class:`ValidatorTestHarness` — findings carry a recognised severity; apply is
  exercised (validators are side-effect-free).
* :class:`InfraProviderTestHarness` — role/subclass conformance for cloud
  providers (apply is *not* run by default — it provisions real infra).
* :class:`CatalogAdapterTestHarness` — role/subclass conformance for catalog
  adapters (apply is *not* run by default — it writes to a live catalog).

Subclass the harness matching your plugin's role and set ``plugin_class``;
pytest auto-discovers every ``test_*`` method.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import ClassVar

from ..domains import Severity
from ..roles.catalog_adapter import CatalogAdapter
from ..roles.custom_scaffold import CustomScaffold
from ..roles.infra_provider import InfraProvider
from ..roles.validator import Validator
from .harness import PluginTestHarness, _as_action_dict


class CustomScaffoldTestHarness(PluginTestHarness):
    """Conformance harness for custom-scaffold plugins.

    Adds determinism + idempotency assertions and a path-traversal check
    against every generated ``write_file`` action.
    """

    #: Override to False if your scaffold writes outside an output_root tempdir.
    requires_output_root: ClassVar[bool] = True

    def test_role_is_custom_scaffold(self) -> None:
        assert (
            getattr(self.plugin_class, "role", "") == "custom_scaffold"
        ), "CustomScaffold plugins must declare role='custom_scaffold'"

    def test_is_custom_scaffold_subclass(self) -> None:
        assert issubclass(
            self.plugin_class, CustomScaffold
        ), f"{self.plugin_class.__name__} must subclass CustomScaffold"

    def test_actions_are_write_file_or_skip(self) -> None:
        if not self.sample_contracts:
            return
        prov = self.get_plugin()
        for contract in self.sample_contracts:
            for action in prov.plan(contract):
                op = action.get("op", "")
                assert op in (
                    "write_file",
                    "skip",
                ), f"CustomScaffold actions should be 'write_file' or 'skip', got {op!r}"

    def test_write_file_actions_have_content(self) -> None:
        if not self.sample_contracts:
            return
        prov = self.get_plugin()
        for contract in self.sample_contracts:
            for action in prov.plan(contract):
                if action.get("op") != "write_file":
                    continue
                params = action.get("params") or {}
                assert "path" in params, f"write_file action missing params.path: {action}"
                assert (
                    "content_b64" in params
                ), f"write_file action missing params.content_b64: {action}"

    def test_apply_writes_files_to_tempdir(self) -> None:
        """Apply must write every action's content to disk under output_root."""
        if not self.sample_contracts:
            return
        with tempfile.TemporaryDirectory() as tmp:
            prov = self.get_plugin(output_root=Path(tmp))
            for contract in self.sample_contracts:
                actions = prov.plan(contract)
                result = prov.apply(actions)
                expected_files = sum(1 for a in actions if a.get("op") == "write_file")
                assert result.applied == expected_files or result.failed == 0, (
                    f"apply() reported applied={result.applied} failed={result.failed} "
                    f"for {expected_files} write_file actions"
                )

    def test_apply_is_idempotent(self) -> None:
        """Re-applying the same actions twice must produce identical bytes on disk."""
        if not self.sample_contracts:
            return
        with tempfile.TemporaryDirectory() as tmp:
            prov = self.get_plugin(output_root=Path(tmp))
            for contract in self.sample_contracts:
                actions = prov.plan(contract)
                prov.apply(actions)
                first = {
                    str(p.relative_to(tmp)): p.read_bytes()
                    for p in Path(tmp).rglob("*")
                    if p.is_file()
                }
                prov.apply(actions)
                second = {
                    str(p.relative_to(tmp)): p.read_bytes()
                    for p in Path(tmp).rglob("*")
                    if p.is_file()
                }
                assert first == second, "Re-applying scaffold must be byte-identical"

    def test_no_path_traversal(self) -> None:
        """Every write_file action's path must stay inside output_root."""
        if not self.sample_contracts:
            return
        prov = self.get_plugin()
        for contract in self.sample_contracts:
            for action in prov.plan(contract):
                if action.get("op") != "write_file":
                    continue
                params = action.get("params") or {}
                path = str(params.get("path", ""))
                assert not path.startswith("/"), f"Absolute path forbidden: {path!r}"
                assert ".." not in path.split("/"), f"Path traversal forbidden: {path!r}"


class ValidatorTestHarness(PluginTestHarness):
    """Conformance harness for validator plugins.

    Validators are side-effect-free, so ``apply`` is exercised by default
    (``skip_apply = False``) — the universal ``test_apply_reflects_plan`` and
    ``test_apply_returns_execution_result`` checks run against fixtures.
    """

    skip_apply: ClassVar[bool] = False

    def test_role_is_validator(self) -> None:
        assert (
            getattr(self.plugin_class, "role", "") == "validator"
        ), "Validator plugins must declare role='validator'"

    def test_is_validator_subclass(self) -> None:
        assert issubclass(
            self.plugin_class, Validator
        ), f"{self.plugin_class.__name__} must subclass Validator"

    def test_findings_carry_recognised_severity(self) -> None:
        """Every emit_finding action's severity must be in the Severity domain.

        Catches typo'd severities (which would otherwise fail safe to ERROR and
        muddy the failure tally) at conformance time.
        """
        if not self.sample_contracts:
            return
        prov = self.get_plugin()
        for contract in self.sample_contracts:
            for action in prov.plan(contract):
                d = _as_action_dict(action)
                if d.get("op") != "emit_finding":
                    continue
                severity = (d.get("params") or {}).get("severity", "info")
                assert Severity.is_known(severity), (
                    f"finding {d.get('resource_id')!r} has unrecognised severity "
                    f"{severity!r} (expected one of {[s.value for s in Severity]})"
                )


class InfraProviderTestHarness(PluginTestHarness):
    """Conformance harness for cloud-infrastructure provider plugins.

    ``apply`` provisions real resources, so it is **not** run by default
    (``skip_apply = True``); the harness verifies role conformance and
    deterministic, well-formed plans.
    """

    skip_apply: ClassVar[bool] = True

    def test_role_is_provider(self) -> None:
        assert (
            getattr(self.plugin_class, "role", "") == "provider"
        ), "InfraProvider plugins must declare role='provider'"

    def test_is_infra_provider_subclass(self) -> None:
        assert issubclass(
            self.plugin_class, InfraProvider
        ), f"{self.plugin_class.__name__} must subclass InfraProvider"

    def test_provision_actions_have_resource_type(self) -> None:
        if not self.sample_contracts:
            return
        prov = self.get_plugin()
        for contract in self.sample_contracts:
            for action in prov.plan(contract):
                d = _as_action_dict(action)
                assert d.get("resource_type"), (
                    f"provider action {d.get('resource_id')!r} must declare a "
                    f"resource_type for dependency/diff tracking"
                )


class CatalogAdapterTestHarness(PluginTestHarness):
    """Conformance harness for metadata-catalog adapter plugins.

    ``apply`` writes to a live catalog, so it is **not** run by default
    (``skip_apply = True``).
    """

    skip_apply: ClassVar[bool] = True

    def test_role_is_catalog(self) -> None:
        assert (
            getattr(self.plugin_class, "role", "") == "catalog"
        ), "CatalogAdapter plugins must declare role='catalog'"

    def test_is_catalog_adapter_subclass(self) -> None:
        assert issubclass(
            self.plugin_class, CatalogAdapter
        ), f"{self.plugin_class.__name__} must subclass CatalogAdapter"


__all__ = [
    "CustomScaffoldTestHarness",
    "ValidatorTestHarness",
    "InfraProviderTestHarness",
    "CatalogAdapterTestHarness",
]
