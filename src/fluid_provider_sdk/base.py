# fluid_provider_sdk/base.py
"""BaseProvider ABC — the contract all FLUID providers implement."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .capabilities import ProviderCapabilities
from .metadata import ProviderMetadata
from .types import ApplyResult, ProviderError
from .version import SDK_VERSION

# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------


def _mk_logger(name: str, passed: Optional[logging.Logger] = None) -> logging.Logger:
    if passed:
        return passed
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = logging.Formatter(
            fmt='{"time": "%(asctime)s", "level": "%(levelname)s", '
            '"name": "%(name)s", "message": "%(message)s"}'
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# ---------------------------------------------------------------------------
# BaseProvider
# ---------------------------------------------------------------------------


class BaseProvider(ABC):
    """Minimal provider lifecycle:

    - ``plan(contract)`` → list of actions
    - ``apply(actions)`` → ``ApplyResult``
    - ``render(src, out=..., fmt=...)`` → artifact *(optional)*
    - ``capabilities()`` → feature flags
    - ``get_provider_info()`` → ``ProviderMetadata`` *(classmethod, optional)*

    Design principles:

    * Defer heavyweight imports to methods (not module-level).
    * Raise ``ProviderError`` for user/action issues;
      ``ProviderInternalError`` for bugs/env.
    * Keep logging structured; let CLI control verbosity/handlers.
    """

    # Stable provider name — override in subclass.
    name: str = "unknown"

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

    # ---------- identity & feature flags ----------

    def capabilities(self) -> Mapping[str, bool]:
        """Feature support advertised by the provider.

        Returns either a plain ``dict`` or a
        :class:`~fluid_provider_sdk.capabilities.ProviderCapabilities` instance
        (which behaves like a dict).
        """
        return ProviderCapabilities()

    @classmethod
    def get_provider_info(cls) -> ProviderMetadata:
        """Return descriptive metadata for registry/marketplace UIs.

        Override in subclasses to provide richer info::

            @classmethod
            def get_provider_info(cls):
                return ProviderMetadata(
                    name="mycloud",
                    description="FLUID provider for MyCloud",
                    version="1.2.0",
                    author="MyCloud Inc.",
                    tags=["lakehouse", "delta"],
                )
        """
        return ProviderMetadata(
            name=cls.name,
            display_name=cls.name.replace("_", " ").title(),
            description="",
            version="0.0.0",
            sdk_version=SDK_VERSION,
            author="Unknown",
        )

    # ---------- planning & application ----------

    @abstractmethod
    def plan(self, contract: Mapping[str, Any]) -> List[Dict[str, Any]]:
        """Produce a list of deterministic, normalized actions."""

    @abstractmethod
    def apply(self, actions: Iterable[Mapping[str, Any]]) -> ApplyResult:
        """Execute actions (idempotent where possible)."""

    # ---------- rendering/exports (optional) ----------

    def render(
        self,
        src: Mapping[str, Any] | Sequence[Mapping[str, Any]],
        *,
        out: Optional[Path | str] = None,
        fmt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Optional exporter to materialize an artifact (e.g., OPDS)."""
        raise ProviderError(
            f"{getattr(self, 'name', self.__class__.__name__)}: render() not supported"
        )

    # ---------- helpers & guardrails ----------

    def require(self, cond: bool, msg: str) -> None:
        """Raise ``ProviderError`` if *cond* is false."""
        if not cond:
            self.logger.error("precondition_failed: %s", msg)
            raise ProviderError(msg)

    def debug_kv(self, **kv: Any) -> None:
        try:
            self.logger.debug(json.dumps(kv))
        except Exception:
            self.logger.debug(str(kv))

    def info_kv(self, **kv: Any) -> None:
        try:
            self.logger.info(json.dumps(kv))
        except Exception:
            self.logger.info(str(kv))

    def warn_kv(self, **kv: Any) -> None:
        try:
            self.logger.warning(json.dumps(kv))
        except Exception:
            self.logger.warning(str(kv))

    def err_kv(self, **kv: Any) -> None:
        try:
            self.logger.error(json.dumps(kv))
        except Exception:
            self.logger.error(str(kv))
