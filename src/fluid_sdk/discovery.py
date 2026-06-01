"""Discovery of plugin-registered ``contract.extensions.<key>`` JSON schemas.

A plugin advertises the JSON-Schema for its ``contract.extensions.<key>`` block
by registering a *provider* under the ``fluid_build.extension_schemas``
entry-point group, keyed by the extension sub-key::

    [project.entry-points."fluid_build.extension_schemas"]
    customScaffold = "my_pkg.schemas:get_extension_schema"

where the provider has the signature ``get_extension_schema(fluid_version=None)
-> dict`` and returns a JSON Schema (draft-07) describing the data *under* the
extension key (this mirrors ``validate-pyproject``'s ``tool_schema`` convention,
and complements the existing ``fluid_build.extension_validators`` group).

:func:`iter_extension_schemas` walks that group with per-plugin error isolation
and returns ``{extension_key: schema}``. The ``data-product-forge`` CLI copilot
uses this to **ground contract generation** on the installed extension schemas
and to **validate** the generated ``extensions.<key>`` blocks — so any plugin
that advertises a schema is handled natively, with no CLI change per extension.

Zero external dependencies (stdlib only), consistent with the rest of this SDK.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

#: The entry-point group plugins register their extension-schema providers under.
EXTENSION_SCHEMAS_GROUP = "fluid_build.extension_schemas"

logger = logging.getLogger(__name__)


def iter_extension_schemas(
    fluid_version: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Return ``{extension_key: json_schema}`` for every installed provider.

    Per-plugin error isolation: a provider that fails to load, raises, or
    returns a non-dict is skipped (a warning is logged with the entry-point
    name and the exception *type* only — never the message, so a provider that
    raises with a secret in its error text cannot leak it through this SDK's
    logs). One broken provider never drops the others, and the call never
    raises to the caller. Returns ``{}`` when no providers are installed (the
    backward-compatible no-op path).

    ``fluid_version`` is forwarded to providers that accept it; providers that
    take no argument are still supported.

    Note:
        Hosts that have a secret redactor (e.g. the ``data-product-forge`` CLI)
        typically wrap discovery with their own redaction in addition to the
        type-only logging here.
    """
    import importlib.metadata as md

    try:
        try:
            eps = md.entry_points(group=EXTENSION_SCHEMAS_GROUP)
        except TypeError:  # pragma: no cover — Python < 3.10 signature
            eps = md.entry_points().get(EXTENSION_SCHEMAS_GROUP, [])
    except Exception as e:  # discovery itself failed — fail open
        logger.warning("extension-schema discovery failed: %s", type(e).__name__)
        return {}

    schemas: Dict[str, Dict[str, Any]] = {}
    for ep in eps:
        try:
            provider = ep.load()
            try:
                schema = provider(fluid_version)
            except TypeError:
                # Provider declared no parameter — call it with none.
                schema = provider()
        except Exception as e:
            logger.warning(
                "extension-schema provider %r failed to load/run: %s",
                ep.name,
                type(e).__name__,
            )
            continue
        if not isinstance(schema, dict):
            logger.warning("extension-schema provider %r returned a non-dict; skipping", ep.name)
            continue
        schemas[ep.name] = schema
    return schemas
