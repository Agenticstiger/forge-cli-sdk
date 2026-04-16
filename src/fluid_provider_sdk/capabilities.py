# fluid_provider_sdk/capabilities.py
"""Typed capabilities for FLUID providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ProviderCapabilities:
    """Structured capability flags advertised by a provider.

    Providers return this from ``capabilities()`` instead of a raw dict.
    The class is backward-compatible: it can be iterated and accessed like
    a ``Mapping[str, bool]``.
    """

    # Core
    planning: bool = True
    apply: bool = True
    render: bool = False
    graph: bool = False
    auth: bool = False

    # Advanced (Phase 4)
    dry_run: bool = False
    rollback: bool = False
    cost_estimation: bool = False
    schema_validation: bool = False
    lineage: bool = False
    streaming: bool = False

    # Extension point — providers can declare custom capabilities here.
    extra: Dict[str, bool] = field(default_factory=dict)

    # -- Mapping-like interface for backward compatibility ------------------

    def _as_dict(self) -> Dict[str, bool]:
        d: Dict[str, bool] = {
            "planning": self.planning,
            "apply": self.apply,
            "render": self.render,
            "graph": self.graph,
            "auth": self.auth,
            "dry_run": self.dry_run,
            "rollback": self.rollback,
            "cost_estimation": self.cost_estimation,
            "schema_validation": self.schema_validation,
            "lineage": self.lineage,
            "streaming": self.streaming,
        }
        d.update(self.extra)
        return d

    def __getitem__(self, key: str) -> bool:
        d = self._as_dict()
        return d[key]

    def __contains__(self, key: object) -> bool:
        return key in self._as_dict()

    def __iter__(self):
        return iter(self._as_dict())

    def __len__(self) -> int:
        return len(self._as_dict())

    def get(self, key: str, default: bool = False) -> bool:
        return self._as_dict().get(key, default)

    def items(self):
        return self._as_dict().items()

    def keys(self):
        return self._as_dict().keys()

    def values(self):
        return self._as_dict().values()
