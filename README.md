# fluid-sdk

**Build a FLUID plugin in 30 seconds. Get 15+ conformance tests for free.**

Zero-dependency Python SDK for building plugins that extend the FLUID data-product CLI. Write a plugin once, plug it into the FLUID CLI via Python entry-points. Four built-in roles, one mental model.

```bash
pip install fluid-sdk
```

That's the only dependency.

## What can I build?

| Role | What it does | When you'd build one |
|---|---|---|
| [`InfraProvider`](docs/reference/role-taxonomy.md#infraprovider) | Provisions cloud resources (datasets, tables, IAM) | You're adding support for a new cloud platform |
| [`CustomScaffold`](docs/reference/role-taxonomy.md#customscaffold) | Generates files from a contract (CI configs, app code, IaC) | Your org has a standard project layout you want every team to use |
| [`Validator`](docs/reference/role-taxonomy.md#validator) | Inspects a contract and emits findings | You have governance / compliance / cost rules to enforce |
| [`CatalogAdapter`](docs/reference/role-taxonomy.md#catalogadapter) | Syncs product metadata to a catalog (DataHub, Atlan) | You want fluid contracts to flow into your existing catalog |

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

**Reference:**

- [`docs/reference/architecture.md`](docs/reference/architecture.md) — the four-layer model
- [`docs/reference/role-taxonomy.md`](docs/reference/role-taxonomy.md) — pick the right role
- [`docs/reference/contract-parsing.md`](docs/reference/contract-parsing.md) — `ContractHelper` API
- [`docs/reference/conformance-testing.md`](docs/reference/conformance-testing.md) — test harnesses

## The public API in 10 lines

```python
from fluid_sdk import (
    CustomScaffold,        # subclass for file-emitting plugins
    InfraProvider,         # subclass for cloud-infra plugins
    Validator,             # subclass for contract-inspection plugins
    CatalogAdapter,        # subclass for catalog-sync plugins
    ContractHelper,        # wrap any contract dict — typed read access
    write_file_action,     # builds a canonical write_file PluginAction
    Finding,               # validator authors emit these
)
# Everything else is in the role docs.
```

## Why a separate SDK?

The full FLUID CLI pulls ~40 transitive dependencies. As a plugin author, you don't need any of that — you only need:

- `BasePlugin` + the four role subclasses
- Action / result / metadata / capabilities data types
- `ContractHelper` for parsing fluid contracts
- A test harness

…all in pure Python stdlib. The end user installs the full CLI; you only need `fluid-sdk`. Faster `pip install`, no version-resolution headaches, your plugin works against multiple FLUID CLI versions.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
