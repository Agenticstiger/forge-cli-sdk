"""Role-specific conformance harnesses.

Only :class:`CustomScaffoldTestHarness` ships here — it adds checks that
genuinely differ from the universal :class:`PluginTestHarness` (byte-identical
determinism, idempotency of repeated apply, path-traversal safety on every
write_file action).

For other roles (cloud-infra providers, validators, catalog adapters), the
universal :class:`PluginTestHarness` is sufficient — add domain-specific
``test_*`` methods directly in your plugin's test file.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import ClassVar

from ..roles.custom_scaffold import CustomScaffold
from .harness import PluginTestHarness


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


__all__ = ["CustomScaffoldTestHarness"]
