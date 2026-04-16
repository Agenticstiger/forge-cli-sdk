"""
Provider conformance test harness.

Subclass ``ProviderTestHarness`` in your provider's test suite and set the
required class attributes.  All ``test_*`` methods are automatically picked
up by **pytest**.

Usage::

    # tests/test_conformance.py
    from fluid_provider_sdk.testing import ProviderTestHarness, LOCAL_CONTRACT
    from my_provider import MyProvider

    class TestMyProvider(ProviderTestHarness):
        provider_class = MyProvider
        init_kwargs = {"project": "test-proj"}
        sample_contracts = [LOCAL_CONTRACT]
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, ClassVar, Dict, List, Type

from ..base import BaseProvider


class ProviderTestHarness:
    """Conformance test suite for FLUID providers.

    Override the class-level attributes in your subclass:

    * ``provider_class`` – the ``BaseProvider`` subclass to test (required)
    * ``init_kwargs``     – keyword arguments passed to the constructor
    * ``sample_contracts`` – list of contract dicts used for ``plan()`` tests
    * ``skip_apply``      – set to ``True`` if ``apply()`` talks to real infra
    """

    provider_class: ClassVar[Type[BaseProvider]]
    init_kwargs: ClassVar[Dict[str, Any]] = {}
    sample_contracts: ClassVar[List[Dict[str, Any]]] = []
    skip_apply: ClassVar[bool] = True

    # ── helpers ──────────────────────────────────────────────────

    def get_provider(self, **extra_kwargs: Any) -> BaseProvider:
        """Instantiate the provider under test."""
        kw = {**self.init_kwargs, **extra_kwargs}
        return self.provider_class(**kw)

    # ── identity tests ───────────────────────────────────────────

    def test_subclasses_base_provider(self) -> None:
        assert issubclass(
            self.provider_class, BaseProvider
        ), f"{self.provider_class.__name__} must subclass BaseProvider"

    def test_name_is_valid(self) -> None:
        name = getattr(self.provider_class, "name", None)
        assert name is not None, "Provider must define a 'name' class attribute"
        assert re.match(
            r"^[a-z][a-z0-9_]*$", name
        ), f"Invalid provider name: {name!r} (must be lowercase alphanumeric + underscores)"

    def test_name_not_reserved(self) -> None:
        reserved = {"unknown", "stub", "base", "test", "none", "default"}
        name = getattr(self.provider_class, "name", "")
        assert name not in reserved, f"Provider name {name!r} is reserved"

    # ── constructor tests ────────────────────────────────────────

    def test_constructor_accepts_kwargs(self) -> None:
        """Provider can be instantiated with the declared init_kwargs."""
        prov = self.get_provider()
        assert prov is not None

    def test_logger_is_set(self) -> None:
        prov = self.get_provider()
        assert prov.logger is not None

    # ── capabilities tests ───────────────────────────────────────

    def test_capabilities_returns_mapping(self) -> None:
        prov = self.get_provider()
        caps = prov.capabilities()
        assert isinstance(
            caps, Mapping
        ), f"capabilities() must return a Mapping, got {type(caps).__name__}"
        assert "planning" in caps
        assert "apply" in caps

    def test_capabilities_values_are_bool(self) -> None:
        prov = self.get_provider()
        caps = prov.capabilities()
        for key in ("planning", "apply"):
            assert isinstance(caps[key], bool), f"capabilities()[{key!r}] must be bool"

    # ── plan tests ───────────────────────────────────────────────

    def test_plan_returns_list(self) -> None:
        if not self.sample_contracts:
            return  # skip if no samples provided
        prov = self.get_provider()
        for contract in self.sample_contracts:
            result = prov.plan(contract)
            assert isinstance(
                result, list
            ), f"plan() must return a list, got {type(result).__name__}"

    def test_plan_actions_have_op(self) -> None:
        if not self.sample_contracts:
            return
        prov = self.get_provider()
        for contract in self.sample_contracts:
            actions = prov.plan(contract)
            for action in actions:
                assert "op" in action, f"Action missing 'op' key: {action}"

    def test_plan_actions_have_resource_id(self) -> None:
        if not self.sample_contracts:
            return
        prov = self.get_provider()
        for contract in self.sample_contracts:
            actions = prov.plan(contract)
            for action in actions:
                assert (
                    "resource_id" in action
                ), f"Action missing 'resource_id' key: {action}"

    # ── metadata tests ───────────────────────────────────────────

    def test_get_provider_info_exists(self) -> None:
        assert hasattr(
            self.provider_class, "get_provider_info"
        ), "Provider must implement get_provider_info() classmethod"

    def test_get_provider_info_returns_metadata(self) -> None:
        if not hasattr(self.provider_class, "get_provider_info"):
            return
        info = self.provider_class.get_provider_info()
        assert info.name == self.provider_class.name, (
            f"ProviderMetadata.name ({info.name!r}) must match "
            f"provider_class.name ({self.provider_class.name!r})"
        )
        assert info.sdk_version, "ProviderMetadata.sdk_version must be set"

    def test_get_provider_info_has_description(self) -> None:
        if not hasattr(self.provider_class, "get_provider_info"):
            return
        info = self.provider_class.get_provider_info()
        assert info.description, "ProviderMetadata should include a description"

    # ── apply tests (opt-in) ─────────────────────────────────────

    def test_apply_returns_apply_result(self) -> None:
        """Only runs if ``skip_apply`` is False and sample contracts exist."""
        if self.skip_apply or not self.sample_contracts:
            return
        prov = self.get_provider()
        for contract in self.sample_contracts:
            actions = prov.plan(contract)
            result = prov.apply(actions)
            assert hasattr(
                result, "provider"
            ), "apply() must return an ApplyResult-like object with 'provider' attr"
