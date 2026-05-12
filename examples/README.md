# Examples — runnable FLUID plugins

Three complete, working plugin packages. Each is a real PyPI-publishable package, fully tested. Copy any directory to start a new plugin from.

| Example | Role | What it does | LOC |
|---|---|---|---|
| [`hello-scaffold/`](hello-scaffold/) | `CustomScaffold` | Smallest possible plugin — emits one `README.md` from any contract | ~30 |
| [`gitlab-ci-scaffold/`](gitlab-ci-scaffold/) | `CustomScaffold` | Realistic CI generator — emits `.gitlab-ci.yml`, `README.md`, per-env config | ~150 |
| [`steward-validator/`](steward-validator/) | `Validator` | Custom governance rule — requires every contract to declare a steward | ~80 |

## Running an example

Every example has the same shape:

```bash
cd examples/<name>/
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -v          # see all conformance + domain tests pass
python demo.py     # see the plugin actually produce output
```

## Using an example as a template

```bash
cp -r examples/hello-scaffold/ my-new-plugin/
cd my-new-plugin/
# Edit pyproject.toml — change [project].name and the entry-point key
# Edit src/<pkg>/scaffold.py — rename the class, change name, write your logic
# Edit tests/ — point at your new class
```

That's it. Every example follows the same layout so swapping logic is mechanical.

## Want to publish?

```bash
pip install build twine
python -m build
twine upload dist/*
```

After publishing, end users install your plugin with the FLUID CLI:

```bash
pip install data-product-forge data-product-forge-custom-scaffold my-new-plugin
fluid generate custom-scaffold --pattern my-new-plugin
```

And it just works — the FLUID CLI discovers your plugin via the entry-point declared in `pyproject.toml`.
