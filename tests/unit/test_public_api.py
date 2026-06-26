"""Pin the public ``fluid_sdk`` API surface."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as dist_version

import pytest

import fluid_sdk

PROMISED_EXPORTS = {
    # ABCs (four roles)
    "BasePlugin",
    "CustomScaffold",
    "Validator",
    "InfraProvider",
    "CatalogAdapter",
    # Action + result
    "PluginAction",
    "ExecutionResult",
    "ScaffoldFile",
    "Finding",
    "PluginCapabilities",
    "validate_actions",
    "write_file_action",
    "provision_action",
    "catalog_entry_action",
    # Typed value domains
    "Severity",
    "ActionStatus",
    "Phase",
    "FAILING_SEVERITIES",
    # Extension-schema discovery
    "iter_extension_schemas",
    "EXTENSION_SCHEMAS_GROUP",
    # Errors
    "PluginError",
    "PluginInternalError",
    # Metadata
    "PluginMetadata",
    # Contract parsing
    "ContractHelper",
    "ExposeSpec",
    "ConsumeSpec",
    "BuildSpec",
    "ColumnSpec",
    # Phase constants
    "PHASE_INFRASTRUCTURE",
    "PHASE_IAM",
    "PHASE_BUILD",
    "PHASE_EXPOSE",
    "PHASE_SCHEDULE",
    "PHASE_VALIDATE",
    "PHASE_SCAFFOLD",
    "PHASE_CATALOG",
    "PHASE_DEFAULT",
    # Version + compatibility
    "SDK_VERSION",
    "SDK_PROTOCOL_VERSION",
    "MIN_CLI_VERSION",
    "MAX_CLI_VERSION",
    "cli_requirement",
}


def test_all_promised_exports_present() -> None:
    missing = PROMISED_EXPORTS - set(fluid_sdk.__all__)
    assert not missing, f"Missing from fluid_sdk.__all__: {missing}"


def test_all_exports_actually_importable() -> None:
    for name in fluid_sdk.__all__:
        assert hasattr(fluid_sdk, name), f"fluid_sdk.{name} is in __all__ but missing"


def test_role_classes_subclass_base_plugin() -> None:
    from fluid_sdk import BasePlugin, CatalogAdapter, CustomScaffold, InfraProvider, Validator

    for role_cls in (CustomScaffold, Validator, InfraProvider, CatalogAdapter):
        assert issubclass(role_cls, BasePlugin), f"{role_cls.__name__} must subclass BasePlugin"


def test_four_roles_have_distinct_canonical_tags() -> None:
    from fluid_sdk import CatalogAdapter, CustomScaffold, InfraProvider, Validator

    tags = {
        CustomScaffold.role,
        Validator.role,
        InfraProvider.role,
        CatalogAdapter.role,
    }
    assert tags == {"custom_scaffold", "validator", "provider", "catalog"}


def test_exports_match_all_strict() -> None:
    """No extras leak — only the promised exports."""
    extras = set(fluid_sdk.__all__) - PROMISED_EXPORTS
    assert not extras, f"Unexpected extras in fluid_sdk.__all__: {extras}"


def test_sdk_version_matches_pyproject() -> None:
    """``SDK_VERSION`` must equal the distribution version in pyproject.toml.

    Two sources of truth (``src/fluid_sdk/version.py::SDK_VERSION`` and
    ``[project.version]``) silently drift if not pinned. A user who reads
    ``fluid_sdk.__version__`` should see the same value pip just resolved.
    """
    try:
        installed = dist_version("data-product-forge-sdk")
    except PackageNotFoundError:
        # SDK not installed (e.g. tests run via PYTHONPATH from source) —
        # skip rather than fail, since there's nothing to compare against.
        pytest.skip("data-product-forge-sdk not installed as a distribution")
    assert (
        fluid_sdk.SDK_VERSION == installed
    ), f"SDK_VERSION={fluid_sdk.SDK_VERSION!r} drifted from pyproject version {installed!r}"
