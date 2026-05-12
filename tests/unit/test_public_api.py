"""Pin the public ``fluid_sdk`` API surface."""

from __future__ import annotations

import fluid_sdk

PROMISED_EXPORTS = {
    # ABCs
    "BasePlugin",
    "CustomScaffold",
    "Validator",
    # Action + result
    "PluginAction",
    "ExecutionResult",
    "ScaffoldFile",
    "Finding",
    "validate_actions",
    "write_file_action",
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
    # Version
    "SDK_VERSION",
}


def test_all_promised_exports_present() -> None:
    missing = PROMISED_EXPORTS - set(fluid_sdk.__all__)
    assert not missing, f"Missing from fluid_sdk.__all__: {missing}"


def test_all_exports_actually_importable() -> None:
    for name in fluid_sdk.__all__:
        assert hasattr(fluid_sdk, name), f"fluid_sdk.{name} is in __all__ but missing"


def test_role_classes_subclass_base_plugin() -> None:
    from fluid_sdk import BasePlugin, CustomScaffold, Validator

    for role_cls in (CustomScaffold, Validator):
        assert issubclass(role_cls, BasePlugin), f"{role_cls.__name__} must subclass BasePlugin"


def test_exports_match_all_strict() -> None:
    """No extras leak — only the promised exports."""
    extras = set(fluid_sdk.__all__) - PROMISED_EXPORTS
    assert not extras, f"Unexpected extras in fluid_sdk.__all__: {extras}"
