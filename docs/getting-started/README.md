# Getting Started

**Time:** 5 minutes | **Difficulty:** Beginner | **Prerequisites:** Python 3.9+, `pip`

You're going to build a working FLUID plugin — a tiny one that generates a `README.md` for any fluid contract — and watch it light up in tests. **5 minutes start to finish.** No FLUID CLI install needed yet; we'll just verify the plugin works.

By the end you'll know exactly how the SDK works and how to write your own.

## What you'll build

A plugin called `hello-scaffold` that takes any fluid contract and emits one file: `README.md`. Three pieces of code, ~30 lines total:

```
hello-scaffold/
├── pyproject.toml              # 12 lines  — declare the plugin
├── src/hello_scaffold/
│   └── scaffold.py             # 18 lines  — the plugin itself
└── tests/
    └── test_scaffold.py        #  4 lines  — get 15 conformance tests free
```

## Step 1 — Install the SDK

```bash
pip install fluid-sdk
```

That's the only dependency. Zero transitive deps.

## Step 2 — Make the package skeleton

```bash
mkdir hello-scaffold && cd hello-scaffold
mkdir -p src/hello_scaffold tests
```

## Step 3 — Write `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "hello-scaffold"
version = "0.1.0"
requires-python = ">=3.9"
dependencies = ["fluid-sdk>=1.0.0"]

[project.entry-points."fluid_build.custom_scaffolds"]
hello = "hello_scaffold.scaffold:HelloScaffold"

[tool.setuptools.packages.find]
where = ["src"]
```

The `[project.entry-points."fluid_build.custom_scaffolds"]` line is **the magic** — once installed, the FLUID CLI discovers your plugin automatically.

## Step 4 — Write the plugin (`src/hello_scaffold/scaffold.py`)

```python
"""Hello-scaffold — the smallest possible CustomScaffold plugin."""

from fluid_sdk import ContractHelper, CustomScaffold, write_file_action


class HelloScaffold(CustomScaffold):
    name = "hello-scaffold"

    def plan(self, contract):
        c = ContractHelper(contract)
        readme = f"# {c.name or c.id or 'Unnamed'}\n\n{c.description or ''}\n"
        return [
            write_file_action(
                path="README.md",
                content=readme.encode("utf-8"),
            ).to_dict(),
        ]
```

That's the whole plugin. **No `apply()` needed** — it's inherited from `CustomScaffold` and writes the files to disk atomically with path-traversal guards and sha256 verification. You almost never override it.

Also create `src/hello_scaffold/__init__.py` (empty):

```bash
touch src/hello_scaffold/__init__.py
```

## Step 5 — Write the conformance test (`tests/test_scaffold.py`)

```python
from fluid_sdk.testing import CustomScaffoldTestHarness, LOCAL_CONTRACT
from hello_scaffold.scaffold import HelloScaffold


class TestHelloScaffold(CustomScaffoldTestHarness):
    plugin_class = HelloScaffold
    sample_contracts = [LOCAL_CONTRACT]
```

**4 lines of code. ~15 tests for free.** Pytest discovers everything inherited from `CustomScaffoldTestHarness`.

## Step 6 — Install + test

```bash
pip install -e .
pip install pytest
pytest -v
```

Output:

```
tests/test_scaffold.py::TestHelloScaffold::test_subclasses_base_plugin PASSED
tests/test_scaffold.py::TestHelloScaffold::test_name_is_valid PASSED
tests/test_scaffold.py::TestHelloScaffold::test_role_declared PASSED
tests/test_scaffold.py::TestHelloScaffold::test_constructor_accepts_kwargs PASSED
tests/test_scaffold.py::TestHelloScaffold::test_capabilities_returns_mapping PASSED
tests/test_scaffold.py::TestHelloScaffold::test_plan_returns_list PASSED
tests/test_scaffold.py::TestHelloScaffold::test_plan_actions_have_op PASSED
tests/test_scaffold.py::TestHelloScaffold::test_plan_actions_have_resource_id PASSED
tests/test_scaffold.py::TestHelloScaffold::test_plan_is_deterministic PASSED
tests/test_scaffold.py::TestHelloScaffold::test_get_plugin_info_exists PASSED
tests/test_scaffold.py::TestHelloScaffold::test_get_plugin_info_returns_metadata PASSED
tests/test_scaffold.py::TestHelloScaffold::test_is_custom_scaffold_subclass PASSED
tests/test_scaffold.py::TestHelloScaffold::test_actions_are_write_file_or_skip PASSED
tests/test_scaffold.py::TestHelloScaffold::test_write_file_actions_have_content PASSED
tests/test_scaffold.py::TestHelloScaffold::test_apply_writes_files_to_tempdir PASSED
tests/test_scaffold.py::TestHelloScaffold::test_apply_is_idempotent PASSED
tests/test_scaffold.py::TestHelloScaffold::test_no_path_traversal PASSED

