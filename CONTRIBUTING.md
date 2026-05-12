# Contributing to data-product-forge-sdk

Thanks for taking the time. Before we get into commands, here's the mental model — most PR comments here come down to "is this consistent with the spirit below?"

## What this SDK is, and isn't

**It is:** a tiny, stdlib-only library that defines four plugin roles (`CustomScaffold`, `Validator`, `InfraProvider`, `CatalogAdapter`), the data types they exchange (`PluginAction`, `ExecutionResult`, `Finding`), and a conformance test harness any plugin can subclass to get ~15 invariants checked for free.

**It isn't:** a framework. There is no DI container, no lifecycle manager, no async runtime. The SDK is a contract. Plugin authors implement it; the `data-product-forge` CLI dispatches it. Keep the dependency graph at zero and the surface area small.

If a change adds runtime dependencies, a new role, or breaks the conformance harness, it needs design discussion before code. Open an issue first.

## Repo layout

```
src/fluid_sdk/             # the package (import path stays `fluid_sdk` even though PyPI ships as data-product-forge-sdk)
├── base.py                # BasePlugin ABC
├── action.py              # PluginAction, phase constants
├── result.py              # ExecutionResult
├── error.py               # PluginError, PluginInternalError
├── contract.py            # ContractHelper — read-only contract parser
├── metadata.py            # PluginMetadata
├── roles/                 # one file per role
│   ├── custom_scaffold.py
│   └── validator.py
└── testing/
    ├── harness.py         # PluginTestHarness (generic, ~15 conformance tests)
    ├── role_harnesses.py  # CustomScaffoldTestHarness, etc.
    └── fixtures.py        # LOCAL_CONTRACT, MINIMAL_CONTRACT
tests/unit/                # SDK's own tests
examples/                  # three runnable example plugins (each builds + tests independently)
docs/                      # walkthroughs + reference; the canonical docs site lives in a separate repo
```

## Dev loop

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"

.venv/bin/pytest                            # 46 tests, ~0.1s
.venv/bin/ruff check src/ tests/
.venv/bin/black --check src/ tests/
.venv/bin/python -m build                   # sdist + wheel; run if you touched pyproject.toml
```

CI on a PR runs the same three gates against Python 3.9 / 3.10 / 3.11 / 3.12 / 3.13. If your laptop is 3.12 and CI fails on 3.9, that's almost always a typing import (`from __future__ import annotations` solves most of these).

## Where high-quality PRs come from

A short list of the things that earn fast review:

- **Tests demonstrate the change.** Bug fix? A failing test, then the fix. New behavior? A test that pins the contract. The conformance harness covers basics; add scenario tests for anything specific.
- **One logical change per PR.** Refactor + bug fix + new role in one branch makes everything slower.
- **Public-API additions** appear in both `src/fluid_sdk/__init__.py::__all__` *and* `tests/unit/test_public_api.py::PROMISED_EXPORTS`. The test would catch the mismatch; the human review shouldn't have to.
- **No drift between sources of truth.** If you touch `[project.version]` in `pyproject.toml`, touch `src/fluid_sdk/version.py::SDK_VERSION` too. `test_sdk_version_matches_pyproject` will catch this; the principle generalises.
- **Honest commit messages.** Conventional Commits format (`feat(roles): add CatalogAdapter helper`) — type, scope, intent. The "why" goes in the PR description.

## How to add a new role

A role is a thin subclass of `BasePlugin` that pins a `role` string and adds role-shaped helpers. Reference roles: `CustomScaffold` (file emission), `Validator` (findings). To add a third:

1. **Create the role module** under `src/fluid_sdk/roles/<role>.py`. Subclass `BasePlugin`, set `role = "<role>"`, override capability defaults if relevant.

   ```python
   # src/fluid_sdk/roles/catalog_adapter.py
   from ..base import BasePlugin

   class CatalogAdapter(BasePlugin):
       """File-emitting? No. Validates? No. Pushes metadata to a catalog."""
       role = "catalog"

       def push_entity(self, contract):  # role-shaped helper, not required by BasePlugin
           ...
   ```

2. **Re-export** from `src/fluid_sdk/roles/__init__.py` and the top-level `src/fluid_sdk/__init__.py` (and `__all__`, and `PROMISED_EXPORTS` in `tests/unit/test_public_api.py`).

3. **Add a conformance harness** in `src/fluid_sdk/testing/role_harnesses.py`:

   ```python
   class CatalogAdapterTestHarness(PluginTestHarness):
       plugin_class: type[CatalogAdapter] | None = None

       def test_push_entity_is_idempotent(self):
           plugin = self._instantiate()
           result1 = plugin.push_entity(self.contract)
           result2 = plugin.push_entity(self.contract)
           assert result1 == result2
   ```

4. **Add a runnable example** under `examples/<role>-example/` with its own `pyproject.toml`, tests, and a `demo.py` that runs end-to-end against `examples/<role>-example/`.

5. **Document** in `docs/reference/role-taxonomy.md` (one section, ~30 lines: when to pick this role, what `plan` returns, what `apply` does).

Roughly 250 lines of code; review-time well under an hour.

## How to write a conformance test

The pattern is: the harness defines tests, your plugin subclasses set `plugin_class`, pytest discovers everything. The test method has access to `self._instantiate()` (fresh plugin) and `self.contract` (a fixture contract).

```python
# In src/fluid_sdk/testing/role_harnesses.py — for everyone

class CustomScaffoldTestHarness(PluginTestHarness):
    def test_output_is_deterministic(self):
        plugin = self._instantiate()
        first = plugin.plan(self.contract)
        second = plugin.plan(self.contract)
        assert first == second, "scaffold output drifted between runs"
```

```python
# In a downstream plugin — once

class TestMyScaffold(CustomScaffoldTestHarness):
    plugin_class = MyScaffold

# That's the whole test file. ~15 conformance tests run automatically.
```

The bar for a new harness test: it must hold for *every* reasonable plugin of that role. Plugin-specific behavior goes in the plugin's own test suite, not the harness.

## Backwards compatibility

The SDK is 0.x. Breaking changes are allowed in minor versions but should:
- be listed in `CHANGELOG.md` under "Breaking changes"
- include a migration note in the PR description
- be avoided when a non-breaking alternative is reasonable

We'll cut 1.0 once the API has been stable through at least one full release cycle with an external plugin in the wild.

## Reporting bugs and security issues

- **Bug reports:** open a GitHub issue with a minimal reproducer. The "what I expected vs. what I got" framing saves a round-trip.
- **Security issues:** see [`SECURITY.md`](SECURITY.md). Do not file a public issue.

## License

By submitting a PR you agree your contribution is licensed under [Apache-2.0](LICENSE).
