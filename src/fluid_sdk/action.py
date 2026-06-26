"""The :class:`PluginAction` data class — the universal action shape.

Every FLUID plugin, regardless of role (infrastructure provider, custom
scaffold generator, validator, catalog adapter), produces a deterministic
list of *actions* from ``plan(contract)``.  The FLUID CLI then either
executes them via ``apply(actions)`` or surfaces them for review.

An action is intentionally generic:

* ``op`` is a free-form verb string (``"create_table"``, ``"write_file"``,
  ``"register_catalog_entry"``, ``"validate"``, …).
* ``resource_id`` uniquely identifies the action's target inside the plan
  (used for dependency edges).
* ``depends_on`` lists ``resource_id`` values that must finish first.
* ``phase`` groups actions for ordered execution.

A plugin role may convention-restrict ``op`` to specific values (e.g.
``CustomScaffold`` instances emit ``op="write_file"``) but the data class
itself does not enforce a closed enumeration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .domains import Phase

# ---------------------------------------------------------------------------
# Standard phase names — now members of the :class:`Phase` domain enum.
#
# These ``PHASE_*`` constants are kept as the ergonomic, back-compatible spelling
# (``phase=PHASE_BUILD``). Each is a ``Phase`` member, and because ``Phase`` is a
# ``str``-enum every existing comparison and serialisation keeps working:
# ``PHASE_BUILD == "build"`` and ``json.dumps(PHASE_BUILD) == '"build"'``.
# ---------------------------------------------------------------------------

PHASE_INFRASTRUCTURE = Phase.INFRASTRUCTURE
PHASE_IAM = Phase.IAM
PHASE_BUILD = Phase.BUILD
PHASE_EXPOSE = Phase.EXPOSE
PHASE_SCHEDULE = Phase.SCHEDULE
PHASE_VALIDATE = Phase.VALIDATE
PHASE_SCAFFOLD = Phase.SCAFFOLD
PHASE_CATALOG = Phase.CATALOG
PHASE_DEFAULT = Phase.DEFAULT


# ---------------------------------------------------------------------------
# PluginAction
# ---------------------------------------------------------------------------


@dataclass
class PluginAction:
    """A single, planned, deterministic operation produced by a plugin.

    Fields:
        op: Operation verb. Free-form. Examples:
            ``"create_dataset"``, ``"write_file"``, ``"validate_schema"``,
            ``"register_table"``.
        resource_type: Logical kind of target (``"dataset"``, ``"file"``,
            ``"schema"``, ``"role"``).
        resource_id: Unique-within-plan identifier. Used as dependency key.
        params: Operation-specific parameters. Free-form mapping.
        depends_on: ``resource_id`` values that must execute first.
        phase: Execution-phase grouping (see ``PHASE_*`` constants).
        idempotent: Whether the action is safe to retry as-is.
        description: Human-readable summary for plan output.
        tags: Arbitrary metadata tags for filtering / reporting.
    """

    op: str
    resource_type: str = ""
    resource_id: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    # Annotated Union[Phase, str]: `from_dict` normalises into a Phase member, but
    # the constructor also accepts a plain str (a plugin may invent a phase name).
    phase: Union[Phase, str] = PHASE_DEFAULT
    idempotent: bool = True
    description: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)

    # ── Serialisation ──────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (the format ``apply()`` already accepts)."""
        d: Dict[str, Any] = {"op": self.op}
        if self.resource_type:
            d["resource_type"] = self.resource_type
        if self.resource_id:
            d["resource_id"] = self.resource_id
        if self.params:
            d["params"] = self.params
        if self.depends_on:
            d["depends_on"] = list(self.depends_on)
        if self.phase != PHASE_DEFAULT:
            d["phase"] = self.phase
        if not self.idempotent:
            d["idempotent"] = False
        if self.description:
            d["description"] = self.description
        if self.tags:
            d["tags"] = dict(self.tags)
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "PluginAction":
        """Reconstruct from a plain dict.

        Unknown keys are placed into ``params`` so legacy action dicts that
        store everything at the top level round-trip cleanly.
        """
        known = {
            "op",
            "resource_type",
            "resource_id",
            "params",
            "depends_on",
            "phase",
            "idempotent",
            "description",
            "tags",
        }
        extra = {k: v for k, v in d.items() if k not in known}
        params = dict(d.get("params") or {})
        params.update(extra)
        return cls(
            op=str(d.get("op", "")),
            resource_type=str(d.get("resource_type", "")),
            resource_id=str(d.get("resource_id", "")),
            params=params,
            depends_on=list(d.get("depends_on") or []),
            # Normalise into the closed Phase domain (was a bare str) so a
            # round-tripped action carries a real Phase member, not free text.
            phase=Phase.coerce(d.get("phase", PHASE_DEFAULT)),
            idempotent=bool(d.get("idempotent", True)),
            description=d.get("description"),
            tags=dict(d.get("tags") or {}),
        )

    # ── Dict compatibility (so callers reading ``action["op"]`` keep
    #    working when a PluginAction is passed where a dict was expected) ──

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def __contains__(self, key: object) -> bool:
        return key in self.to_dict()

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_actions(actions: Sequence[PluginAction]) -> List[str]:
    """Static validation of an action list.

    Returns a list of error messages; an empty list means the actions are
    structurally sound. Checks:

    * Every action has a non-empty ``op``.
    * Every action has a non-empty ``resource_id``.
    * No duplicate ``resource_id`` values.
    * Every ``depends_on`` reference resolves within the same plan.

    Note: this is *static* validation only — runtime errors (network,
    auth, quota) surface during ``apply()``.
    """
    errors: List[str] = []
    all_ids: set[str] = set()
    seen_ids: set[str] = set()

    for a in actions:
        if a.resource_id:
            all_ids.add(a.resource_id)

    for i, a in enumerate(actions):
        if not a.op:
            errors.append(f"Action [{i}] missing 'op'")
        if not a.resource_id:
            errors.append(f"Action [{i}] (op={a.op!r}) missing 'resource_id'")
        elif a.resource_id in seen_ids:
            errors.append(f"Duplicate resource_id: {a.resource_id!r}")
        seen_ids.add(a.resource_id)
        for dep in a.depends_on:
            if dep not in all_ids:
                errors.append(f"Action {a.resource_id!r} depends on unknown {dep!r}")
    return errors


__all__ = [
    "PluginAction",
    "validate_actions",
    "Phase",
    "PHASE_INFRASTRUCTURE",
    "PHASE_IAM",
    "PHASE_BUILD",
    "PHASE_EXPOSE",
    "PHASE_SCHEDULE",
    "PHASE_VALIDATE",
    "PHASE_SCAFFOLD",
    "PHASE_CATALOG",
    "PHASE_DEFAULT",
]
