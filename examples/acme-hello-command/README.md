# acme-hello-command

Example CLI subcommand (`CommandPlugin`). Adds `fluid acme-hello`. The `fluid_build.commands`
group is read by forge-cli 0.8.3 and later.

forge-cli reads the entry-point name from package metadata and imports the module only when the
invoked command is not one of its own, so `fluid --help` imports nothing from this package. The
entry point names an *instance* (`command`), because forge-cli calls the loaded object with the
CLI's subparsers.

```bash
pip install -e ".[dev]"
pytest -v
fluid acme-hello --who there
```
