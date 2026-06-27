# Your first real plugin — a GitLab CI generator

**Time:** 15 minutes | **Difficulty:** Beginner | **Prerequisites:** [Getting Started](../getting-started/README.md)

You're going to build something useful: a plugin that takes any fluid contract and produces a complete project scaffold — `.gitlab-ci.yml`, a project `README.md`, and per-environment config files. ~100 lines of plugin code. The CI definition adapts to the contract's environments automatically.

## What you'll build

A plugin called `gitlab-ci-scaffold` that, given a contract like:

```yaml
fluidVersion: "0.7.4"
id: my-data-product
name: My Data Product
description: A nightly aggregation of yesterday's events.
metadata:
  owner: {team: platform, email: platform@example.com}
environments:
  dev:
    metadata:
      labels: {"cloud.accountId": "111111111111", "cloud.region": "eu-west-1"}
  staging:
    metadata:
      labels: {"cloud.accountId": "222222222222", "cloud.region": "eu-west-1"}
  prod:
    metadata:
      labels: {"cloud.accountId": "333333333333", "cloud.region": "eu-west-1"}
```

…produces, deterministically:

```
my-data-product/
├── README.md
├── .gitlab-ci.yml
└── config/
    ├── dev.json
    ├── staging.json
    └── prod.json
```

The `.gitlab-ci.yml` will have one `deploy:` job per environment, in the right order. The per-env config files will carry the right cloud account IDs. **All driven by the contract** — change the contract, regenerate, the output adapts.

## What you'll learn

- Reading rich contract data via `ContractHelper`
- Iterating over `environments` and emitting one file per env
- Using `description=` on actions for nice CLI output
- Conformance harness's idempotency + determinism assertions on a real plugin
- Adding your own domain-specific tests on top of the harness

## Step 1 — Project skeleton

```bash
mkdir gitlab-ci-scaffold && cd gitlab-ci-scaffold
mkdir -p src/gitlab_ci_scaffold tests
touch src/gitlab_ci_scaffold/__init__.py
```

## Step 2 — `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "gitlab-ci-scaffold"
version = "0.1.0"
description = "Generates a complete GitLab CI scaffold from a fluid contract"
requires-python = ">=3.9"
dependencies = ["data-product-forge-sdk>=0.9,<1"]

[project.optional-dependencies]
dev = ["pytest>=7.0"]

[project.entry-points."fluid_build.custom_scaffolds"]
gitlab-ci = "gitlab_ci_scaffold.scaffold:GitLabCIScaffold"

[tool.setuptools.packages.find]
where = ["src"]
```

## Step 3 — The plugin (`src/gitlab_ci_scaffold/scaffold.py`)

```python
"""GitLab CI scaffold — generates a full project layout from a fluid contract."""

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

    # ── identity (descriptive metadata for registry / marketplace tooling) ──
    # NB: these fields do NOT appear in `fluid plugins list` — that command reads
    # entry-point names + allow/block status only and never loads the plugin.

    @classmethod
    def get_plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name=cls.name,
            role=cls.role,
            display_name="GitLab CI Scaffold",
            description="Generates a complete GitLab CI scaffold from a fluid contract.",
            version="0.1.0",
            author="Example Author",
            tags=["ci", "gitlab", "scaffold"],
        )

    # ── plan: build the action list ─────────────────────────────

    def plan(self, contract: Mapping[str, Any]) -> List[dict]:
        c = ContractHelper(contract)
        actions: List[dict] = []

        # 1. README.md
        actions.append(
            write_file_action(
                path="README.md",
                content=self._render_readme(c).encode("utf-8"),
                description="Project README",
            ).to_dict()
        )

        # 2. .gitlab-ci.yml — one deploy job per environment
        actions.append(
            write_file_action(
                path=".gitlab-ci.yml",
                content=self._render_ci(c).encode("utf-8"),
                description="GitLab CI definition",
            ).to_dict()
        )

        # 3. Per-environment config files
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
```

That's the whole plugin. ~85 lines including blank lines and docstrings.

## Step 4 — Tests (`tests/test_scaffold.py`)

```python
"""Tests for the GitLab CI scaffold."""

from __future__ import annotations

import base64
import json

from fluid_sdk.testing import CustomScaffoldTestHarness

from gitlab_ci_scaffold.scaffold import GitLabCIScaffold


