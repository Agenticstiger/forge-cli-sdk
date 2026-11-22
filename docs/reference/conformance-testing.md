# Conformance testing

Subclass the matching test harness in your plugin's test suite; pytest auto-discovers every `test_*` method. You get tens of conformance tests for free.

## The harness hierarchy

```
PluginTestHarness  (universal — covers any BasePlugin)
├── InfraProviderTestHarness  (adds: role == provider, base is InfraProvider)
├── CustomScaffoldTestHarness (adds: determinism, idempotency, path-traversal, ...)
├── ValidatorTestHarness       (adds: finding severity, base is Validator)
└── CatalogAdapterTestHarness  (adds: role == catalog, base is CatalogAdapter)
```

The roles for forge-cli's newer groups have no `plan` / `apply`, so their harnesses stand alone (they do not extend `PluginTestHarness`): `AlertNotifierTestHarness`, `MaintenanceActionTestHarness` and `CommandPluginTestHarness`. They are described [below](#alertnotifiertestharness).

## Setup

```python
# tests/test_conformance.py
from fluid_sdk.testing import CustomScaffoldTestHarness, LOCAL_CONTRACT
from my_pkg.scaffold import MyCIScaffold

class TestMyCIScaffold(CustomScaffoldTestHarness):
    plugin_class = MyCIScaffold
    init_kwargs = {}                  # any extra ctor kwargs
    sample_contracts = [LOCAL_CONTRACT]
```

Run with `pytest tests/test_conformance.py -v`. Every inherited `test_*` method runs against your plugin.

## What each harness verifies

### `PluginTestHarness` (universal)

- Plugin subclasses `BasePlugin`.
- `name` is a non-empty identifier matching `^[a-z][a-z0-9_\-]*$`.
- `name` is not in a reserved list (`unknown`, `base`, `test`, ...).
- `role` is declared (non-empty class attribute).
- Constructor accepts `init_kwargs`.
- `logger` is set after construction.
- `capabilities()` returns a `Mapping[str, bool]` with `planning` and `apply` keys.
- `plan()` returns a list.
- Every action in `plan()` has both `op` and `resource_id`.
- `plan()` is **deterministic** — same contract twice → same list.
- `get_plugin_info()` returns metadata whose `name` matches the class.
- (Opt-in) `apply()` returns an `ExecutionResult`-like object with the expected fields.

### `CustomScaffoldTestHarness`

All of the above, plus:

- Subclass declares `role = "custom_scaffold"`.
- Subclass is a `CustomScaffold` subclass.
- Every action's `op` is either `write_file` or `skip`.
- Every `write_file` action carries `params.path` + `params.content_b64`.
- `apply()` writes the expected number of files to a tempdir under `output_root`.
- **Re-applying** the same actions produces byte-identical output (idempotency).
- No action's `params.path` is absolute or contains `..` (path-traversal safety).
- `apply()` does not write through a symlink planted beside an output file: a link at a common staging name (`<name>.tmp~`, `.tmp`, `~`, `.part`, `.new`, `.<name>.tmp`, `<stem>.tmp` — the class attribute `planted_temp_names`, which you can extend) pointing at a file outside `output_root` stays untouched. A net over the common shapes, not a proof. Stage files through `tempfile.mkstemp`, as the inherited `apply()` does, not under a predictable temp name.

### `InfraProviderTestHarness`

All of `PluginTestHarness`, plus:

- Subclass declares `role = "provider"`.
- Subclass is an `InfraProvider` subclass.

### `ValidatorTestHarness`

All of `PluginTestHarness`, plus:

- Subclass declares `role = "validator"`.
- Subclass is a `Validator` subclass.
- `apply` is not skipped (validators are cheap to run).
- Every `emit_finding` action has `params.severity` in `{info, warn, error, critical}`.

### `CatalogAdapterTestHarness`

All of `PluginTestHarness`, plus:

- Subclass declares `role = "catalog"`.
- Subclass is a `CatalogAdapter` subclass.

### `AlertNotifierTestHarness`

Set `notifier_class` (a class built with no arguments, or an instance), `sample_routes` (routes of this kind) and, if you like, `entry_point_name`. It verifies:

