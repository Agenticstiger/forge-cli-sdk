"""The :class:`ExecutionResult` — normalised output of ``apply(actions)``.

Every plugin's ``apply()`` returns one of these, regardless of role.
The FLUID CLI uses ``applied`` / ``failed`` counts for status displays,
and the structured ``results`` list for audit trails and lineage capture.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ExecutionResult:
    """Normalised result from a plugin's ``apply()`` call.

    Fields:
        plugin: Stable plugin name (matches ``BasePlugin.name``).
        role: Plugin role (e.g. ``"provider"``, ``"custom_scaffold"``,
            ``"validator"``, ``"catalog"``).
        applied: Count of actions that completed successfully.
        failed: Count of actions that failed.
        duration_sec: Wall-clock execution time.
        timestamp: ISO-8601 timestamp of completion.
        results: Per-action result records. Each entry should at minimum
            include ``{"op": ..., "resource_id": ..., "status": ...}``
            where ``status`` is one of ``"ok"``, ``"failed"``, ``"skipped"``.
        artifacts: Optional list of paths/URIs produced (e.g. file paths
            written by a scaffold, audit logs, exported artifacts).
        warnings: Non-fatal messages worth surfacing.
    """

    plugin: str
    role: str = ""
    applied: int = 0
    failed: int = 0
    duration_sec: float = 0.0
    timestamp: str = ""
    results: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # ── Serialisation ──────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin": self.plugin,
            "role": self.role,
            "applied": self.applied,
            "failed": self.failed,
            "duration_sec": self.duration_sec,
            "timestamp": self.timestamp,
            "results": self.results,
            "artifacts": self.artifacts,
            "warnings": self.warnings,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=None)

    # ── Dict compatibility (legacy callers expect ``result["applied"]``) ──

    def __getitem__(self, key: str) -> Any:
        d = self.to_dict()
        if key in d:
            return d[key]
        raise KeyError(key)

    def __contains__(self, key: object) -> bool:
        return key in self.to_dict()

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    @property
    def is_success(self) -> bool:
        return self.failed == 0


__all__ = ["ExecutionResult"]
