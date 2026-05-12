"""The universal :class:`BasePlugin` ABC.

Every FLUID plugin — regardless of role — implements this ABC:

* ``plan(contract)`` → deterministic, normalised list of action dicts
* ``apply(actions)`` → :class:`ExecutionResult`
* ``get_plugin_info()`` → :class:`PluginMetadata` *(classmethod, optional)*

Role-specific subclasses in :mod:`fluid_sdk.roles` provide tighter
conventions and helper methods on top of this ABC:

* :class:`fluid_sdk.roles.CustomScaffold` — file generation (ships a
  reference :meth:`apply` that writes files atomically with
  path-traversal protection and sha256 verification)
* :class:`fluid_sdk.roles.Validator` — contract inspection (ships a
  default :meth:`apply` that summarises findings by severity)

Plugins for other roles (cloud providers, catalog adapters, etc.)
subclass :class:`BasePlugin` directly and set ``role = "..."``.

Design principles:

* Defer heavyweight imports to methods so CLI startup stays cheap.
* Raise :class:`PluginError` for user/contract issues;
  :class:`PluginInternalError` for bugs / environment failures.
* Keep logging structured (JSON-friendly); the CLI controls verbosity
  and handlers.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .error import PluginError
from .metadata import PluginMetadata
from .result import ExecutionResult
from .version import SDK_VERSION

# ---------------------------------------------------------------------------
# Logger helper
# ---------------------------------------------------------------------------


def _mk_logger(name: str, passed: Optional[logging.Logger] = None) -> logging.Logger:
    """Return a configured logger, falling back to a JSON-formatted stream."""
    if passed:
        return passed
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                '{"time": "%(asctime)s", "level": "%(levelname)s", '
                '"name": "%(name)s", "message": "%(message)s"}'
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# ---------------------------------------------------------------------------
# BasePlugin
# ---------------------------------------------------------------------------


class BasePlugin(ABC):
    """Universal FLUID plugin ABC.

    Subclasses define a stable :attr:`name`, a :attr:`role` tag, and
    implement :meth:`plan` and :meth:`apply`.
    """

    #: Stable, lowercase, identifier-shaped name. Override in subclasses.
    name: str = "unknown"

    #: Role tag — drives entry-point group selection and CLI filtering.
    #: Example values: ``"provider"``, ``"custom_scaffold"``, ``"validator"``,
    #: ``"catalog"``.
    role: str = "plugin"

    def __init__(
        self,
        *,
        project: Optional[str] = None,
        region: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        **kwargs: Any,
    ) -> None:
        self.project = project
        self.region = region
        self.logger = _mk_logger(self.__class__.__module__, logger)
        self.extra: Dict[str, Any] = dict(kwargs)

    # ── identity ────────────────────────────────────────────────────

    @classmethod
    def get_plugin_info(cls) -> PluginMetadata:
        """Return descriptive metadata for registry / marketplace UIs.

        Override to provide rich info::

            @classmethod
            def get_plugin_info(cls):
                return PluginMetadata(
                    name="mycloud",
                    role="provider",
                    description="FLUID provider for MyCloud",
                    version="1.2.0",
                    author="MyCloud Inc.",
                    tags=["lakehouse", "delta"],
                )
        """
        return PluginMetadata(
            name=cls.name,
            role=cls.role,
            display_name=cls.name.replace("_", " ").replace("-", " ").title(),
            description="",
            version="0.0.0",
            sdk_version=SDK_VERSION,
            author="Unknown",
        )

    # ── plan / apply (required) ─────────────────────────────────────

    @abstractmethod
    def plan(self, contract: Mapping[str, Any]) -> List[Dict[str, Any]]:
        """Produce a deterministic, normalised action list from *contract*.

        Actions must be:

        * Deterministic — same input ⇒ same output (no clock / random).
        * Idempotent where possible (``action.idempotent=True``).
        * Stable-ordered — running ``plan()`` twice yields byte-identical
          output. Tests assert this.
        """

    @abstractmethod
    def apply(self, actions: Iterable[Mapping[str, Any]]) -> ExecutionResult:
        """Execute *actions* (idempotent where possible).

        Return an :class:`ExecutionResult` with per-action status records.
        Raise :class:`PluginError` for user-actionable failures (auth, quota,
        contract issues); :class:`PluginInternalError` for bugs.
        """

    # ── helpers & guardrails ────────────────────────────────────────

    def require(self, cond: bool, msg: str) -> None:
        """Raise :class:`PluginError` if *cond* is false. Logs first."""
        if not cond:
            self.logger.error("precondition_failed: %s", msg)
            raise PluginError(msg)

    def _log_kv(self, level: int, **kv: Any) -> None:
        try:
            self.logger.log(level, json.dumps(kv))
        except Exception:
            self.logger.log(level, str(kv))

    def debug_kv(self, **kv: Any) -> None:
        self._log_kv(logging.DEBUG, **kv)

    def info_kv(self, **kv: Any) -> None:
        self._log_kv(logging.INFO, **kv)

    def warn_kv(self, **kv: Any) -> None:
        self._log_kv(logging.WARNING, **kv)

    def err_kv(self, **kv: Any) -> None:
        self._log_kv(logging.ERROR, **kv)


__all__ = ["BasePlugin"]
