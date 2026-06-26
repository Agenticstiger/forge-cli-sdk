"""The :class:`InfraProvider` role — cloud-infrastructure plugins.

Infra providers provision real resources (datasets, tables, IAM, schedules)
from a fluid contract. They are dispatched by ``fluid apply`` and registered
under the ``fluid_build.providers`` entry-point group.

Unlike :class:`CustomScaffold` / :class:`Validator`, this role ships **no
reference ``apply``** — provisioning is platform-specific, and a default no-op
``apply`` would silently do nothing on ``fluid apply`` (the exact failure mode
this SDK exists to prevent). Subclasses MUST implement :meth:`plan` and
:meth:`apply`; :func:`provision_action` builds the canonical action shape.

Example::

    from fluid_sdk import InfraProvider, ExecutionResult
    from fluid_sdk.roles import provision_action

    class MyCloudProvider(InfraProvider):
        name = "mycloud"

        def plan(self, contract):
            return [
                provision_action(
                    op="create_dataset",
                    resource_type="dataset",
                    resource_id=contract["id"],
                    params={"location": "us"},
                ).to_dict()
            ]

        def apply(self, actions):
            ...  # call the cloud SDK, return an ExecutionResult

Register via entry-point::

    [project.entry-points."fluid_build.providers"]
    mycloud = "my_pkg.provider:MyCloudProvider"
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional

from ..action import PHASE_INFRASTRUCTURE, PluginAction
from ..base import BasePlugin
from ..capabilities import PluginCapabilities


def provision_action(
    *,
    op: str,
    resource_type: str,
    resource_id: str,
    params: Optional[Mapping[str, Any]] = None,
    depends_on: Optional[List[str]] = None,
    phase: str = PHASE_INFRASTRUCTURE,
    idempotent: bool = True,
    description: Optional[str] = None,
    tags: Optional[Mapping[str, str]] = None,
) -> PluginAction:
    """Construct a canonical infrastructure-provisioning action."""
    return PluginAction(
        op=op,
        resource_type=resource_type,
        resource_id=resource_id,
        params=dict(params or {}),
        depends_on=list(depends_on or []),
        phase=phase,
        idempotent=idempotent,
        description=description,
        tags=dict(tags or {}),
    )


class InfraProvider(BasePlugin):
    """Cloud-infrastructure provisioning plugin role.

    ``apply`` is intentionally left abstract (inherited from
    :class:`BasePlugin`) so a provider that forgets to implement it fails loudly
    at construction rather than silently no-op'ing a deployment.
    """

    role = "provider"

    # Providers need credentials and support a dry-run; they don't render files.
    _capabilities = PluginCapabilities(render=False, auth=True, dry_run=True)


__all__ = ["InfraProvider", "provision_action"]
