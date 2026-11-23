"""The names forge-cli's own commands take, vendored so the SDK can refuse a plugin that uses one.

Source: the top-level subcommands and aliases of ``fluid_build.cli.build_parser()`` at forge-cli
commit ``cc52b755`` (the v0.38.0 release; main when this was written). forge-cli 0.39.0 refuses
a ``fluid_build.commands`` plugin that registers one of these names, with a typed error: it skips
that plugin and loads the others, on every supported Python. Before that, argparse let the last
registration win on Python 3.10 and raised on 3.11 and later.

forge-cli is the authority. A command a later forge-cli adds is not in this list until the list
is regenerated, so a name that passes here can still be refused there. Regenerate it with
``list(subparsers.choices)`` of the top-level subparsers action of ``build_parser()``, and
update this header with the new commit.
"""

from __future__ import annotations

from typing import FrozenSet

#: Every top-level command name and alias of forge-cli (aliases such as ``dmm`` included).
FORGE_CORE_COMMANDS: FrozenSet[str] = frozenset(
    {
        "agents",
        "ai",
        "apply",
        "auth",
        "bundle",
        "config",
        "contract",
        "contract-tests",
        "contract-validation",
        "datamesh-manager",
        "demo",
        "describe",
        "diff",
        "dmm",
        "docs",
        "doctor",
        "export",
        "export-opds",
        "exporters",
        "forge",
        "generate",
        "generate-airflow",
        "genie",
        "ide",
        "import",
        "init",
        "market",
        "marketplace",
        "mcp",
        "odcs",
        "odps",
        "odps-bitol",
        "opds",
        "plan",
        "plugins",
        "policy",
        "policy-apply",
        "policy-check",
        "policy-compile",
        "product-add",
        "product-new",
        "profile",
        "provider-init",
        "providers",
        "publish",
        "retention",
        "roadmap",
        "rollback",
        "runs",
        "scaffold-composer",
        "scaffold-ide",
        "schedule-sync",
        "secrets",
        "ship",
        "skills",
        "split",
        "stats",
        "status",
        "test",
        "validate",
        "validate-artifacts",
        "verify",
        "verify-signature",
        "version",
        "viz-graph",
        "viz-plan",
        "workspace",
    }
)

__all__ = ["FORGE_CORE_COMMANDS"]
