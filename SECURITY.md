# Security policy

## Reporting a vulnerability

If you believe you've found a security issue in `data-product-forge-sdk`, **do not** open a public GitHub issue. Use GitHub's private vulnerability-reporting channel instead:

> **[Report a vulnerability →](https://github.com/Agenticstiger/forge-cli-sdk/security/advisories/new)**

That form is private to the maintainers and lets us coordinate a fix and disclosure timeline with you directly. Include:

- A description of the issue and its impact.
- Steps to reproduce (a minimal proof-of-concept is ideal).
- The version of the SDK affected.

You should hear back within 3 business days. We aim to ship a fix and a CVE (where applicable) within 30 days for high-severity issues. For lower-severity reports the cadence is best-effort but always acknowledged.

## Threat model

This SDK is a **library**. It does not run a server, open sockets, or interpret untrusted code on its own. What it does:

- **Defines plugin ABCs.** Downstream plugins inherit from `BasePlugin` and the four role classes (`CustomScaffold`, `Validator`, `InfraProvider`, `CatalogAdapter`).
- **Provides a reference `CustomScaffold.apply`** that writes files to disk. The reference implementation is defensive: it rejects absolute paths and `..` traversal in destination paths, computes and verifies `sha256` integrity before write, and writes atomically via `os.replace`. See `src/fluid_sdk/roles/custom_scaffold.py`.
- **Provides `ContractHelper`** — a read-only parser over fluid contract dicts. No code execution, no eval, no YAML loading.

### What the SDK is **not** responsible for

- **Plugin trust.** A plugin is third-party Python that gets imported into the `data-product-forge` CLI process. Trust in a plugin = trust in whatever pip resolved when the user installed it. The SDK does not sandbox, time-limit, or isolate plugin code. The CLI documents this trust boundary in its own SECURITY.md; this SDK inherits it.
- **Contract content.** If a contract `metadata.labels["x"]` contains `{{ 7*7 }}`, the SDK doesn't evaluate it. Downstream renderers (e.g. `data-product-forge-custom-scaffold`) make their own choices about Jinja2 autoescaping; see *their* SECURITY.md.
- **Catalog / cloud auth.** Role implementations that talk to external systems handle credentials themselves; the SDK has nothing to do with that.

### Defensive behavior baked in

- `CustomScaffold.apply` rejects path traversal (`..`) and absolute paths before any write.
- `CustomScaffold.apply` computes `sha256` of bytes-to-write and refuses if it doesn't match the integrity hash in the action.
- `CustomScaffold.apply` writes atomically (`temp + os.replace`) so a crashed run leaves either the old file or the new file, never a half-written file.
- `validate_actions` rejects duplicate `resource_id`s and unknown `depends_on` references before any plugin sees them.

## Supported versions

| Version | Supported          | Notes                                          |
|---------|--------------------|------------------------------------------------|
| 0.9.x   | ✅ Active           | Current development line                       |
| < 0.9   | ❌ Not supported    | Pre-rename `fluid-sdk` / `fluid_provider_sdk` versions — please upgrade |

We backport security fixes only to the current minor version while it's the latest.
