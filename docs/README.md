# `data-product-forge-sdk` documentation

> Distributed on PyPI as **`data-product-forge-sdk`**. Import path: **`fluid_sdk`**.

## Start here

1. **[Getting Started (5 minutes)](getting-started/README.md)** — build your first plugin from scratch, watch tests pass, see it produce a file.

2. **[Your first real plugin (15 minutes)](walkthrough/your-first-real-plugin.md)** — build a complete GitLab CI generator that adapts to the contract's environments.

## Walkthroughs

| Doc | Time | What you'll build |
|---|---|---|
| [`getting-started/`](getting-started/README.md) | 5 min | `hello-scaffold` — minimal plugin |
| [`walkthrough/your-first-real-plugin.md`](walkthrough/your-first-real-plugin.md) | 15 min | `gitlab-ci-scaffold` — full CI generator |
| [`walkthrough/build-a-validator.md`](walkthrough/build-a-validator.md) | 10 min | `steward-validator` — custom governance rule |
| [`walkthrough/plug-into-fluid-cli.md`](walkthrough/plug-into-fluid-cli.md) | 10 min | End-to-end — from `pip install` to generated files |

## Reference

| Doc | What's inside |
|---|---|
| [`reference/architecture.md`](reference/architecture.md) | The four-layer model. Why role taxonomy. Entry-point discovery. Determinism contract. |
| [`reference/role-taxonomy.md`](reference/role-taxonomy.md) | The four roles in detail. When to pick which. |
| [`reference/contract-parsing.md`](reference/contract-parsing.md) | `ContractHelper` — version-agnostic contract reader. |
| [`reference/conformance-testing.md`](reference/conformance-testing.md) | Test-harness usage. What each harness verifies. Customising. |

## Working examples

Three complete, runnable plugin packages — copy any of them to start a new plugin.

| Example | Role | Lines | What it shows |
|---|---|---|---|
| [`examples/hello-scaffold/`](../examples/hello-scaffold/) | `CustomScaffold` | ~30 | The smallest possible plugin |
| [`examples/gitlab-ci-scaffold/`](../examples/gitlab-ci-scaffold/) | `CustomScaffold` | ~150 | Real-world CI generator |
| [`examples/steward-validator/`](../examples/steward-validator/) | `Validator` | ~80 | Custom governance rule |

Each example has `pyproject.toml`, source code, conformance tests, and a `demo.py` that produces real output you can inspect.

## Quick reference — the public API

```python
from fluid_sdk import (
    # ── Universal ABC + role specialisations ─────────────────────
    BasePlugin,          # universal ABC
    InfraProvider,       # role: provider
    CustomScaffold,      # role: custom_scaffold
    Validator,           # role: validator
    CatalogAdapter,      # role: catalog

    # ── Data types ────────────────────────────────────────────────
    PluginAction,        # the action shape
    ExecutionResult,     # apply() return type
    ScaffoldFile,        # convenience for scaffold authors
    Finding,             # convenience for validator authors

    # ── Errors ───────────────────────────────────────────────────
    PluginError,         # user-actionable (auth, contract, env)
    PluginInternalError, # bugs / unexpected env failures

    # ── Metadata, capabilities, hooks ─────────────────────────────
    PluginMetadata,
    PluginCapabilities,
    PluginHookSpec,
    CostEstimate,

    # ── Contract parsing (version-agnostic) ───────────────────────
    ContractHelper,
    ExposeSpec, ConsumeSpec, BuildSpec, ColumnSpec,

    # ── Helpers ──────────────────────────────────────────────────
    write_file_action,
    validate_actions,
    invoke_hook, has_hook,
)
```

For installation + a 30-second overview, see the [top-level README](../README.md).
