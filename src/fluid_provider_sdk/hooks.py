# fluid_provider_sdk/hooks.py
"""Lifecycle hooks for FLUID providers.

Providers can implement these hooks by subclassing ``ProviderHookSpec``
(or mixing it into their ``BaseProvider`` subclass).  Every method is a
no-op by default so providers only override what they need.

CLI integration points call hooks at:

    pre_plan  -> provider.plan()  -> post_plan
    pre_apply -> provider.apply() -> post_apply
                                      on_error  (on failure)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

# ---------------------------------------------------------------------------
# Cost estimation data class
# ---------------------------------------------------------------------------


@dataclass
class CostEstimate:
    """Estimated cost for a set of planned actions."""

    currency: str = "USD"
    monthly: float = 0.0
    one_time: float = 0.0
    breakdown: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""

    def total(self) -> float:
        return self.monthly + self.one_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "currency": self.currency,
            "monthly": self.monthly,
            "one_time": self.one_time,
            "total": self.total(),
            "breakdown": self.breakdown,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Hook specification
# ---------------------------------------------------------------------------


class ProviderHookSpec:
    """Optional lifecycle hooks a provider can implement.

    All methods are no-ops by default.  Override only what you need.
    The CLI calls hooks at the documented lifecycle points — providers
    that don't subclass ``ProviderHookSpec`` simply skip hook invocation.
    """

    # -- plan lifecycle -----------------------------------------------------

    def pre_plan(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        """Called before ``plan()``.  May modify/enrich the contract.

        Return the (possibly modified) contract dict.
        """
        return contract

    def post_plan(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Called after ``plan()`` with the generated action list.

        May filter, reorder, or annotate actions.
        Return the (possibly modified) action list.
        """
        return actions

    # -- apply lifecycle ----------------------------------------------------

    def pre_apply(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Called before ``apply()``.  Last chance to modify actions.

        Return the (possibly modified) action list.
        """
        return actions

    def post_apply(self, result: Mapping[str, Any]) -> None:
        """Called after a successful ``apply()``.

        Use for notifications, lineage capture, audit logging, etc.
        """

    def on_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """Called when ``plan()`` or ``apply()`` raises an exception.

        *context* contains ``{"phase": "plan"|"apply", ...}`` plus
        any additional info the CLI can provide.
        """

    # -- optional advanced hooks -------------------------------------------

    def estimate_cost(self, actions: List[Dict[str, Any]]) -> Optional[CostEstimate]:
        """Return a cost estimate for *actions*, or ``None`` if unsupported."""
        return None

    def validate_sovereignty(self, contract: Dict[str, Any]) -> List[str]:
        """Check data-sovereignty / residency constraints.

        Return a list of violation messages (empty == pass).
        """
        return []


# ---------------------------------------------------------------------------
# Hook invocation helpers (used by CLI)
# ---------------------------------------------------------------------------


def invoke_hook(provider: Any, hook_name: str, *args: Any, **kwargs: Any) -> Any:
    """Safely invoke a lifecycle hook on *provider* if it exists.

    Returns the hook's return value, or the first positional arg
    (pass-through) if the provider doesn't implement the hook.
    """
    method = getattr(provider, hook_name, None)
    if method is None:
        # Provider doesn't implement this hook — pass through
        return args[0] if args else None
    try:
        return method(*args, **kwargs)
    except Exception:
        # Hook failures must never break the core plan/apply flow.
        # The CLI should log but continue.
        return args[0] if args else None


def has_hook(provider: Any, hook_name: str) -> bool:
    """Return ``True`` if *provider* implements the named hook."""
    method = getattr(provider, hook_name, None)
    if method is None:
        return False
    # Check it's not just the no-op default from ProviderHookSpec
    if isinstance(provider, ProviderHookSpec):
        default = getattr(ProviderHookSpec, hook_name, None)
        return method.__func__ is not default  # type: ignore[union-attr]
    return True
