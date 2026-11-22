# data-product-forge-sdk

**Build a `data-product-forge` plugin in 30 seconds. Get 15+ conformance tests for free.**

Zero-dependency Python SDK for building plugins that extend the `data-product-forge` (a.k.a. FLUID) CLI. Write a plugin once, plug it in via Python entry-points. Seven built-in roles: four with a `plan` / `apply` lifecycle, three typed classes for the plugin groups forge-cli 0.38.0 adds.

```bash
pip install data-product-forge-sdk
```

```python
from fluid_sdk import CustomScaffold, Validator, ContractHelper
```

> **Dual naming, on purpose.** PyPI distribution: `data-product-forge-sdk`. Import path: `fluid_sdk`. Same pattern as `pyyaml` ↔ `yaml`, `scikit-learn` ↔ `sklearn`. The PyPI name reflects the product brand; the import path stays short.

Zero dependencies beyond the Python standard library.

## What can I build?

| Role | What it does | When you'd build one |
|---|---|---|
| [`InfraProvider`](docs/reference/role-taxonomy.md#infraprovider) | Provisions cloud resources (datasets, tables, IAM) | You're adding support for a new cloud platform |
| [`CustomScaffold`](docs/reference/role-taxonomy.md#customscaffold) | Generates files from a contract (CI configs, app code, IaC) | Your org has a standard project layout you want every team to use |
| [`Validator`](docs/reference/role-taxonomy.md#validator) | Inspects a contract and emits findings | You have governance / compliance / cost rules to enforce |
| [`CatalogAdapter`](docs/reference/role-taxonomy.md#catalogadapter) | Syncs product metadata to a catalog (DataHub, Atlan) | You want fluid contracts to flow into your existing catalog |
| [`AlertNotifier`](docs/reference/plugin-groups.md#alertnotifier) | Adds a route kind (Teams, Opsgenie, an internal pager) to the alerts of generated DAGs, and an organisation's default routes (`alert_route`) | Your on-call tool is not one of the built-in kinds. Needs forge-cli 0.38.0 |
| [`MaintenanceAction`](docs/reference/plugin-groups.md#maintenanceaction) | Returns the SQL for a step of an Iceberg table's maintenance, such as an erasure of the rows a request names | You need a table to be cleaned on a schedule beyond compaction and expiry. Needs forge-cli 0.38.0 |
| [`CommandPlugin`](docs/reference/plugin-groups.md#commandplugin) | Adds a `fluid <name>` subcommand | You want your own command in the same CLI. Needs forge-cli 0.8.3 |

## 30-second example — your first plugin

```python
# scaffold.py
from fluid_sdk import ContractHelper, CustomScaffold, write_file_action


class HelloScaffold(CustomScaffold):
    name = "hello"

    def plan(self, contract):
        c = ContractHelper(contract)
        return [
            write_file_action(
                path="README.md",
                content=f"# {c.name}\n\n{c.description}\n".encode("utf-8"),
            ).to_dict(),
        ]
```

```python
# tests/test_scaffold.py
from fluid_sdk.testing import CustomScaffoldTestHarness, LOCAL_CONTRACT
from scaffold import HelloScaffold


class TestHelloScaffold(CustomScaffoldTestHarness):
    plugin_class = HelloScaffold
    sample_contracts = [LOCAL_CONTRACT]
```

`pytest` runs **15+ conformance tests** automatically. Determinism, idempotency, path-traversal safety, role declaration — all verified.

→ Full step-by-step in [docs/getting-started/](docs/getting-started/README.md).

## How users plug your plugin into the FLUID CLI

Plugin authors register via `pyproject.toml`:

```toml
[project.entry-points."fluid_build.custom_scaffolds"]
hello = "my_pkg.scaffold:HelloScaffold"
```

End users then:

```bash
pip install data-product-forge               # the CLI
pip install data-product-forge-custom-scaffold   # the engine
pip install your-plugin               # what you wrote
```

And in any contract:

```yaml
extensions:
  customScaffold:
    libraries:
      - id: ci
        source: { kind: pypi, package: your-plugin, version: ">=0.1" }
    patterns:
      - use: ci:hello
```

```bash
fluid generate custom-scaffold
# Your plugin's files appear in the workspace.
```

## Documentation

**Start here:**

- **[Getting Started (5 minutes)](docs/getting-started/README.md)** — build your first plugin, see tests pass, run it.
- **[Your first real plugin (15 minutes)](docs/walkthrough/your-first-real-plugin.md)** — build a complete GitLab CI generator. Realistic, deployable.

**Working examples** (every one runs `pytest` + `python demo.py` standalone):

- **[`examples/hello-scaffold/`](examples/hello-scaffold/)** — the smallest possible plugin (~30 LOC)
- **[`examples/gitlab-ci-scaffold/`](examples/gitlab-ci-scaffold/)** — full CI generator (~150 LOC, 27 tests)
- **[`examples/steward-validator/`](examples/steward-validator/)** — custom governance rule (~80 LOC, 22 tests)
- **[`examples/acme-chat-alerts/`](examples/acme-chat-alerts/)** — an alert route kind plus an organisation's default route
- **[`examples/acme-erasure-action/`](examples/acme-erasure-action/)** — a maintenance action that returns a `DELETE`
- **[`examples/acme-hello-command/`](examples/acme-hello-command/)** — a `fluid` subcommand

**Reference:**

- [`docs/reference/architecture.md`](docs/reference/architecture.md) — the four-layer model
- [`docs/reference/role-taxonomy.md`](docs/reference/role-taxonomy.md) — pick the right role
- [`docs/reference/plugin-groups.md`](docs/reference/plugin-groups.md) — alert notifiers, maintenance actions and command plugins
- [`docs/reference/contract-parsing.md`](docs/reference/contract-parsing.md) — `ContractHelper` API
- [`docs/reference/conformance-testing.md`](docs/reference/conformance-testing.md) — test harnesses

## The public API in a few lines

```python
from fluid_sdk import (
    CustomScaffold,        # subclass for file-emitting plugins
    InfraProvider,         # subclass for cloud-infra plugins
    Validator,             # subclass for contract-inspection plugins
    CatalogAdapter,        # subclass for catalog-sync plugins
    AlertNotifier,         # a route kind for the alerts of generated DAGs
    MaintenanceAction,     # SQL for a step of an Iceberg table's maintenance
    CommandPlugin,         # a `fluid <name>` subcommand
    ContractHelper,        # wrap any contract dict — typed read access
    write_file_action,     # builds a canonical write_file PluginAction
    Finding,               # validator authors emit these
)
# Everything else is in the role docs.
```

## Why a separate SDK?

The full `data-product-forge` CLI pulls ~40 transitive dependencies. As a plugin author, you don't need any of that — you only need:

- `BasePlugin` + the four role subclasses, and the three plain classes for the newer groups
- Action / result / metadata / capabilities data types
- `ContractHelper` for parsing fluid contracts
- A test harness

…all in pure Python stdlib. The end user installs the full CLI; you only need `data-product-forge-sdk`. Faster `pip install`, no version-resolution headaches, your plugin works against multiple `data-product-forge` CLI versions.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
