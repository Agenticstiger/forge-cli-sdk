"""
Standardised action schema for provider plan/apply pipelines.

Every provider's ``plan()`` can return a mix of raw dicts **and**
``ProviderAction`` instances — both are accepted by the framework.
``ProviderAction`` adds validation, dependency tracking, and a stable
serialisation format.

Usage::

    from fluid_provider_sdk import ProviderAction, validate_actions

    actions = [
        ProviderAction(
            op="create_dataset",
            resource_type="dataset",
            resource_id="crypto_data",
            params={"project": "my-proj", "location": "US"},
            phase="infrastructure",
        ),
        ProviderAction(
            op="create_table",
            resource_type="table",
            resource_id="bitcoin_prices",
            params={"dataset": "crypto_data", "schema": [...]},
            depends_on=["crypto_data"],
            phase="expose",
        ),
    ]
    errors = validate_actions(actions)
    assert errors == []  # valid
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class ProviderAction:
    """Standardised action — the common language between ``plan()`` and ``apply()``.

    Attributes:
        op:            Operation verb, e.g. ``"create_dataset"``, ``"grant_access"``.
        resource_type: Logical resource kind, e.g. ``"dataset"``, ``"table"``, ``"role"``.
        resource_id:   Unique identifier within this plan (used for dependency edges).
        params:        Provider-specific parameters for the operation.
        depends_on:    List of ``resource_id`` values that must execute first.
        phase:         Execution phase grouping.  Common values:
                       ``"infrastructure"``, ``"iam"``, ``"build"``, ``"expose"``,
                       ``"schedule"``, ``"test"``, ``"default"``.
        idempotent:    Whether this action is safe to retry.
        description:   Human-readable summary for plan output.
        tags:          Optional metadata tags for filtering / reporting.
    """

    op: str
    resource_type: str = ""
    resource_id: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    phase: str = "default"
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
        if self.phase != "default":
            d["phase"] = self.phase
        if not self.idempotent:
            d["idempotent"] = False
        if self.description:
            d["description"] = self.description
        if self.tags:
            d["tags"] = dict(self.tags)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProviderAction":
        """Reconstruct from a plain dict.

        Unrecognised keys are placed in ``params`` so that legacy action
        dicts (which store everything at the top level) round-trip cleanly.
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
            op=d.get("op", ""),
            resource_type=d.get("resource_type", ""),
            resource_id=d.get("resource_id", ""),
            params=params,
            depends_on=list(d.get("depends_on") or []),
            phase=d.get("phase", "default"),
            idempotent=d.get("idempotent", True),
            description=d.get("description"),
            tags=dict(d.get("tags") or {}),
        )

    # ── Dict compatibility ─────────────────────────────────────────
    # So that existing code doing ``action["op"]`` keeps working when
    # a ``ProviderAction`` is passed where a dict was expected.

    def __getitem__(self, key: str) -> Any:
        d = self.to_dict()
        return d[key]

    def __contains__(self, key: object) -> bool:
        return key in self.to_dict()

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)


# ── Validation ─────────────────────────────────────────────────────


def validate_actions(actions: Sequence[ProviderAction]) -> List[str]:
    """Return a list of validation errors (empty = valid).

    Checks:
    - Every action has a non-empty ``op``.
    - Every action has a non-empty ``resource_id``.
    - No duplicate ``resource_id`` values.
    - ``depends_on`` references exist within the action set.
    """
    errors: List[str] = []
    all_ids: set[str] = set()
    seen_ids: set[str] = set()

    # First pass: collect all resource_ids
    for a in actions:
        if a.resource_id:
            all_ids.add(a.resource_id)

    # Second pass: validate
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
