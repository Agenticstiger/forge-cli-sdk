# Changelog

All notable changes to `data-product-forge-sdk` (formerly `fluid-sdk` /
`fluid_provider_sdk`) are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.12.1] — 2026-11-23

Mirrors two rule changes in forge-cli 0.39.0.

### Changed

- **An alert kind's `default_connection` satisfies `requires_connection`.** A route needs to
  name a connection only when the kind's `requires_connection` is true and its
  `default_connection` is `None`. When a route names none, `check` and `kwargs` get the kind's
  default as `route.connection`; a connection the route names wins. `AlertNotifierTestHarness`
  resolves sample routes the same way, so a kind with a default no longer needs a connection on
  every sample route. New helpers `connection_required(kind)` and
  `with_default_connection(kind, route)` in `fluid_sdk.roles.alert_notifier`. The `AlertNotifier`
  docstring and the plugin-group docs describe the interplay.
- **`CommandPluginTestHarness` refuses forge-cli's core command names by default.** forge-cli
  0.39.0 skips a command plugin that registers the name or an alias of a core command, with a
  typed error, on every supported Python (before, the last registration won silently on
  Python 3.10 and raised on 3.11 and later). The harness checks each added name against the
  core commands, vendored in `fluid_sdk/roles/_forge_commands.py` from forge-cli's parser as of
  its 0.38.0 release. `reserved_command_names` now adds names of your own on top of those;
  `check_core_command_names = False` turns the core check off for a forge-cli before 0.39.0.
  The `CommandPlugin` docstring states that the entry point is a callable `(subparsers) -> None`.

## [0.12.0] — 2026-11-22

### Added

- **`AlertNotifier`: a route kind for the alerts of generated DAGs.** forge-cli 0.38.0 reads
  the `fluid_build.alert_notifiers` entry-point group. The class carries forge-cli's own
  attributes and defaults (`notifier`, `requirements`, `supports_async`, `async_requirements`,
  `events`, `requires_connection`, `default_connection`) and its two methods,
  `check(route)` and `kwargs(route, alert)`. The values forge-cli hands a kind (`AlertRoute`,
  `Alert`, `NotifierCall`) are exported too. Like the other plain roles below it has no
  `plan` / `apply` and does not subclass `BasePlugin`: forge-cli reads the same names from any
  object.
- **`alert_route` and `check_alert_route`: default routes for `fluid_build.alert_defaults`.**
  `alert_route` builds one route as a contract writes it and raises `ValueError` for a shape
  the SDK's copy of forge-cli's route rules refuses, never quoting a value. `check_alert_route`
  returns the problems as a list. The checks cover the keys, `name`, `kind`, `events`,
  `connection`, `severity`, the email-only keys and `options` (JSON values with no template
  syntax or URL). Option keys follow forge-cli's `secret_option_key` by whole words, and a string
  with a shape forge-cli's redactor masks (provider key prefixes, `Bearer`, a JWT, a PEM block,
  URL user info, `key=value` with a credential-named key, the incident and chat webhook URLs) is
  refused in `name`, `kind`, `connection`, `format` and every option string. Those rules are
  vendored from forge-cli, which is the authority: it has more rules than a zero-dependency SDK
  can carry, it also asks the route's kind, and it may refuse more. forge-cli 0.38.0 first loads
  this group.
- **`MaintenanceAction`: a step of an Iceberg table's maintenance.** forge-cli 0.38.0 reads
  the `fluid_build.maintenance_actions` entry-point group. `check(options)` returns the problems
  with the options; `statements(table, options)` returns the SQL, each statement one `DELETE`,
  `UPDATE` or `MERGE` on the action's own table. `sql_literal` writes a string as a literal
  that passes, and `fluid_sdk.roles.maintenance_action.statement_problem` applies forge-cli's
  statement rules (no `${...}`, comment, backslash or control character; one write to the
  table), parsing as Spark SQL when `sqlglot` is installed. Without it the target is read by
  text right after `DELETE FROM`, `UPDATE` or `MERGE INTO`, and a statement that does not parse,
  or whose target an unusual spelling hides, can pass; the harness warns. The SDK still has no
  dependencies.
