"""Tests for hello-scaffold — the smallest CustomScaffold example."""

from __future__ import annotations

import base64

from hello_scaffold.scaffold import HelloScaffold

from fluid_sdk.testing import LOCAL_CONTRACT, CustomScaffoldTestHarness


class TestHelloScaffold(CustomScaffoldTestHarness):
    """Inherits ~15 conformance tests from the SDK + adds a domain check."""

    plugin_class = HelloScaffold
    sample_contracts = [LOCAL_CONTRACT]

    def test_readme_includes_product_name(self) -> None:
        plugin = self.get_plugin()
        actions = plugin.plan(LOCAL_CONTRACT)
        readme_action = next(a for a in actions if a["params"]["path"] == "README.md")
        content = base64.b64decode(readme_action["params"]["content_b64"]).decode("utf-8")
        assert "Local Product" in content
