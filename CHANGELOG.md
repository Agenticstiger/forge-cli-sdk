# Changelog

All notable changes to `data-product-forge-sdk` (formerly `fluid-sdk` /
`fluid_provider_sdk`) are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.1] — 2026-06-01

### Added

- `iter_extension_schemas()` and the `fluid_build.extension_schemas` entry-point
  group. Plugins advertise the JSON-Schema for their `contract.extensions.<key>`
  block via a provider (`get_extension_schema(fluid_version=None) -> dict`), and
  the `data-product-forge` CLI copilot enumerates them to natively generate and
  validate extension blocks — no CLI change required per new extension. Walks the
  group with per-plugin error isolation (a broken provider is skipped, logged by
  exception *type* only so a secret-bearing error message cannot leak). Zero new
  dependencies.

### Removed

- Dead `schemas/*.json` package-data glob (the SDK ships no first-party schema;
  extension schemas live in the plugins that own them).

## [0.9.0] — 2026-05-12

First PyPI release under the `data-product-forge-sdk` distribution name.
Import path remains `fluid_sdk` (dual naming — see README).

### Added

- Role-based plugin model: `BasePlugin` ABC plus four roles
  (`CustomScaffold`, `Validator`, `InfraProvider`, `CatalogAdapter`).
- Reference `CustomScaffold.apply` with atomic writes, sha256 verification,
  and path-traversal protection.
- `Validator` with severity-bucketed `Finding` reporting.
- `ContractHelper` — read-only contract parser tolerant of legacy contract
  shapes (`metadata.id`, `metadata.productId` fallbacks).
- `PluginTestHarness` and role-specific harnesses (`CustomScaffoldTestHarness`,
  `ValidatorTestHarness`) — downstream plugins inherit ~15 conformance tests
  for free.
- Three runnable example plugins: `hello-scaffold`, `gitlab-ci-scaffold`,
  `steward-validator`. Each ships its own `pyproject.toml`, demo, and tests.
- Public-API stability pin: `tests/unit/test_public_api.py` asserts every
  promised export is present, importable, and that `SDK_VERSION` matches the
  distribution version on disk.

### Changed (breaking)

- **Renamed PyPI distribution** `fluid-sdk` → `data-product-forge-sdk`.
  Import path is unchanged (`from fluid_sdk import …`). The old name is
  not republished and is not back-compat-shimmed; there are no known
  consumers of the previous name.
- **Removed the legacy `fluid_provider_sdk` package** (the provider-only
  precursor). All exports moved to `fluid_sdk` with role-based naming
  (`BasePlugin` instead of `BaseProvider`, `ExecutionResult` instead of
  `ApplyResult`, `PluginError` instead of `ProviderError`).
- **Raised Python floor: `requires-python = ">=3.10"`** (was `>=3.9`).
  Matches the `data-product-forge` CLI's `>=3.10` requirement so plugin
  authors and CLI users target the same Python range. CI matrix now runs
  on 3.10 / 3.11 / 3.12 / 3.13 / 3.14. Black / ruff / mypy targets
  bumped to match.

### Fixed

- CI workflow imports point at `fluid_sdk` (the previous version still
  imported `fluid_provider_sdk` and would have failed on every push).
- `SDK_VERSION` and `[project.version]` are now pinned to match and the
  test suite enforces the invariant.

### Security

- `CustomScaffold.apply` rejects absolute paths and `..` traversal before
  any file write.
- `CustomScaffold.apply` writes atomically (`temp + os.replace`) to avoid
  half-written files on crash.
- `validate_actions` rejects duplicate `resource_id` and unknown
  `depends_on` references before plugin code sees them.

## Older versions

Anything before `0.9.0` shipped under the `fluid-sdk` / `fluid_provider_sdk`
names and was never published to PyPI. See git history for context.

[Unreleased]: https://github.com/Agenticstiger/forge-cli-sdk/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/Agenticstiger/forge-cli-sdk/releases/tag/v0.9.0
