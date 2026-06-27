"""SDK version + plugin↔CLI compatibility declaration.

``SDK_VERSION`` is kept in sync with ``[project.version]`` in pyproject.toml.
If you bump one, bump the other. ``tests/unit/test_public_api.py`` pins that
invariant.

**Compatibility (declare-and-gate).** A plugin built against this SDK declares
which FLUID CLI versions it speaks to; the CLI gates at load time. We borrow
dbt's ``require-dbt-version`` model: the *plugin* declares, the *host* enforces
(https://docs.getdbt.com/reference/project-configs/require-dbt-version). The SDK
exposes the declaration only — it stays stdlib-only and does no version maths;
the CLI (which already depends on ``packaging``) does the ``SpecifierSet`` check.

* ``SDK_PROTOCOL_VERSION`` — the plugin-interface generation. Bump **only** on a
  breaking change to ``BasePlugin`` / the role contracts. The CLI advertises the
  protocol generations it supports; a plugin carries the one it was built
  against in ``PluginMetadata.sdk_protocol_version``.
* ``MIN_CLI_VERSION`` / ``MAX_CLI_VERSION`` — the CLI version window this SDK's
  protocol is known to work with (read by the CLI's compat check off the
  ``fluid_sdk`` module). ``MAX_CLI_VERSION = None`` means "no known upper bound".
* ``cli_requirement()`` — the same window as a PEP 440 specifier string, the
  default for ``PluginMetadata.requires_cli`` when a plugin doesn't override it.
"""

from __future__ import annotations

from typing import Optional

SDK_VERSION = "0.10.0"

#: Plugin-interface protocol generation. Bump only on a breaking interface change.
SDK_PROTOCOL_VERSION = 1

#: CLI version window this SDK's protocol is known to work with.
MIN_CLI_VERSION: str = "0.7.0"
MAX_CLI_VERSION: Optional[str] = None  # open-ended


def cli_requirement() -> str:
    """Return the CLI compatibility window as a PEP 440 specifier string.

    Example: ``">=0.7.0"`` (or ``">=0.7.0,<2.0.0"`` once an upper bound is set).
    Used as the default ``PluginMetadata.requires_cli`` and gated by the CLI.
    """
    spec = f">={MIN_CLI_VERSION}"
    if MAX_CLI_VERSION:
        spec += f",<{MAX_CLI_VERSION}"
    return spec
