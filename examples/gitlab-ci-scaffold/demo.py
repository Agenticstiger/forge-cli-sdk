"""Demo — run gitlab-ci-scaffold against a multi-environment contract.

Usage:

    python demo.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from gitlab_ci_scaffold.scaffold import GitLabCIScaffold

CONTRACT = {
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
}


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        plugin = GitLabCIScaffold(output_root=Path(tmp))
        actions = plugin.plan(CONTRACT)
        result = plugin.apply(actions)

        print(f"✓ {result.applied} files written, {result.failed} failed\n")
        for p in sorted(Path(tmp).rglob("*")):
            if p.is_file():
                rel = p.relative_to(tmp)
                print(f"=== {rel} ===")
                print(p.read_text())
                print()


if __name__ == "__main__":
    main()
