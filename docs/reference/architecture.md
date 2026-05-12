# Architecture

`data-product-forge-sdk` (import path `fluid_sdk`) is a zero-dependency Python SDK for building `data-product-forge` plugins.
This document explains the design — why it looks the way it does and how the pieces fit.

## Goals

1. **Build a plugin once, plug it in anywhere.** A plugin author learns one lifecycle (`plan` → `apply`, hooks, capabilities) and one data model (actions, results). The same skills work whether they're writing a cloud-infrastructure provider, a CI scaffolding generator, a custom validator, or a catalog adapter.
2. **Zero external dependencies.** Plugin authors don't need to pull the FLUID CLI's transitive dependency tree just to develop a plugin. The SDK is stdlib-only.
3. **Strong types, generously documented.** Every public class, function, and entry-point group is documented inline. The SDK ships a `py.typed` marker.
4. **Conformance test harness built in.** Plugin authors get tens of test cases for free by subclassing the right harness. No need to hand-roll determinism / idempotency / path-traversal tests.
5. **Forward-compatible.** New roles can be added in future SDK versions without breaking existing plugins. The `BasePlugin` ABC is intentionally minimal so role subclasses can layer on conventions.

## The four-layer model

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer 4 — Plugin packages (third-party)                          │
│  • Cloud providers (BigQuery, Snowflake, Glue, ...)              │
│  • Custom scaffolds (CI generators, project bootstrappers, ...)  │
│  • Validators (governance, compliance, cost, ...)                │
│  • Catalog adapters (DataHub, Atlan, ...)                        │
└──────────────────────────────┬───────────────────────────────────┘
                               │ subclasses + entry-points
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  Layer 3 — Role specialisations (fluid_sdk.roles.*)               │
│  • InfraProvider      — cloud-infra plan/apply                    │
│  • CustomScaffold     — file emission                             │
│  • Validator          — contract inspection                       │
│  • CatalogAdapter     — metadata sync                             │
│                                                                  │
│  Each is a thin BasePlugin subclass: sets role tag, provides      │
│  role-tuned capability defaults, adds role-specific helpers       │
│  (write_file_action, Finding.to_action, etc.).                    │
└──────────────────────────────┬───────────────────────────────────┘
                               │ inherits
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  Layer 2 — Universal foundation (fluid_sdk.{base,action,...})    │
│  • BasePlugin (ABC: plan, apply, render, capabilities)            │
│  • PluginAction (op, resource_id, params, depends_on, phase, ...)│
│  • ExecutionResult (apply() return type)                          │
│  • PluginMetadata, PluginCapabilities, PluginHookSpec             │
│  • PluginError, PluginInternalError                              │
└──────────────────────────────┬───────────────────────────────────┘
                               │ wraps contract input
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  Layer 1 — Contract parsing (fluid_sdk.contract)                  │
│  • ContractHelper — version-agnostic view over a contract dict   │
│  • ExposeSpec, ConsumeSpec, BuildSpec, ColumnSpec                │
└──────────────────────────────────────────────────────────────────┘
```

Each layer below is fully usable on its own. `ContractHelper` works without ever instantiating a plugin; `PluginAction` works without ever calling `plan()`.

## Why four roles, not one?

A single `BasePlugin` ABC could in principle do everything — but each of the four roles has subtly different semantics, defaults, and conformance expectations:

|  | InfraProvider | CustomScaffold | Validator | CatalogAdapter |
|---|---|---|---|---|
| Typical `op` values | `create_dataset`, `grant_access`, ... | `write_file` | `emit_finding` | `catalog.upsert`, `catalog.delete` |
| Pipeline stage | apply | generate | validate | publish |
| Side effects | cloud API calls | filesystem writes | none (pure inspection) | catalog API calls |
| Idempotency | provider-dependent | required (byte-identical) | always | usually |
| Determinism | required | **strictly required** | required | required |
| Streaming flag | possible | never | never | rare |
| Auth flag | usually | never | rarely | usually |

Pinning these via role subclasses gives:

- **Better defaults** (`CustomScaffold.capabilities()` automatically sets `render=True, auth=False`).
- **Targeted test harnesses** (`CustomScaffoldTestHarness` adds determinism + path-traversal + idempotency tests that don't apply to providers).
- **Type-aware tooling** (the FLUID CLI can dispatch validators differently from providers without sniffing the plugin internals).

Authors can still inherit `BasePlugin` directly for novel use cases — the role subclasses are conventions, not jailers.

## Entry-point discovery

The FLUID CLI walks four separate entry-point groups:

```toml
[project.entry-points."fluid_build.providers"]
mycloud = "my_pkg:MyCloudProvider"

