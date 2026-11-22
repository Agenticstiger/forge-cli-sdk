"""
fluid-sdk — Zero-dependency SDK for building FLUID plugins.

Build a plugin once against this SDK, register it via Python entry-points,
and the FLUID CLI (``data-product-forge``) discovers and dispatches to it.
Seven roles ship — one ``role`` tag each. Four are ABCs over :class:`BasePlugin`:

* :class:`CustomScaffold` — file-emitting plugins (CI configs, app code,
  IaC stacks). Ships a reference :meth:`apply` that writes files atomically
  with path-traversal protection and sha256 verification.
* :class:`Validator` — contract-inspection plugins (governance / compliance
  rules). Ships a default :meth:`apply` that summarises findings by severity.
* :class:`InfraProvider` — cloud-infrastructure provisioning. ``apply`` is
  abstract (platform-specific); use :func:`provision_action` to build actions.
* :class:`CatalogAdapter` — metadata-catalog sync. ``apply`` is abstract
  (catalog-specific); use :func:`catalog_entry_action` to build actions.

Three more describe the plugin groups forge-cli 0.38.0 adds. They have no ``plan`` /
``apply``: forge-cli reads forge-cli's own attributes and methods from any object.

* :class:`AlertNotifier` — an alert route kind for generated DAGs; :func:`alert_route`
  builds a default route for an organisation's pack.
* :class:`MaintenanceAction` — a step of an Iceberg table's maintenance that returns SQL.
* :class:`CommandPlugin` — an extra ``fluid <name>`` subcommand.

Each BasePlugin role declares typed :meth:`~fluid_sdk.base.BasePlugin.capabilities` and a
plugin↔CLI compatibility window the CLI gates at load (see :mod:`fluid_sdk.version`).

Entry-point groups the FLUID CLI walks (one per role):

* ``fluid_build.custom_scaffolds`` — register :class:`CustomScaffold` plugins
* ``fluid_build.validators`` — register :class:`Validator` plugins
* ``fluid_build.providers`` — register cloud-infra providers
* ``fluid_build.catalog_adapters`` — register catalog adapters
* ``fluid_build.alert_notifiers`` — register :class:`AlertNotifier` kinds (forge-cli 0.38.0+)
* ``fluid_build.alert_defaults`` — register an organisation's default alert routes (0.38.0+)
* ``fluid_build.maintenance_actions`` — register :class:`MaintenanceAction` kinds (0.38.0+)
* ``fluid_build.commands`` — register :class:`CommandPlugin` subcommands (0.8.3+)
* ``fluid_build.extension_schemas`` — register a JSON-Schema provider for a
  ``contract.extensions.<key>`` block so the CLI copilot can natively generate
  and validate it (see :func:`iter_extension_schemas`)

This SDK has **zero external dependencies** beyond the Python standard
library. Install ``fluid-sdk`` and you can develop a plugin without
pulling the full FLUID CLI.

Public API::

    from fluid_sdk import (
        # ABCs — four roles, one mental model
        BasePlugin,
        CustomScaffold,
        Validator,
        InfraProvider,
        CatalogAdapter,
        # Plain roles for the forge-cli 0.38.0 groups
        AlertNotifier,
        MaintenanceAction,
        CommandPlugin,
        # Data types
        PluginAction,
        ExecutionResult,
        ScaffoldFile,
        Finding,
        # Typed value domains
        Severity,
        ActionStatus,
        Phase,
        FAILING_SEVERITIES,
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
        # Extension-schema discovery
        iter_extension_schemas,
        EXTENSION_SCHEMAS_GROUP,
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

# Capabilities (typed plugin self-description)
from .capabilities import PluginCapabilities
from .contract import (
    BuildSpec,
    ColumnSpec,
    ConsumeSpec,
    ContractHelper,
    ExposeSpec,
)

# Extension-schema discovery (for the CLI copilot + plugin authors)
from .discovery import EXTENSION_SCHEMAS_GROUP, iter_extension_schemas

# Typed value domains (severity / status / phase)
from .domains import (
    FAILING_SEVERITIES,
    ActionStatus,
    Phase,
    Severity,
)
from .error import PluginError, PluginInternalError
from .metadata import PluginMetadata
from .result import ExecutionResult

# Role helpers — seven roles
from .roles import (
    Alert,
    AlertNotifier,
    AlertRoute,
    CatalogAdapter,
    CommandPlugin,
    CustomScaffold,
    Finding,
    InfraProvider,
    MaintenanceAction,
    NotifierCall,
    ScaffoldFile,
    Validator,
    alert_route,
    catalog_entry_action,
    check_alert_route,
    provision_action,
    sql_literal,
    write_file_action,
)

# Version + plugin↔CLI compatibility declaration
from .version import (
    MAX_CLI_VERSION,
    MIN_CLI_VERSION,
    SDK_PROTOCOL_VERSION,
    SDK_VERSION,
    cli_requirement,
)

__version__ = SDK_VERSION

__all__ = [
    # ── ABCs (four BasePlugin roles) ─────────────────────────────
    "BasePlugin",
    "CustomScaffold",
    "Validator",
    "InfraProvider",
    "CatalogAdapter",
    # ── Plain roles (no plan/apply): the forge-cli 0.38.0 groups ──
    "AlertNotifier",
    "AlertRoute",
    "Alert",
    "NotifierCall",
    "alert_route",
    "check_alert_route",
    "MaintenanceAction",
    "sql_literal",
    "CommandPlugin",
    # ── Action + result ──────────────────────────────────────────
    "PluginAction",
    "ExecutionResult",
    "ScaffoldFile",
    "Finding",
    "PluginCapabilities",
    "validate_actions",
    "write_file_action",
    "provision_action",
    "catalog_entry_action",
    # ── Typed value domains ──────────────────────────────────────
    "Severity",
    "ActionStatus",
    "Phase",
    "FAILING_SEVERITIES",
    # ── Extension-schema discovery ───────────────────────────────
    "iter_extension_schemas",
    "EXTENSION_SCHEMAS_GROUP",
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
    # ── Version + compatibility ──────────────────────────────────
    "SDK_VERSION",
    "SDK_PROTOCOL_VERSION",
    "MIN_CLI_VERSION",
    "MAX_CLI_VERSION",
    "cli_requirement",
]