- **`CommandPlugin`: a `fluid <name>` subcommand.** The `fluid_build.commands` group is read by
  forge-cli 0.8.3 and later (lazy loading, the allow/block policy and the one-argument
  `func(args)` form arrived with forge-cli 0.11.0). Set `name` and `help`, override `configure(parser)` and
  `run(args, logger)`, and name an instance in the entry point: forge-cli calls the loaded
  object with the CLI's subparsers.
- **Conformance harnesses** in `fluid_sdk.testing`, one per new role, each encoding the rules
  forge-cli applies when it loads the entry point:
  - `AlertNotifierTestHarness`: the `notifier` path, plain requirements and default connection,
    known events, an entry-point name that is a kind name and not a built-in one, sample routes
    with the shape forge-cli reads (at least one passing the kind's own `check`), and `kwargs` that are deterministic, literal, identifier-keyed
    (not `context`) and leave the route alone for every event.
  - `MaintenanceActionTestHarness`: `check` (optional; a list, not a string) refuses bad options
    without quoting a value (the SDK's own rule);
    `statements` is deterministic, a non-empty list, leaves the options alone, and every
    statement passes `statement_problem`.
  - `CommandPluginTestHarness`: the entry point is a callable and not a class; registering adds a
    command, prints nothing and leaves the working directory and environment alone; every parser
    has a `func` forge-cli can call; `--help` exits cleanly; importing the module is quiet.
  - A plain class or object, or a function that returns a kind or action, works as forge-cli
    accepts it; the subclass tests skip for it.
- **Three example packages**: `examples/acme-chat-alerts` (a kind and a default route),
  `examples/acme-erasure-action` and `examples/acme-hello-command`, each with its entry point and
  a test that runs the harness.
- `docs/reference/plugin-groups.md`, and updates to the role taxonomy, architecture and
  conformance-testing references, say what each group reads and which forge-cli version first
  loads it.

### Notes

- `SDK_PROTOCOL_VERSION` stays 1 (the `BasePlugin` interface is unchanged) and
  `MIN_CLI_VERSION` stays 0.7.0. The alert and maintenance groups need forge-cli 0.38.0; a
  plugin for them simply registers nothing on an older CLI.

## [0.11.0] — 2026-11-21

### Fixed

- **`CustomScaffold.apply` no longer writes through a symlink planted at its temp
  file name.** The reference `apply()` staged each file at the predictable
  `<target>.tmp~`. A symlink planted there (a checked-out repository can carry one)
  made the write and the `chmod` land on a file outside `output_root`, and the final
  rename turned the output file into a symlink to it, while `apply()` reported
  success. Each file is now written through a temp file that `tempfile.mkstemp`
  creates exclusively in the target's directory (`O_CREAT | O_EXCL`, random name); the
  bytes and the mode go through the file descriptor (on Windows before Python 3.13,
  which has no `os.fchmod`, the mode is set by name on the fresh random file), and
  `os.replace` swaps it in. The temp file is removed if anything fails. File content,
  the exact planned mode, the path guard and the result shapes are unchanged. An
  OS-level failure message (permission denied, a directory in the way) now names the
  random temp file instead of `<target>.tmp~`.
- A `write_file` path that names `output_root` itself is now rejected before anything
  is created (it used to fail at the rename, after a temp file had been created beside
  the output root).
- **A planned setuid or setgid bit is applied as planned.** With the temp-file write
  above, a payload that fits the write buffer (the file system's block size, typically
  4 KiB; 128 KiB from Python 3.14) reached the kernel when the file closed, after
  `fchmod`, and a write by an unprivileged process makes the kernel drop those bits, so a
  planned `0o4755` landed as `0o755` (the mode used to be set after the write). The bytes
  are now flushed before the mode is set.

### Added

- **Conformance check: no write through a planted symlink.**
  `CustomScaffoldTestHarness.test_apply_does_not_write_through_planted_symlinks`
  plants a symlink beside each planned file at the common staging names (`<name>.tmp~`,
  `.tmp`, `~`, `.part`, `.new`, `.<name>.tmp` and `<stem>.tmp`; the class attribute
  `planted_temp_names`, which you can extend) pointing at a file outside
  `output_root`, runs `apply()`, and asserts that file is untouched. The links are files
  in `output_root` before `apply()` runs, so a plugin that refuses to write into a
  directory that already holds files may raise from `apply()`: a clean refusal passes, and
  a write through a link fails however `apply()` ends. It never plants a name the plugin
  itself needs (a planned file or one of its directories). It is a net
  over the common shapes, not a proof that no predictable name is used. A plugin that
  overrides `apply()` and stages files under one of those names now fails it; stage
  through `tempfile.mkstemp` as the inherited `apply()` does. The inherited `apply()`
  passes.

## [0.10.0] — 2026-06-27

### Changed

- **Type-honesty + conformance floor.** `PluginAction.from_dict` now coerces
  `phase` into the closed `Phase` domain (was a bare `str`); the reference
  `apply` implementations emit `ActionStatus` values (previously an
  exported-but-unused vocabulary). The universal conformance harness now
  **requires** at least one `sample_contract` (opt out with
  `allow_no_sample_contracts = True`) instead of silently passing on empty, and
  `test_apply_reflects_plan` enforces an **exact** per-action ledger rather than
  a `>=` net.

### Added

- **Docs-honesty CI gate** (`tests/unit/test_docs_honesty.py`) — scans every
  Markdown doc for `from fluid_sdk… import X` statements and `fluid_build.<group>`
  entry-point names and asserts each one actually resolves, so a doc can never
  again advertise an export, harness, or group that doesn't exist. Plus a
  consolidated SDK↔CLI **compatibility matrix** in `architecture.md` and a concrete
  **plugin trust-boundary** section (allow/block lists, type-only error logging) in
  `SECURITY.md`.

### Fixed

- **Docs reconciled to the real API.** Removed carried-over `fluid_provider_sdk`
  symbols that were documented but never exported (`PluginHookSpec`, `CostEstimate`,
  `invoke_hook`, `has_hook`) and the fictional hooks section; documented the real
  `provision_action` / `catalog_entry_action` helpers and the typed domains; and
  labelled an illustrative engine transcript as non-literal.

### Added (roles, domains, harnesses)

- **Two new role ABCs make the "four roles" promise real.** `InfraProvider`
  (`role="provider"`) and `CatalogAdapter` (`role="catalog"`) ship as first-class
  exports alongside `CustomScaffold` and `Validator`, each with an action builder
  (`provision_action` / `catalog_entry_action`). Both leave `apply` abstract on
  purpose, so a plugin that forgets to implement it fails loudly rather than
  silently no-op'ing.
- **Typed value domains** `Severity`, `ActionStatus`, `Phase` (zero-dependency
  `str`-enums) plus `FAILING_SEVERITIES`. `Severity.coerce` normalises aliases
  and **fails safe** — an unrecognised severity counts as `ERROR`, never silently
  passing.
- **`PluginCapabilities` + `BasePlugin.capabilities()`** — a typed plugin
  self-description with per-role defaults (replaces the prose-only "capability
  defaults" the role docstrings previously claimed).
- **Plugin↔CLI compatibility declaration** — `SDK_PROTOCOL_VERSION`,
  `MIN_CLI_VERSION` / `MAX_CLI_VERSION`, `cli_requirement()`, and
  `PluginMetadata.{sdk_protocol_version,requires_cli}`. The SDK declares; the CLI
  gates (dbt `require-dbt-version` model).
- **The three previously-advertised role harnesses now exist** —
  `ValidatorTestHarness`, `InfraProviderTestHarness`, `CatalogAdapterTestHarness`
  (previously documented but `ImportError` on use). The universal harness floor
  rose too: capabilities/compat declared, plan JSON-serialisable, and an opt-in
  apply-reflects-plan check.
- **`assert_plan_matches_snapshot`** — a zero-dependency golden-file snapshot
  helper (syrupy UX: fail-on-missing, `FLUID_SNAPSHOT_UPDATE=1`) for dbt-grade
  plan output pinning across every role.

### Fixed

- **Severity footgun in `Validator.apply`.** The reference implementation bucketed
  `counts[severity]` by raw string and tallied failures only from the literal
  `"error"`/`"critical"` keys, so a typo'd severity landed in a phantom bucket and
  silently escaped the failure tally. Severities now route through
  `Severity.coerce` (fail-safe) and unrecognised values surface in
  `ExecutionResult.warnings`.

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

[Unreleased]: https://github.com/Agenticstiger/forge-cli-sdk/compare/v0.12.0...HEAD
[0.12.0]: https://github.com/Agenticstiger/forge-cli-sdk/releases/tag/v0.12.0
[0.9.0]: https://github.com/Agenticstiger/forge-cli-sdk/releases/tag/v0.9.0
