"""Role-specific helpers built on :class:`fluid_sdk.base.BasePlugin`.

Seven roles ship in the SDK. Four are ABCs over :class:`fluid_sdk.base.BasePlugin` (one mental
model, one ABC per role):

* :class:`CustomScaffold` — file generation. Provides a reference
  :meth:`apply` that writes ``write_file`` actions to disk atomically,
  with path-traversal protection and sha256 verification.
* :class:`Validator` — contract inspection. Provides a default
  :meth:`apply` that summarises emitted findings by severity (info /
  warn / error / critical) and counts errors as failures.
* :class:`InfraProvider` — cloud-infrastructure provisioning. ``apply`` is
  abstract (platform-specific); :func:`provision_action` builds the action.
* :class:`CatalogAdapter` — metadata-catalog sync. ``apply`` is abstract
  (catalog-specific); :func:`catalog_entry_action` builds the action.

Three more describe the plugin groups forge-cli 0.38.0 adds. They have no ``plan`` /
``apply``: forge-cli reads a few attributes (or calls one method) on any object, so they are
plain classes with forge-cli's own names and signatures.

* :class:`AlertNotifier` — an alert route kind for generated DAGs
  (``fluid_build.alert_notifiers``); :func:`alert_route` builds an entry of
  ``fluid_build.alert_defaults``.
* :class:`MaintenanceAction` — a step of an Iceberg table's maintenance that returns SQL
  (``fluid_build.maintenance_actions``).
* :class:`CommandPlugin` — an extra ``fluid <name>`` subcommand (``fluid_build.commands``).

Each BasePlugin role sets a canonical ``role`` tag that drives entry-point group selection
and CLI dispatch, and declares default :meth:`~fluid_sdk.base.BasePlugin.capabilities`.
"""

from .alert_notifier import (
    Alert,
    AlertNotifier,
    AlertRoute,
    NotifierCall,
    alert_route,
    check_alert_route,
)
from .catalog_adapter import CatalogAdapter, catalog_entry_action
from .command_plugin import CommandPlugin
from .custom_scaffold import CustomScaffold, ScaffoldFile, write_file_action
from .infra_provider import InfraProvider, provision_action
from .maintenance_action import MaintenanceAction, sql_literal
from .validator import Finding, Validator

__all__ = [
    "CustomScaffold",
    "ScaffoldFile",
    "write_file_action",
    "Validator",
    "Finding",
    "InfraProvider",
    "provision_action",
    "CatalogAdapter",
    "catalog_entry_action",
    "AlertNotifier",
    "AlertRoute",
    "Alert",
    "NotifierCall",
    "alert_route",
    "check_alert_route",
    "MaintenanceAction",
    "sql_literal",
    "CommandPlugin",
]