- The kind is one forge-cli accepts: a `notifier` path of dotted identifiers (`module.path:Class`), a callable `kwargs`, plain pip `requirements` / `async_requirements`, a plain `default_connection`, and `events` drawn from `failure`, `retry`, `success`, `sla_miss`.
- The entry-point name is a kind name and not a built-in kind's name (`email`, `slack`, `webhook`, `pagerduty`).
- Each sample route has the shape forge-cli reads, asks only for events the kind sends, and names a connection when the kind requires one.
- `check` returns sentences and does not raise.
- For every event of every sample route, `kwargs` is deterministic, returns Python-identifier keys (not `context`) with literal values, and does not modify the route.

### `MaintenanceActionTestHarness`

Set `action_class`, `sample_options` (at least one that `check` accepts), `bad_options` (each must be refused) and, if the table is not `fluid.silver.orders`, `table`. It verifies:

- `statements` exists and is callable; the entry-point name is plain.
- `check` returns sentences, refuses every bad option, and never quotes an option value in its message.
- `statements` is deterministic, returns a non-empty list (not a bare string), and does not modify the options.
- Every statement passes `statement_problem`: no `${...}`, comment marker, backslash or control character; one `DELETE`, `UPDATE` or `MERGE` that writes the table. With `sqlglot` installed the statement is parsed as Spark SQL as forge-cli does; without it a text check stands in.

### `CommandPluginTestHarness`

Set `command_entry_point` (the function or instance the entry point names; not the class), optionally `expected_commands` and `reserved_command_names`. It verifies:

- The entry point is callable and is not a class.
- Registering with a fresh `subparsers` adds at least one command, prints nothing, and leaves the working directory and environment alone.
- Command names are plain and not reserved.
- Every parser has a callable `func` default taking `(args)` or `(args, logger)`.
- `<command> --help` exits cleanly.
- Importing the module prints nothing and changes no environment or working directory.

## Sample contracts

The SDK ships two fixtures (under `fluid_sdk.testing.fixtures`):

- `MINIMAL_CONTRACT` — sparse. Exercises that plugins don't crash on empty exposes/builds/consumes.
- `LOCAL_CONTRACT` — slightly richer. Has one expose, one build, one environment, governance labels.

Plugin authors should usually add their own `sample_contracts` covering domain-specific shapes:

```python
class TestMyProvider(InfraProviderTestHarness):
    plugin_class = MyProvider
    sample_contracts = [
        LOCAL_CONTRACT,         # the SDK baseline
        {                       # plugin-specific fixture
            "fluidVersion": "0.7.4",
            "id": "my-test-product",
            "exposes": [{...}],
            ...
        },
    ]
```

## Overriding harness behaviour

### Skipping `apply()` tests

Default `skip_apply = True` because most cloud-infra `apply()` impls hit real cloud APIs. Override to `False` for plugins that are safe to apply in tests:

```python
class TestMyScaffold(CustomScaffoldTestHarness):
    plugin_class = MyScaffold
    sample_contracts = [LOCAL_CONTRACT]
    # CustomScaffoldTestHarness already has skip_apply implicitly False
    # (scaffolds write to tempdir — always safe in tests)
```

### Skipping specific tests

Use pytest's standard mechanisms — `pytest.mark.skip` or override the method in your subclass:

```python
class TestMyScaffold(CustomScaffoldTestHarness):
    plugin_class = MyScaffold
    sample_contracts = [LOCAL_CONTRACT]

    @pytest.mark.skip(reason="Plugin uses random IDs by design — non-deterministic")
    def test_plan_is_deterministic(self):
        pass
```

(Don't do this lightly. Determinism is a strong contract.)

### Adding custom tests

Just add more `test_*` methods to the subclass; pytest discovers them automatically.

```python
class TestMyScaffold(CustomScaffoldTestHarness):
    plugin_class = MyScaffold
    sample_contracts = [LOCAL_CONTRACT]

    def test_my_specific_invariant(self):
        scaffold = self.get_plugin()
        actions = scaffold.plan(LOCAL_CONTRACT)
        # custom assertion
        assert any(a["resource_id"] == "README.md" for a in actions)
```

## CI integration

Run conformance tests in CI alongside your normal test suite:

```yaml
# .github/workflows/test.yml
- name: Run conformance tests
  run: pytest tests/ -v --tb=short
```

If your plugin advertises support for many platforms / engines, parametrise:

```python
@pytest.mark.parametrize("contract", [LOCAL_CONTRACT, CUSTOM_FIXTURE_1, CUSTOM_FIXTURE_2])
class TestMyScaffold(CustomScaffoldTestHarness):
    plugin_class = MyScaffold

    @property
    def sample_contracts(self):
        return [self.contract]  # pytest injects via parametrize
```
