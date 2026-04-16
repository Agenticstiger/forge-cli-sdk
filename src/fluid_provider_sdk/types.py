# fluid_provider_sdk/types.py
"""Core types shared between providers and the FLUID CLI.

All types here are pure Python with zero external dependencies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Plan / Apply result types
# ---------------------------------------------------------------------------


@dataclass
class PlanAction:
    """Represents a planned infrastructure action."""

    action_type: str  # e.g. "create", "update", "grant"
    op: str  # e.g. "bq.ensure_dataset", "gcs.bucket"
    resource_id: str  # e.g. "my-dataset", "my-bucket"
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApplyResult:
    """Normalized result from ``provider.apply()``."""

    provider: str
    applied: int
    failed: int
    duration_sec: float
    timestamp: str
    results: List[Dict[str, Any]] = field(default_factory=list)

    # -- serialization -------------------------------------------------------

    def to_json(self) -> str:
        return json.dumps(
            {
                "provider": self.provider,
                "applied": self.applied,
                "failed": self.failed,
                "duration_sec": self.duration_sec,
                "timestamp": self.timestamp,
                "results": self.results,
            },
            indent=None,
        )

    # -- dict-compat helpers (backward compatibility with CLI code) ----------

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like ``get()`` for backward compatibility."""
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        """Dict-like ``[]`` access for backward compatibility."""
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        """Dict-like ``in`` operator for backward compatibility."""
        return hasattr(self, key)


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class ProviderError(RuntimeError):
    """Provider-specific user/action error (surface to user)."""


class ProviderInternalError(RuntimeError):
    """Provider bug or environment failure (not user fault)."""