[project.entry-points."fluid_build.custom_scaffolds"]
my-ci = "my_pkg:MyCIScaffold"

[project.entry-points."fluid_build.validators"]
my-rule = "my_pkg:MyValidator"

[project.entry-points."fluid_build.catalog_adapters"]
my-catalog = "my_pkg:MyCatalogAdapter"
```

Forge-cli loads each group at the appropriate lifecycle stage (providers at apply, scaffolds at generate, validators at validate, catalog adapters at publish). The plugin's `role` class attribute is the canonical signal — entry-point groups are convenience for the loader.

A plugin can in principle register under multiple groups if it implements multiple roles, but this is unusual.

## Why `plan()` returns dicts, not strongly-typed actions

`plan()` is declared to return `List[Dict[str, Any]]` rather than `List[PluginAction]`. Two reasons:

1. **JSON round-tripping** — actions cross process boundaries (forge-cli writes them to `plan.json`, ships them across machines). Dict is the canonical wire shape.
2. **Backwards compatibility** — older plugins return raw dicts. The new ABC doesn't break them.

`PluginAction` is provided as a typed builder: instantiate one, call `.to_dict()`, append. The conformance harness checks both shapes equally.

## Contract parsing — why a separate `ContractHelper`?

The FLUID contract schema evolves (0.4.0 → 0.5.7 → 0.7.x → …) and binding / location structures vary by version. Plugin authors should not have to detect version drift themselves.

`ContractHelper` is a read-only, typed facade:

```python
from fluid_sdk import ContractHelper

c = ContractHelper(contract_dict)
for expose in c.exposes():
    # ExposeSpec — handles all binding/location variants transparently
    print(expose.id, expose.platform, expose.format)
```

When the SDK version is bumped to track a new contract version, `ContractHelper` absorbs the diff; plugin code stays unchanged.

## Hooks and error handling

`PluginHookSpec` declares the lifecycle hooks; `BasePlugin` doesn't inherit it by default (hooks are opt-in). Plugins that need hooks:

```python
from fluid_sdk import InfraProvider, PluginHookSpec

class MyProvider(InfraProvider, PluginHookSpec):
    name = "myprov"

    def pre_apply(self, actions):
        # Last chance to filter/annotate actions before apply
        return [a for a in actions if not a.get("tags", {}).get("dry_run")]

    def post_apply(self, result):
        # Audit logging
        ...
```

Hook exceptions are **swallowed** by `invoke_hook` so a buggy hook can never break core plan/apply flow. If you need hard-failure semantics, raise from `plan()`/`apply()` instead.

Two error types let plugins signal failure intent:

- `PluginError` — user-actionable (auth, contract, env). CLI prints the message verbatim, no traceback.
- `PluginInternalError` — bug or unexpected env failure. CLI prints traceback + asks the user to file an issue.

## Determinism is the bedrock

Every plugin's `plan()` MUST be deterministic — same contract input ⇒ byte-identical action list. This is the foundation of:

- **Reproducible builds** — `plan.json` can be cached and re-applied.
- **Plan diffing** — `fluid diff` compares two plans byte-by-byte.
- **CI gating** — "did the plan change?" is a simple hash check.

For `CustomScaffold`, determinism is **doubly** important — re-generating the same scaffold twice must produce byte-identical output files. The conformance harness asserts this.

## Future evolution

New roles can be added in future SDK versions:

- `Orchestrator` — for plugins that wire DAGs / schedules
- `SecretStore` — for plugins that manage credentials
- `Observer` — for plugins that emit lineage / telemetry

Each will be a new `BasePlugin` subclass + new entry-point group, with no breaking change to existing roles.
