# hello-scaffold

The smallest possible FLUID `CustomScaffold` plugin — emits one `README.md` from any contract.

**~30 lines of Python.** Useful as a template you can copy and grow into something real.

## Try it

```bash
cd examples/hello-scaffold/
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Conformance tests + one domain test
pytest -v

# See it actually run
python demo.py
```

Demo output:

```
✓ 1 files written, 0 failed

--- README.md ---
# My First Product

A demo product produced by the hello-scaffold plugin.
```

## Make it your own

```bash
cp -r examples/hello-scaffold/ my-plugin/
cd my-plugin/
```

Edit:

1. `pyproject.toml` — change `[project].name` and the entry-point key
2. `src/hello_scaffold/scaffold.py` — rename class + `name`, add more `write_file_action` entries in `plan()`
3. `tests/test_scaffold.py` — update import, add your domain assertions

Then `pytest -v` will still pass — the inherited harness adapts.
