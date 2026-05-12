"""The smallest possible CustomScaffold plugin.

Given any fluid contract, emits a single ``README.md`` summarising the
product's name + description. Three jobs:

1. Show how few lines a working plugin needs.
2. Be a template you can copy and grow into something real.
3. Pass the full ``CustomScaffoldTestHarness`` for free.
"""

from __future__ import annotations

from typing import Any, List, Mapping

from fluid_sdk import (
    ContractHelper,
    CustomScaffold,
    PluginMetadata,
    write_file_action,
)


class HelloScaffold(CustomScaffold):
    """Minimal CustomScaffold — emits exactly one file: README.md."""

    name = "hello"

    @classmethod
    def get_plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name=cls.name,
            role=cls.role,
            display_name="Hello Scaffold",
            description="Minimal CustomScaffold example. Emits a single README.md.",
            version="0.1.0",
            author="FLUID SDK Examples",
            tags=["example", "minimal"],
        )

    def plan(self, contract: Mapping[str, Any]) -> List[dict]:
        c = ContractHelper(contract)
        readme = (
            f"# {c.name or c.id or 'Unnamed product'}\n\n"
            f"{c.description or 'No description provided.'}\n"
        )
        return [
            write_file_action(
                path="README.md",
                content=readme.encode("utf-8"),
                description="Project README",
            ).to_dict(),
        ]
