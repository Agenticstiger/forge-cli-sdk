"""The :class:`CustomScaffold` role — file-emitting plugins.

This is the role for plugins that generate files into a workspace from a
fluid contract: CI definitions, application code, per-environment config,
IaC stacks, anything that needs to live on disk.

Compared to :class:`InfraProvider`, the semantic differences are:

* **Output kind**: actions emit files (``op="write_file"``), not cloud
  resources.
* **Lifecycle**: invoked via ``fluid generate <scaffold-name>`` (or
  ``fluid generate custom-scaffold`` for the canonical engine), not via
  ``fluid apply``.
* **Determinism**: scaffolds MUST be byte-deterministic across runs given
  identical contract input. The conformance harness asserts this.
* **Apply phase**: writes files to disk. No network. Idempotent (overwrite
  with the same bytes is a no-op).

The lifecycle and ABC are identical to :class:`BasePlugin`; only the
helpers and capability defaults differ.

Example::

    from fluid_sdk.roles import CustomScaffold, ScaffoldFile, write_file_action
    from fluid_sdk import ExecutionResult

    class MyCIScaffold(CustomScaffold):
        name = "my-ci-scaffold"

        def plan(self, contract):
            ci_yaml = self._render_ci(contract)
            return [
                write_file_action(
                    path=".gitlab-ci.yml",
                    content=ci_yaml.encode("utf-8"),
                    resource_id="gitlab-ci-yml",
                ).to_dict(),
            ]

        def apply(self, actions):
            ...

Register via entry-point::

    [project.entry-points."fluid_build.custom_scaffolds"]
    my-ci = "my_pkg.scaffold:MyCIScaffold"
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from ..action import PHASE_SCAFFOLD, PluginAction
from ..base import BasePlugin
from ..capabilities import PluginCapabilities
from ..domains import ActionStatus
from ..error import PluginError
from ..result import ExecutionResult

# ---------------------------------------------------------------------------
# ScaffoldFile — typed convenience over PluginAction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScaffoldFile:
    """A single rendered file ready to be written to disk.

    Most scaffold plugins build a list of these, then convert each to a
    ``write_file`` :class:`PluginAction` via :func:`write_file_action`.
    """

    path: str  # destination path relative to output root
    content: bytes
    mode: int = 0o644
    description: Optional[str] = None
    tags: Mapping[str, str] = field(default_factory=dict)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


def write_file_action(
    *,
    path: str,
    content: bytes,
    resource_id: Optional[str] = None,
    mode: int = 0o644,
    description: Optional[str] = None,
    depends_on: Optional[List[str]] = None,
    tags: Optional[Mapping[str, str]] = None,
) -> PluginAction:
    """Construct a canonical ``write_file`` action.

    The action stores file bytes (base64-encoded for JSON-safety in
    ``params.content_b64``) plus the destination path, mode, and an
    integrity hash. Apply implementations write the bytes to disk.
    """
    import base64

    rid = resource_id or path
    params: Dict[str, Any] = {
        "path": path,
        "content_b64": base64.b64encode(content).decode("ascii"),
        "mode": mode,
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
    }
    return PluginAction(
        op="write_file",
        resource_type="file",
        resource_id=rid,
        params=params,
        depends_on=list(depends_on or []),
        phase=PHASE_SCAFFOLD,
        idempotent=True,
        description=description,
        tags=dict(tags or {}),
    )


# ---------------------------------------------------------------------------
# CustomScaffold ABC
# ---------------------------------------------------------------------------


class CustomScaffold(BasePlugin):
    """File-emitting plugin role.

    Provides:

    * ``role = "custom_scaffold"`` — drives entry-point group selection.
    * Capability defaults tuned for scaffold flows (``render=True``,
      ``auth=False``, ``streaming=False``).
    * A reference :meth:`apply` implementation that writes ``write_file``
      actions to disk safely (path-traversal guarded, parent-dirs created,
      atomic via temp-file rename).

    Subclasses can override :meth:`apply` entirely; the default just
    materialises ``write_file`` actions.
    """

    role = "custom_scaffold"

    # Scaffolds render files to disk; no credentials, no streaming.
    _capabilities = PluginCapabilities(render=True, auth=False, streaming=False)

    def __init__(
        self,
        *,
        output_root: Optional[Path] = None,
        project: Optional[str] = None,
        region: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(project=project, region=region, logger=logger, **kwargs)
        self.output_root: Path = Path(output_root or Path.cwd()).resolve()

    # ── Default apply: materialise write_file actions to disk ─────

    def apply(self, actions: Iterable[Mapping[str, Any]]) -> ExecutionResult:
        """Reference implementation: walk ``write_file`` actions and write
        each to disk under :attr:`output_root`, atomically and with
        path-traversal protection.

        Plugins that need different semantics (e.g. dry-run, in-memory
        capture, archive output) override this entirely.
        """
        import base64

        started = time.monotonic()
        applied = 0
        failed = 0
        artifacts: List[str] = []
        results: List[Dict[str, Any]] = []
        warnings: List[str] = []

        for action in actions:
            op = action.get("op", "")
            rid = action.get("resource_id", "")
            params = action.get("params") or {}
            try:
                if op != "write_file":
                    warnings.append(f"ignoring unsupported op={op!r} (resource_id={rid!r})")
                    results.append(
                        {"op": op, "resource_id": rid, "status": ActionStatus.SKIPPED.value}
                    )
                    continue

                rel_path = params.get("path", "")
                content_b64 = params.get("content_b64", "")
                mode = int(params.get("mode", 0o644))
                expected_sha = params.get("sha256")

                if not rel_path:
                    raise PluginError(f"write_file action {rid!r} missing params.path")
                if not isinstance(content_b64, str):
                    raise PluginError(f"write_file action {rid!r} content_b64 must be a string")

                target = (self.output_root / rel_path).resolve()
                # Path-traversal guard: target must remain inside output_root.
                if os.path.commonpath([str(target), str(self.output_root)]) != str(
                    self.output_root
                ):
                    raise PluginError(
                        f"write_file action {rid!r} target {rel_path!r} escapes output root"
                    )

                target.parent.mkdir(parents=True, exist_ok=True)
                payload = base64.b64decode(content_b64)
                if expected_sha:
                    actual_sha = hashlib.sha256(payload).hexdigest()
                    if actual_sha != expected_sha:
                        raise PluginError(
                            f"write_file action {rid!r} sha256 mismatch "
                            f"(plan={expected_sha} apply={actual_sha})"
                        )

                # Atomic write: tmp file + rename.
                tmp = target.with_suffix(target.suffix + ".tmp~")
                tmp.write_bytes(payload)
                os.chmod(tmp, mode)
                os.replace(tmp, target)

                applied += 1
                artifacts.append(str(target))
                results.append(
                    {
                        "op": op,
                        "resource_id": rid,
                        "status": ActionStatus.OK.value,
                        "path": rel_path,
                    }
                )
            except Exception as e:
                failed += 1
                results.append(
                    {
                        "op": op,
                        "resource_id": rid,
                        "status": ActionStatus.FAILED.value,
                        "error": str(e),
                    }
                )
                self.err_kv(event="apply_failed", resource_id=rid, error=str(e))

        return ExecutionResult(
            plugin=self.name,
            role=self.role,
            applied=applied,
            failed=failed,
            duration_sec=round(time.monotonic() - started, 4),
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            results=results,
            artifacts=artifacts,
            warnings=warnings,
        )


__all__ = ["CustomScaffold", "ScaffoldFile", "write_file_action"]
