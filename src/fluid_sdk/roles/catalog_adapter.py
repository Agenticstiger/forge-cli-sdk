"""The :class:`CatalogAdapter` role — metadata-catalog sync plugins.

Catalog adapters push data-product metadata from a fluid contract into an
external catalog (DataHub, OpenMetadata, Atlan, …). They are registered under
the ``fluid_build.catalog_adapters`` entry-point group and invoked during the
publish/catalog phase.

Like :class:`InfraProvider`, this role ships **no reference ``apply``** — the
write is catalog-specific and network-bound. Subclasses implement :meth:`plan`
and :meth:`apply`; :func:`catalog_entry_action` builds the canonical action.

Example::

    from fluid_sdk import CatalogAdapter, ExecutionResult
    from fluid_sdk.roles import catalog_entry_action

    class DataHubAdapter(CatalogAdapter):
        name = "datahub"

        def plan(self, contract):
            return [
                catalog_entry_action(
                    entry_id=contract["id"],
                    properties={"description": contract.get("description", "")},
                ).to_dict()
            ]

        def apply(self, actions):
            ...  # emit to the catalog API, return an ExecutionResult

Register via entry-point::

    [project.entry-points."fluid_build.catalog_adapters"]
    datahub = "my_pkg.adapter:DataHubAdapter"
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional

from ..action import PHASE_CATALOG, PluginAction
from ..base import BasePlugin
from ..capabilities import PluginCapabilities


def catalog_entry_action(
    *,
    entry_id: str,
    properties: Optional[Mapping[str, Any]] = None,
    op: str = "register_catalog_entry",
    resource_type: str = "catalog_entry",
    depends_on: Optional[List[str]] = None,
    description: Optional[str] = None,
    tags: Optional[Mapping[str, str]] = None,
) -> PluginAction:
    """Construct a canonical catalog-registration action."""
    return PluginAction(
        op=op,
        resource_type=resource_type,
        resource_id=entry_id,
        params={"properties": dict(properties or {})},
        depends_on=list(depends_on or []),
        phase=PHASE_CATALOG,
        idempotent=True,
        description=description,
        tags=dict(tags or {}),
    )


class CatalogAdapter(BasePlugin):
    """Metadata-catalog sync plugin role.

    ``apply`` is left abstract so an adapter that forgets to implement it fails
    loudly rather than silently skipping the catalog write.
    """

    role = "catalog"

    # Catalog APIs are authenticated and network-bound; no file rendering.
    _capabilities = PluginCapabilities(render=False, auth=True)


__all__ = ["CatalogAdapter", "catalog_entry_action"]
