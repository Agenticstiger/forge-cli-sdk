"""Universal conformance test harness for any :class:`BasePlugin` subclass.

Subclass in your plugin's test suite and set the required class
attributes. pytest auto-discovers every ``test_*`` method.

.. code-block:: python

    # tests/test_conformance.py
    from fluid_sdk.testing import PluginTestHarness, LOCAL_CONTRACT
    from my_pkg.plugin import MyPlugin

    class TestMyPlugin(PluginTestHarness):
        plugin_class = MyPlugin
        init_kwargs = {"project": "test-proj"}
        sample_contracts = [LOCAL_CONTRACT]

Override :attr:`skip_apply` to ``False`` if your plugin's ``apply()`` is
safe to run against test fixtures (e.g. scaffolds writing to a tempdir).
"""

from __future__ import annotations

import json
import re
from typing import Any, ClassVar, Dict, List, Type

from ..base import BasePlugin
from ..capabilities import PluginCapabilities


def _as_action_dict(action: Any) -> Dict[str, Any]:
    """Normalise an action (dict or PluginAction) to a plain dict."""
    if hasattr(action, "to_dict"):
        return action.to_dict()
    if isinstance(action, dict):
        return action
    raise AssertionError(f"action is neither a dict nor a PluginAction: {type(action).__name__}")


