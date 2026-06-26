"""Declared plugin capabilities — a small, typed self-description.

Every plugin advertises what it does via :meth:`BasePlugin.capabilities`. The
CLI and conformance harness read these flags to decide how to drive the plugin
(e.g. whether to prompt for credentials, whether a dry-run is available). Role
ABCs ship sensible defaults; plugins override only what differs.

This replaces the prose-only "capability defaults" the role docstrings used to
mention without any code behind them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class PluginCapabilities:
    """What a plugin can do. All flags default conservative (off)."""

    #: Renders/produces files on disk (scaffolds).
    render: bool = False
    #: Requires credentials / authenticated context (cloud, catalog APIs).
    auth: bool = False
    #: Supports streaming / incremental execution.
    streaming: bool = False
    #: Supports a side-effect-free dry-run of ``apply``.
    dry_run: bool = False
    #: ``apply`` is idempotent (safe to re-run).
    idempotent: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "render": self.render,
            "auth": self.auth,
            "streaming": self.streaming,
            "dry_run": self.dry_run,
            "idempotent": self.idempotent,
        }


__all__ = ["PluginCapabilities"]
