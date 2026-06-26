"""Unit tests for the plugin↔CLI compatibility declaration surface.

The SDK only *declares* compatibility (stdlib-only, no version maths); the CLI
gates. These tests pin the declaration the CLI reads.
"""

from __future__ import annotations

import fluid_sdk
from fluid_sdk import (
    MAX_CLI_VERSION,
    MIN_CLI_VERSION,
    SDK_PROTOCOL_VERSION,
    BasePlugin,
    PluginMetadata,
    cli_requirement,
)


def test_module_exposes_min_max_cli_version_for_the_cli_reader() -> None:
    # The CLI's compat check reads these attributes off the `fluid_sdk` module.
    assert isinstance(fluid_sdk.MIN_CLI_VERSION, str) and fluid_sdk.MIN_CLI_VERSION
    assert fluid_sdk.MAX_CLI_VERSION is None or isinstance(fluid_sdk.MAX_CLI_VERSION, str)


def test_protocol_version_is_a_positive_int() -> None:
    assert isinstance(SDK_PROTOCOL_VERSION, int) and SDK_PROTOCOL_VERSION >= 1


def test_cli_requirement_is_a_pep440_specifier_string() -> None:
    req = cli_requirement()
    assert req.startswith(">=")
    assert MIN_CLI_VERSION in req
    if MAX_CLI_VERSION:
        assert f"<{MAX_CLI_VERSION}" in req


def test_metadata_defaults_carry_compat_fields() -> None:
    md = PluginMetadata(name="x", role="provider")
    assert md.sdk_protocol_version == SDK_PROTOCOL_VERSION
    # requires_cli inherits the SDK default when not overridden.
    assert md.requires_cli == cli_requirement()
    d = md.to_dict()
    assert d["sdk_protocol_version"] == SDK_PROTOCOL_VERSION
    assert d["requires_cli"] == cli_requirement()


def test_metadata_requires_cli_is_overridable() -> None:
    md = PluginMetadata(name="x", requires_cli=">=1.0,<2.0")
    assert md.requires_cli == ">=1.0,<2.0"


def test_default_get_plugin_info_declares_protocol() -> None:
    class _Toy(BasePlugin):
        name = "toy"
        role = "provider"

        def plan(self, contract):
            return []

        def apply(self, actions):
            from fluid_sdk import ExecutionResult

            return ExecutionResult(plugin=self.name)

    info = _Toy.get_plugin_info()
    assert info.sdk_protocol_version == SDK_PROTOCOL_VERSION
    assert info.sdk_version == fluid_sdk.SDK_VERSION
    # The default metadata inherits the SDK CLI requirement.
    assert info.requires_cli == cli_requirement()
