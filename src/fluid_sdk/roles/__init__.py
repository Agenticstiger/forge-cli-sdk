"""Role-specific helpers built on :class:`fluid_sdk.base.BasePlugin`.

Two role specialisations ship in the SDK because they include real
implementation logic plugins benefit from inheriting:

* :class:`CustomScaffold` — file generation. Provides a reference
  :meth:`apply` that writes ``write_file`` actions to disk atomically,
  with path-traversal protection and sha256 verification.
* :class:`Validator` — contract inspection. Provides a default
  :meth:`apply` that summarises emitted findings by severity (info /
  warn / error / critical) and counts errors as failures.

Plugins for other roles (cloud-infra providers, catalog adapters) subclass
:class:`BasePlugin` directly and set ``role = "provider"`` or
``role = "catalog"``.
"""

from .custom_scaffold import CustomScaffold, ScaffoldFile, write_file_action
from .validator import Finding, Validator

__all__ = [
    "CustomScaffold",
    "ScaffoldFile",
    "write_file_action",
    "Validator",
    "Finding",
]
