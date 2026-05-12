"""
fluid-sdk — Zero-dependency SDK for building FLUID plugins.

Build a plugin once against this SDK, register it via Python entry-points,
and the FLUID CLI (``data-product-forge``) will discover and dispatch to it.
Two role specialisations ship with real implementation value:

* :class:`CustomScaffold` — file-emitting plugins (CI configs, app code,
  IaC stacks). Ships a reference :meth:`apply` that writes files atomically
  with path-traversal protection and sha256 verification.
* :class:`Validator` — contract-inspection plugins (governance / compliance
  rules). Ships a default :meth:`apply` that summarises findings by
  severity.

Plugins for other roles (cloud-infra providers, catalog adapters) subclass
:class:`BasePlugin` directly and set ``role = "provider"`` or
``role = "catalog"`` themselves.

Entry-point groups the FLUID CLI walks:

* ``fluid_build.custom_scaffolds`` — register :class:`CustomScaffold` plugins
* ``fluid_build.validators`` — register :class:`Validator` plugins
* ``fluid_build.providers`` — register cloud-infra providers
* ``fluid_build.catalog_adapters`` — register catalog adapters

This SDK has **zero external dependencies** beyond the Python standard
library. Install ``fluid-sdk`` and you can develop a plugin without
pulling the full FLUID CLI.

Public API::

    from fluid_sdk import (
        # ABCs
        BasePlugin,
        CustomScaffold,
        Validator,
        # Data types
        PluginAction,
        ExecutionResult,
        ScaffoldFile,
        Finding,
        # Errors
        PluginError,
        PluginInternalError,
        # Metadata
        PluginMetadata,
        # Contract parsing
        ContractHelper,
        ExposeSpec,
        ConsumeSpec,
        BuildSpec,
        ColumnSpec,
        # Helpers
        write_file_action,
        validate_actions,
        # Phase constants
        PHASE_INFRASTRUCTURE,
        PHASE_BUILD,
        PHASE_EXPOSE,
        PHASE_SCAFFOLD,
        PHASE_VALIDATE,
        PHASE_CATALOG,
        # Version
        SDK_VERSION,
    )
"""

from __future__ import annotations

# Core types
from .action import (
    PHASE_BUILD,
    PHASE_CATALOG,
    PHASE_DEFAULT,
    PHASE_EXPOSE,
    PHASE_IAM,
    PHASE_INFRASTRUCTURE,
    PHASE_SCAFFOLD,
    PHASE_SCHEDULE,
    PHASE_VALIDATE,
    PluginAction,
    validate_actions,
)
from .base import BasePlugin
from .contract import (
    BuildSpec,
    ColumnSpec,
    ConsumeSpec,
    ContractHelper,
    ExposeSpec,
)
from .error import PluginError, PluginInternalError
from .metadata import PluginMetadata
from .result import ExecutionResult

# Role helpers (ship with real implementation value)
from .roles import (
    CustomScaffold,
    Finding,
    ScaffoldFile,
    Validator,
    write_file_action,
)

# Version
from .version import SDK_VERSION

__version__ = SDK_VERSION

__all__ = [
    # ── ABCs ─────────────────────────────────────────────────────
    "BasePlugin",
    "CustomScaffold",
    "Validator",
    # ── Action + result ──────────────────────────────────────────
    "PluginAction",
    "ExecutionResult",
    "ScaffoldFile",
    "Finding",
    "validate_actions",
    "write_file_action",
    # ── Errors ───────────────────────────────────────────────────
    "PluginError",
    "PluginInternalError",
    # ── Metadata ─────────────────────────────────────────────────
    "PluginMetadata",
    # ── Contract parsing ─────────────────────────────────────────
    "ContractHelper",
    "ExposeSpec",
    "ConsumeSpec",
    "BuildSpec",
    "ColumnSpec",
    # ── Phase constants ──────────────────────────────────────────
    "PHASE_INFRASTRUCTURE",
    "PHASE_IAM",
    "PHASE_BUILD",
    "PHASE_EXPOSE",
    "PHASE_SCHEDULE",
    "PHASE_VALIDATE",
    "PHASE_SCAFFOLD",
    "PHASE_CATALOG",
    "PHASE_DEFAULT",
    # ── Version ──────────────────────────────────────────────────
    "SDK_VERSION",
]
