"""Role-specific helpers built on :class:`fluid_sdk.base.BasePlugin`.

Four role specialisations ship in the SDK — one mental model, one ABC per role:

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

Each role sets a canonical ``role`` tag that drives entry-point group selection
and CLI dispatch, and declares default :meth:`~fluid_sdk.base.BasePlugin.capabilities`.
"""

from .catalog_adapter import CatalogAdapter, catalog_entry_action
from .custom_scaffold import CustomScaffold, ScaffoldFile, write_file_action
from .infra_provider import InfraProvider, provision_action
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
]
