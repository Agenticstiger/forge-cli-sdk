"""GitLab CI scaffold — generates a full project layout from a fluid contract.

Given any fluid contract, emits:

* ``README.md`` — derived from contract identity + envs
* ``.gitlab-ci.yml`` — validate + one deploy job per declared environment
* ``config/<env>.json`` — per-env config carrying cloud account/region

The contract is the source of truth. Change ``environments`` in the contract,
regenerate, and the CI definition + config files adapt automatically.
"""

from __future__ import annotations

import json
from typing import Any, List, Mapping

from fluid_sdk import (
    ContractHelper,
    CustomScaffold,
    PluginMetadata,
    write_file_action,
)


class GitLabCIScaffold(CustomScaffold):
    """Generates README.md, .gitlab-ci.yml, and per-env config files."""

    name = "gitlab-ci"

    # ── identity (surfaces to `fluid plugins list`) ─────────────

    @classmethod
    def get_plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name=cls.name,
            role=cls.role,
            display_name="GitLab CI Scaffold",
            description="Generates a complete GitLab CI scaffold from a fluid contract.",
            version="0.1.0",
            author="FLUID SDK Examples",
            tags=["ci", "gitlab", "scaffold"],
        )

    # ── plan: build the action list ─────────────────────────────

    def plan(self, contract: Mapping[str, Any]) -> List[dict]:
        c = ContractHelper(contract)
        actions: List[dict] = []

        actions.append(
            write_file_action(
                path="README.md",
                content=self._render_readme(c).encode("utf-8"),
                description="Project README",
            ).to_dict()
        )

        actions.append(
            write_file_action(
                path=".gitlab-ci.yml",
                content=self._render_ci(c).encode("utf-8"),
                description="GitLab CI definition",
            ).to_dict()
        )

        for env_name in c.environment_names():
            actions.append(
                write_file_action(
                    path=f"config/{env_name}.json",
                    content=self._render_env_config(c, env_name).encode("utf-8"),
                    description=f"Config for environment {env_name!r}",
                ).to_dict()
            )

        return actions

    # ── private rendering helpers ───────────────────────────────

    def _render_readme(self, c: ContractHelper) -> str:
        owner = c.owner.get("email", "unknown")
        envs = ", ".join(c.environment_names()) or "(none declared)"
        return (
            f"# {c.name or c.id or 'Unnamed'}\n\n"
            f"{c.description or ''}\n\n"
            f"## Project metadata\n\n"
            f"- **Owner:** {owner}\n"
            f"- **Domain:** {c.domain or 'unknown'}\n"
            f"- **Environments:** {envs}\n\n"
            f"## CI / CD\n\n"
            f"This project ships a `.gitlab-ci.yml` with one `deploy:` job per environment.\n"
            f"Push to `main` to trigger.\n"
        )

    def _render_ci(self, c: ContractHelper) -> str:
        envs = c.environment_names()
        lines: List[str] = []
        lines.append(f"# Auto-generated GitLab CI for {c.id}")
        lines.append("# DO NOT EDIT BY HAND — regenerate via `fluid generate custom-scaffold`")
        lines.append("")
        lines.append("stages:")
        lines.append("  - validate")
        lines.append("  - deploy")
        lines.append("")
        lines.append("validate:")
        lines.append("  stage: validate")
        lines.append("  script:")
        lines.append("    - fluid validate")
        lines.append("")
        for env in envs:
            lines.append(f"deploy:{env}:")
            lines.append("  stage: deploy")
            lines.append("  script:")
            lines.append(f"    - fluid apply --env {env}")
            if env == "prod":
                lines.append("  when: manual")
                lines.append("  only:")
                lines.append("    - main")
            else:
                lines.append("  only:")
                lines.append("    - main")
            lines.append("")
        return "\n".join(lines)

    def _render_env_config(self, c: ContractHelper, env_name: str) -> str:
        env = c.environments.get(env_name) or {}
        env_meta = env.get("metadata") or {}
        labels = env_meta.get("labels") or {}
        config = {
            "environment": env_name,
            "cloud": {
                "accountId": labels.get("cloud.accountId", "unknown"),
                "region": labels.get("cloud.region", "unknown"),
            },
            "product": {
                "id": c.id,
                "owner": c.owner.get("email"),
            },
        }
        return json.dumps(config, indent=2, sort_keys=True) + "\n"