============================== 17 passed in 0.05s ==============================
```

**You wrote 18 lines of plugin code and got 17 conformance tests.** Determinism, idempotency, path-traversal safety, role declaration, plan validity — all verified automatically.

## Step 7 — See it actually run

Let's run the plugin against a contract by hand (later, the FLUID CLI does this for you):

```python
# demo.py
from pathlib import Path
import tempfile
from hello_scaffold.scaffold import HelloScaffold

contract = {
    "fluidVersion": "0.7.4",
    "id": "my-first-product",
    "name": "My First Product",
    "description": "A demo product.",
}

with tempfile.TemporaryDirectory() as tmpdir:
    plugin = HelloScaffold(output_root=Path(tmpdir))
    actions = plugin.plan(contract)
    result = plugin.apply(actions)

    print(f"Applied {result.applied} actions, {result.failed} failed")
    print(f"Artifacts: {result.artifacts}")
    print(f"Wrote:\n{(Path(tmpdir) / 'README.md').read_text()}")
```

```bash
python demo.py
```

Output:

```
Applied 1 actions, 0 failed
Artifacts: ['/var/folders/.../README.md']
Wrote:
# My First Product

A demo product.
```

You just shipped a working FLUID plugin.

## What just happened?

```
┌──────────────────────────────────────────────────────┐
│  Your contract dict                                  │
│  { "id": "my-first-product", "name": "...", ... }    │
└──────────────────┬───────────────────────────────────┘
                   │
                   ▼  plan()
┌──────────────────────────────────────────────────────┐
│  plugin.plan(contract)                               │
│    1. Wraps contract in ContractHelper (typed view)  │
│    2. Builds a README string                         │
│    3. Returns one write_file action                  │
└──────────────────┬───────────────────────────────────┘
                   │
                   ▼  apply()  (inherited from CustomScaffold)
┌──────────────────────────────────────────────────────┐
│  plugin.apply(actions)  ←  inherited reference impl  │
│    1. Decodes content_b64                            │
│    2. Verifies sha256 (plan ↔ apply integrity)       │
│    3. Path-traversal guard                           │
│    4. Atomic tempfile + rename to README.md          │
│    5. Returns ExecutionResult                        │
└──────────────────────────────────────────────────────┘
```

## What's next?

| If you want to... | Go to |
|---|---|
| Build something realistic — a full CI generator | [walkthrough/your-first-real-plugin.md](../walkthrough/your-first-real-plugin.md) |
| Understand the four plugin roles + pick the right one | [reference/role-taxonomy.md](../reference/role-taxonomy.md) |
| See the underlying ABCs + lifecycle in detail | [reference/architecture.md](../reference/architecture.md) |
| Hook your plugin into the FLUID CLI end-to-end | [walkthrough/plug-into-fluid-cli.md](../walkthrough/plug-into-fluid-cli.md) |
| Browse complete working examples | [`examples/`](../../examples/) |

## Cheat sheet — the SDK in 10 lines

```python
from fluid_sdk import (
    CustomScaffold,        # subclass this for file-emitting plugins
    InfraProvider,         # subclass this for cloud-infra plugins
    Validator,             # subclass this for contract-inspection plugins
    CatalogAdapter,        # subclass this for catalog-sync plugins
    ContractHelper,        # wrap any contract dict — typed read access
    write_file_action,     # builds a canonical write_file PluginAction
    Finding,               # validator authors emit these
)
# That's basically everything.
```

Continue → [walkthrough/your-first-real-plugin.md](../walkthrough/your-first-real-plugin.md)
