"""Tests for gitlab-ci-scaffold."""

from __future__ import annotations

import base64
import json

from gitlab_ci_scaffold.scaffold import GitLabCIScaffold

from fluid_sdk.testing import CustomScaffoldTestHarness

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
    """Inherits ~15 conformance tests + adds domain-specific assertions below."""

    plugin_class = GitLabCIScaffold
    sample_contracts = [MULTI_ENV_CONTRACT]

    # ── domain-specific assertions ──────────────────────────────

    def _action_content(self, actions, path: str) -> str:
        action = next(a for a in actions if a["params"]["path"] == path)
        return base64.b64decode(action["params"]["content_b64"]).decode("utf-8")

    def test_readme_includes_owner_and_envs(self) -> None:
        plugin = self.get_plugin()
        actions = plugin.plan(MULTI_ENV_CONTRACT)
        readme = self._action_content(actions, "README.md")
        assert "platform@example.com" in readme
        # environment_names() returns sorted list for determinism → alphabetical
        assert "dev, prod, staging" in readme

    def test_ci_has_one_deploy_per_env(self) -> None:
        plugin = self.get_plugin()
        actions = plugin.plan(MULTI_ENV_CONTRACT)
        ci = self._action_content(actions, ".gitlab-ci.yml")
        assert "deploy:dev:" in ci
        assert "deploy:staging:" in ci
        assert "deploy:prod:" in ci

    def test_prod_deploy_is_manual(self) -> None:
        """Prod deploys must be gated ``when: manual`` so they don't auto-run."""
        plugin = self.get_plugin()
        actions = plugin.plan(MULTI_ENV_CONTRACT)
        ci = self._action_content(actions, ".gitlab-ci.yml")
        prod_idx = ci.index("deploy:prod:")
        # Find the start of any following 'deploy:' block, or end of file
        rest = ci[prod_idx + len("deploy:prod:") :]
        next_deploy = rest.find("\ndeploy:")
        end = prod_idx + len("deploy:prod:") + next_deploy if next_deploy != -1 else len(ci)
        prod_block = ci[prod_idx:end]
        assert "when: manual" in prod_block

    def test_env_config_carries_account_id(self) -> None:
        plugin = self.get_plugin()
        actions = plugin.plan(MULTI_ENV_CONTRACT)
        dev_config = json.loads(self._action_content(actions, "config/dev.json"))
        assert dev_config["cloud"]["accountId"] == "111111111111"
        assert dev_config["cloud"]["region"] == "eu-west-1"

    def test_emits_correct_file_count(self) -> None:
        plugin = self.get_plugin()
        actions = plugin.plan(MULTI_ENV_CONTRACT)
        # 1 README + 1 CI + 3 env configs = 5
        assert len(actions) == 5