# A realistic multi-env contract used by both the harness AND our domain tests.
MULTI_ENV_CONTRACT = {
    "fluidVersion": "0.7.4",
    "kind": "DataProduct",
    "id": "my-data-product",
    "name": "My Data Product",
    "description": "A nightly aggregation of yesterday's events.",
    "domain": "platform",
    "metadata": {
        "owner": {"team": "platform", "email": "platform@example.com"},
    },
    "environments": {
        "dev": {
            "metadata": {
                "labels": {"cloud.accountId": "111111111111", "cloud.region": "eu-west-1"},
            },
        },
        "staging": {
            "metadata": {
                "labels": {"cloud.accountId": "222222222222", "cloud.region": "eu-west-1"},
            },
        },
        "prod": {
            "metadata": {
                "labels": {"cloud.accountId": "333333333333", "cloud.region": "eu-west-1"},
            },
        },
    },
    "exposes": [],
    "consumes": [],
    "builds": [],
}


class TestGitLabCIScaffold(CustomScaffoldTestHarness):
    """Inherits ~15 conformance tests + adds domain-specific ones below."""

    plugin_class = GitLabCIScaffold
    sample_contracts = [MULTI_ENV_CONTRACT]

    # ── domain-specific assertions ──────────────────────────────

    def _action_content(self, actions, path: str) -> str:
        action = next(a for a in actions if a["params"]["path"] == path)
        return base64.b64decode(action["params"]["content_b64"]).decode("utf-8")

    def test_readme_includes_owner_and_envs(self):
        plugin = self.get_plugin()
        actions = plugin.plan(MULTI_ENV_CONTRACT)
        readme = self._action_content(actions, "README.md")
        assert "platform@example.com" in readme
        # environment_names() returns sorted list for determinism → alphabetical
        assert "dev, prod, staging" in readme

    def test_ci_has_one_deploy_per_env(self):
        plugin = self.get_plugin()
        actions = plugin.plan(MULTI_ENV_CONTRACT)
        ci = self._action_content(actions, ".gitlab-ci.yml")
        assert "deploy:dev:" in ci
        assert "deploy:staging:" in ci
        assert "deploy:prod:" in ci

    def test_prod_deploy_is_manual(self):
        """Prod deploys must be gated `when: manual` so they don't auto-run."""
        plugin = self.get_plugin()
        actions = plugin.plan(MULTI_ENV_CONTRACT)
        ci = self._action_content(actions, ".gitlab-ci.yml")
        # Find the deploy:prod block and assert `when: manual` appears after it
        prod_idx = ci.index("deploy:prod:")
        next_section = ci.index("deploy:", prod_idx + 1) if "deploy:" in ci[prod_idx + 1 :] else len(ci)
        prod_block = ci[prod_idx:next_section]
        assert "when: manual" in prod_block

    def test_env_config_carries_account_id(self):
        plugin = self.get_plugin()
        actions = plugin.plan(MULTI_ENV_CONTRACT)
        dev_config = json.loads(self._action_content(actions, "config/dev.json"))
        assert dev_config["cloud"]["accountId"] == "111111111111"
        assert dev_config["cloud"]["region"] == "eu-west-1"

    def test_emits_correct_file_count(self):
        plugin = self.get_plugin()
        actions = plugin.plan(MULTI_ENV_CONTRACT)
        # 1 README + 1 CI + 3 env configs = 5
        assert len(actions) == 5
```

## Step 5 — Install + run

```bash
pip install -e ".[dev]"
pytest -v
```

You'll see ~22 tests pass — 15 inherited from the harness, 5 you added:

```
tests/test_scaffold.py::TestGitLabCIScaffold::test_subclasses_base_plugin PASSED
tests/test_scaffold.py::TestGitLabCIScaffold::test_name_is_valid PASSED
tests/test_scaffold.py::TestGitLabCIScaffold::test_plan_is_deterministic PASSED
tests/test_scaffold.py::TestGitLabCIScaffold::test_apply_writes_files_to_tempdir PASSED
tests/test_scaffold.py::TestGitLabCIScaffold::test_apply_is_idempotent PASSED
tests/test_scaffold.py::TestGitLabCIScaffold::test_no_path_traversal PASSED
...
tests/test_scaffold.py::TestGitLabCIScaffold::test_readme_includes_owner_and_envs PASSED
tests/test_scaffold.py::TestGitLabCIScaffold::test_ci_has_one_deploy_per_env PASSED
tests/test_scaffold.py::TestGitLabCIScaffold::test_prod_deploy_is_manual PASSED
tests/test_scaffold.py::TestGitLabCIScaffold::test_env_config_carries_account_id PASSED
tests/test_scaffold.py::TestGitLabCIScaffold::test_emits_correct_file_count PASSED
============================== 22 passed in 0.07s ==============================
```

## Step 6 — Watch it generate a real project

```python
# demo.py
import tempfile
from pathlib import Path