class PluginTestHarness:
    """Conformance test suite for any FLUID plugin.

    Required attributes (set in subclass):

    * ``plugin_class`` — the :class:`BasePlugin` subclass under test.

    Optional attributes:

    * ``init_kwargs`` — kwargs forwarded to the plugin constructor.
    * ``sample_contracts`` — contracts used in ``plan()`` tests.
    * ``skip_apply`` — when False, ``apply()`` is exercised. Default True
      because most cloud-infra ``apply()`` impls hit real infrastructure.
    """

    plugin_class: ClassVar[Type[BasePlugin]]
    init_kwargs: ClassVar[Dict[str, Any]] = {}
    sample_contracts: ClassVar[List[Dict[str, Any]]] = []
    skip_apply: ClassVar[bool] = True

    # ── helpers ──────────────────────────────────────────────────

    def get_plugin(self, **extra_kwargs: Any) -> BasePlugin:
        kw = {**self.init_kwargs, **extra_kwargs}
        return self.plugin_class(**kw)

    # ── identity tests ───────────────────────────────────────────

    def test_subclasses_base_plugin(self) -> None:
        assert issubclass(
            self.plugin_class, BasePlugin
        ), f"{self.plugin_class.__name__} must subclass BasePlugin"

    def test_name_is_valid(self) -> None:
        name = getattr(self.plugin_class, "name", None)
        assert name is not None, "Plugin must define a 'name' class attribute"
        assert re.match(
            r"^[a-z][a-z0-9_\-]*$", name
        ), f"Invalid plugin name: {name!r} (lowercase + underscores/hyphens)"

    def test_name_not_reserved(self) -> None:
        reserved = {"unknown", "stub", "base", "test", "none", "default"}
        name = getattr(self.plugin_class, "name", "")
        assert name not in reserved, f"Plugin name {name!r} is reserved"

    def test_role_declared(self) -> None:
        role = getattr(self.plugin_class, "role", None)
        assert role, "Plugin must define a 'role' class attribute"

    # ── constructor tests ────────────────────────────────────────

    def test_constructor_accepts_kwargs(self) -> None:
        prov = self.get_plugin()
        assert prov is not None

    def test_logger_is_set(self) -> None:
        prov = self.get_plugin()
        assert prov.logger is not None

    # ── plan tests ───────────────────────────────────────────────

    def test_plan_returns_list(self) -> None:
        if not self.sample_contracts:
            return
        prov = self.get_plugin()
        for contract in self.sample_contracts:
            result = prov.plan(contract)
            assert isinstance(
                result, list
            ), f"plan() must return a list, got {type(result).__name__}"

    def test_plan_actions_have_op(self) -> None:
        if not self.sample_contracts:
            return
        prov = self.get_plugin()
        for contract in self.sample_contracts:
            actions = prov.plan(contract)
            for action in actions:
                assert "op" in action, f"Action missing 'op': {action}"

    def test_plan_actions_have_resource_id(self) -> None:
        if not self.sample_contracts:
            return
        prov = self.get_plugin()
        for contract in self.sample_contracts:
            actions = prov.plan(contract)
            for action in actions:
                assert "resource_id" in action, f"Action missing 'resource_id': {action}"

    def test_plan_is_deterministic(self) -> None:
        """Same contract input ⇒ same action list. Critical for reproducibility."""
        if not self.sample_contracts:
            return
        prov = self.get_plugin()
        for contract in self.sample_contracts:
            first = prov.plan(contract)
            second = prov.plan(contract)
            assert first == second, "plan() must be deterministic — same input ⇒ same output"

    # ── metadata tests ───────────────────────────────────────────

    def test_get_plugin_info_exists(self) -> None:
        assert hasattr(
            self.plugin_class, "get_plugin_info"
        ), "Plugin must implement get_plugin_info() classmethod"

    def test_get_plugin_info_returns_metadata(self) -> None:
        if not hasattr(self.plugin_class, "get_plugin_info"):
            return
        info = self.plugin_class.get_plugin_info()
        assert info.name == self.plugin_class.name, (
            f"PluginMetadata.name ({info.name!r}) must match "
            f"plugin_class.name ({self.plugin_class.name!r})"
        )
        assert info.sdk_version, "PluginMetadata.sdk_version must be set"

    def test_get_plugin_info_declares_compat(self) -> None:
        """Metadata must declare the protocol generation + CLI requirement."""
        if not hasattr(self.plugin_class, "get_plugin_info"):
            return
        info = self.plugin_class.get_plugin_info()
        assert isinstance(
            getattr(info, "sdk_protocol_version", None), int
        ), "PluginMetadata.sdk_protocol_version must be an int (declared compat)"
        assert getattr(info, "requires_cli", None), "PluginMetadata.requires_cli must be set"

    # ── capabilities test ────────────────────────────────────────

    def test_capabilities_declared(self) -> None:
        """Plugin must declare typed capabilities via capabilities()."""
        caps = self.plugin_class.capabilities()
        assert isinstance(
            caps, PluginCapabilities
        ), "capabilities() must return a PluginCapabilities"
        # to_dict() round-trips the flag set (used by the CLI / marketplace).
        assert set(caps.to_dict()) == {"render", "auth", "streaming", "dry_run", "idempotent"}

    # ── serialisation test ───────────────────────────────────────

    def test_plan_actions_are_json_serialisable(self) -> None:
        """Every planned action must serialise to JSON (CLI plan/audit trail)."""
        if not self.sample_contracts:
            return
        prov = self.get_plugin()
        for contract in self.sample_contracts:
            for action in prov.plan(contract):
                json.dumps(_as_action_dict(action))

    # ── apply tests (opt-in) ─────────────────────────────────────

    def test_apply_returns_execution_result(self) -> None:
        if self.skip_apply or not self.sample_contracts:
            return
        prov = self.get_plugin()
        for contract in self.sample_contracts:
            actions = prov.plan(contract)
            result = prov.apply(actions)
            assert hasattr(
                result, "plugin"
            ), "apply() must return an ExecutionResult-like object with 'plugin' attr"
            assert hasattr(result, "applied"), "ExecutionResult must have 'applied'"
            assert hasattr(result, "failed"), "ExecutionResult must have 'failed'"

    def test_apply_reflects_plan(self) -> None:
        """apply() must account for every planned action (no silent drops).

        Opt-in: only runs when ``skip_apply`` is False (i.e. apply is safe to
        exercise against fixtures). Catches the 'plan emits N actions, apply
        silently handles fewer' class of bug.
        """
        if self.skip_apply or not self.sample_contracts:
            return
        prov = self.get_plugin()
        for contract in self.sample_contracts:
            actions = prov.plan(contract)
            result = prov.apply(actions)
            accounted = result.applied + result.failed + len(getattr(result, "results", []) or [])
            assert accounted >= len(actions) or len(getattr(result, "results", [])) == len(
                actions
            ), (
                f"apply() accounted for fewer actions than planned "
                f"(planned={len(actions)}, applied={result.applied}, failed={result.failed})"
            )
