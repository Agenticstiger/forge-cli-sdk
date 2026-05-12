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