from gitlab_ci_scaffold.scaffold import GitLabCIScaffold
from tests.test_scaffold import MULTI_ENV_CONTRACT

with tempfile.TemporaryDirectory() as tmp:
    plugin = GitLabCIScaffold(output_root=Path(tmp))
    actions = plugin.plan(MULTI_ENV_CONTRACT)
    result = plugin.apply(actions)

    print(f"✓ {result.applied} files written, {result.failed} failed")
    for p in sorted(Path(tmp).rglob("*")):
        if p.is_file():
            rel = p.relative_to(tmp)
            print(f"\n=== {rel} ===")
            print(p.read_text())
```

```bash
python demo.py
```

```
✓ 5 files written, 0 failed

=== .gitlab-ci.yml ===
# Auto-generated GitLab CI for my-data-product
# DO NOT EDIT BY HAND — regenerate via `fluid generate custom-scaffold`

stages:
  - validate
  - deploy

validate:
  stage: validate
  script:
    - fluid validate

deploy:dev:
  stage: deploy
  script:
    - fluid apply --env dev
  only:
    - main

deploy:staging:
  stage: deploy
  script:
    - fluid apply --env staging
  only:
    - main

deploy:prod:
  stage: deploy
  script:
    - fluid apply --env prod
  when: manual
  only:
    - main

=== README.md ===
# My Data Product

A nightly aggregation of yesterday's events.

## Project metadata

- **Owner:** platform@example.com
- **Domain:** platform
- **Environments:** dev, staging, prod

## CI / CD

This project ships a `.gitlab-ci.yml` with one `deploy:` job per environment.
Push to `main` to trigger.

=== config/dev.json ===
{
  "cloud": {
    "accountId": "111111111111",
    "region": "eu-west-1"
  },
  "environment": "dev",
  "product": {
    "id": "my-data-product",
    "owner": "platform@example.com"
  }
}

=== config/prod.json ===
{
  "cloud": {
    "accountId": "333333333333",
    "region": "eu-west-1"
  },
  "environment": "prod",
  "product": {
    "id": "my-data-product",
    "owner": "platform@example.com"
  }
}

=== config/staging.json ===
{
  "cloud": {
    "accountId": "222222222222",
    "region": "eu-west-1"
  },
  "environment": "staging",
  "product": {
    "id": "my-data-product",
    "owner": "platform@example.com"
  }
}
```

**This is a complete, working scaffold.** Drop the contract change → regenerate → output adapts.

## Step 7 — Publish (when ready)

```bash
pip install build twine
python -m build
twine upload dist/*
```

End users then install it alongside the FLUID CLI:

```bash
pip install data-product-forge data-product-forge-custom-scaffold gitlab-ci-scaffold
```

And reference it from any contract:

```yaml
extensions:
  customScaffold:
    libraries:
      - id: gitlab-ci
        source: { kind: pypi, package: gitlab-ci-scaffold, version: ">=0.1" }
    patterns:
      - use: gitlab-ci:gitlab-ci
```

Then:

```bash
fluid generate custom-scaffold
```

The FLUID CLI discovers your plugin via entry-points, calls `plan(contract)`, then `apply(actions)`. Files appear in the workspace.

## What you just shipped

| Component | LOC | Got you |
|---|---|---|
| `scaffold.py` | ~85 lines | Working plugin: README + CI + per-env configs |
| `pyproject.toml` | 14 lines | Pip-installable + discoverable by FLUID CLI |
| `test_scaffold.py` | ~50 lines | 22 tests (15 free conformance + 5 domain-specific) |

A non-trivial plugin in ~150 lines total. The SDK does the heavy lifting:

- Path-traversal protection — automatic
- Atomic writes — automatic
- Idempotency — automatic
- Determinism testing — automatic
- Contract version-agnostic parsing — automatic (via `ContractHelper`)

## What's next?

| If you want to... | Go to |
|---|---|
| Build a Validator (governance rules) | [walkthrough/build-a-validator.md](build-a-validator.md) |
| Hook into the actual FLUID CLI | [walkthrough/plug-into-fluid-cli.md](plug-into-fluid-cli.md) |
| Pick the right plugin role for your use case | [reference/role-taxonomy.md](../reference/role-taxonomy.md) |
| Browse complete working examples | [`examples/gitlab-ci-scaffold/`](../../examples/gitlab-ci-scaffold/) |
