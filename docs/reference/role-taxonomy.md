# Role taxonomy

`data-product-forge-sdk` (import path `fluid_sdk`) ships seven built-in plugin roles. Four (`InfraProvider`, `CustomScaffold`, `Validator`, `CatalogAdapter`) are thin subclasses of `BasePlugin` that pin a `role` tag, set role-appropriate capability defaults, and provide role-specific helpers. Three more (`AlertNotifier`, `MaintenanceAction`, `CommandPlugin`) describe plugin groups with no `plan` / `apply` lifecycle: plain classes with forge-cli's own attribute names and signatures. They are summarised here and covered in full in [plugin-groups.md](plugin-groups.md).

## When to pick which

```
Are you... ?
│
├── Provisioning or mutating cloud resources (datasets, tables, IAM, ...)
│     → InfraProvider          (entry-point: fluid_build.providers)
│
├── Writing files (CI configs, app code, IaC stacks, generated config)
│     → CustomScaffold         (entry-point: fluid_build.custom_scaffolds)
│
├── Inspecting a contract and emitting findings (governance, compliance)
│     → Validator              (entry-point: fluid_build.validators)
│
├── Syncing product metadata to an external catalog (DataHub, Atlan, ...)
│     → CatalogAdapter         (entry-point: fluid_build.catalog_adapters)
│
├── Adding where a generated DAG sends its alerts (Teams, a pager, ...)
│     → AlertNotifier          (entry-point: fluid_build.alert_notifiers, forge-cli 0.38.0+)
│       an organisation's default routes: alert_route (fluid_build.alert_defaults, 0.38.0+)
│
├── Adding a step of an Iceberg table's maintenance (an erasure, a purge)
│     → MaintenanceAction      (entry-point: fluid_build.maintenance_actions, forge-cli 0.38.0+)
│
├── Adding a `fluid <name>` subcommand
│     → CommandPlugin          (entry-point: fluid_build.commands, forge-cli 0.8.3+)
│
└── None of the above
      → BasePlugin (raw)       (entry-point: pick or propose a new group)
```

---

## InfraProvider

**Subclass for plugins that talk to cloud APIs.**

Defaults: `planning=True, apply=True, render=False, auth=True, graph=True`, everything else `False`.

```python
from fluid_sdk import InfraProvider, PluginAction, ExecutionResult, ContractHelper

class BigQueryProvider(InfraProvider):
    name = "bigquery"

    def plan(self, contract):
        c = ContractHelper(contract)
        actions = []
        for expose in c.exposes():
            if expose.platform != "gcp":
                continue
            actions.append(
                PluginAction(
                    op="bq.ensure_dataset",
                    resource_type="dataset",
                    resource_id=expose.dataset or expose.id,
                    params={"project": expose.project, "location": expose.region},
                    phase="infrastructure",
                ).to_dict()
            )
        return actions

    def apply(self, actions):
        # Call google-cloud-bigquery here.
        ...
```

Conformance: use `InfraProviderTestHarness`.

---

## CustomScaffold

**Subclass for plugins that generate files from a contract.**

Defaults: `planning=True, apply=True, render=True, dry_run=True, schema_validation=True`, everything else `False`.

Adds a constructor parameter `output_root: Path` and a reference `apply()` that writes `write_file` actions to disk atomically, with path-traversal protection.

```python
from fluid_sdk import CustomScaffold, write_file_action, ContractHelper

class GitHubActionsScaffold(CustomScaffold):
    name = "github-actions-scaffold"

    def plan(self, contract):
        c = ContractHelper(contract)
        return [
            write_file_action(
                path=".github/workflows/build.yml",
                content=self._render_ci(c).encode("utf-8"),
                description="GitHub Actions CI",
            ).to_dict(),
        ]

    def _render_ci(self, c):
        return f"# CI for {c.id}\nname: build\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n"
```

**The `apply()` is inherited from `CustomScaffold` and almost never needs overriding.** It:

1. Decodes `params.content_b64` for each `write_file` action.
2. Verifies the sha256 hash matches what `plan()` recorded.
3. Resolves the target path under `output_root` and rejects path-traversal attempts.
4. Creates parent directories.
5. Writes via an exclusively created tmpfile (a random name, never a predictable one, so a planted symlink is never followed) + atomic rename.
6. Chmod's per `params.mode`.
7. Returns an `ExecutionResult` with `applied` / `failed` counts + `artifacts` paths.

Conformance: use `CustomScaffoldTestHarness`. The harness automatically verifies determinism, idempotency, path-traversal safety.

---

## Validator

**Subclass for plugins that inspect a contract and emit findings.**

Defaults: `planning=True, apply=False, schema_validation=True, dry_run=True`, everything else `False`.

```python
from fluid_sdk import Validator, Finding, ContractHelper

class StewardRequiredValidator(Validator):
    name = "steward-required"

    def plan(self, contract):
        c = ContractHelper(contract)
        findings = []

        steward_id = c.metadata.get("labels", {}).get("principal.steward.id")
        if not steward_id:
            findings.append(Finding(
                severity="error",
                code="STEWARD_MISSING",
                message=f"Contract {c.id!r} is missing metadata.labels['principal.steward.id']",
                path='metadata.labels["principal.steward.id"]',
                remediation="Add a steward identifier to metadata.labels.",
            ))

        return [f.to_action().to_dict() for f in findings]
```

The default `apply()` (inherited from `Validator`) summarises findings by severity and returns an `ExecutionResult` with `applied = info+warn count` and `failed = error+critical count`. CLI uses these counts to determine exit status.

Severities (mapped to CLI exit behaviour):

| Severity | CLI behaviour |
|---|---|
| `info` | reported, no exit-code change |
| `warn` | reported with `[WARN]`, no exit-code change |
| `error` | reported with `[ERROR]`, non-zero exit code |
| `critical` | reported with `[CRITICAL]`, non-zero exit + halts pipeline |

Conformance: use `ValidatorTestHarness`. The harness verifies that every action with `op="emit_finding"` has a valid `severity`.

---

## CatalogAdapter

**Subclass for plugins that sync product metadata to an external catalog.**

Defaults: `planning=True, apply=True, dry_run=True, auth=True, lineage=True`, everything else `False`.

```python
from fluid_sdk import CatalogAdapter, PluginAction, ContractHelper

class DataHubAdapter(CatalogAdapter):
    name = "datahub"

    def plan(self, contract):
        c = ContractHelper(contract)
        return [
            PluginAction(
                op="catalog.upsert",
                resource_type="dataset",
                resource_id=c.id or "unknown",
                params={
                    "urn": f"urn:li:dataset:(urn:li:dataPlatform:fluid,{c.id},PROD)",
                    "facets": {
                        "description": c.description,
                        "tags": c.tags,
                        "owner": c.owner.get("email"),
                    },
                },
                phase="catalog",
            ).to_dict(),
        ]

    def apply(self, actions):
        # POST to DataHub REST API.
        ...
```

Conformance: use `CatalogAdapterTestHarness`.

---

## AlertNotifier

**Subclass to add a route kind for the alerts of the DAGs `fluid generate schedule` writes.** Needs forge-cli 0.38.0 or later (group `fluid_build.alert_notifiers`).

No `plan` / `apply`: set `notifier` (the Airflow notifier the DAG imports, `"<module>:<class>"`) and implement `kwargs(route, alert)`, which returns the notifier's keyword arguments as literals.

```python
from fluid_sdk import AlertNotifier

class ChatNotifier(AlertNotifier):
    notifier = "acme_alerts.notifiers:ChatNotifier"

    def kwargs(self, route, alert):
        return {"message": alert.title, "chat_conn_id": route.connection}
```

A route names a connection only when the kind requires one and has no `default_connection`; when it names none, forge-cli 0.39.0 hands the kind its `default_connection` as `route.connection`.

An organisation's default routes are a second group, `fluid_build.alert_defaults`: an entry point that loads to a list of routes (or a function that returns one), built with `alert_route(...)`, which refuses the shapes the SDK's copy of forge-cli's route rules refuses (forge-cli may refuse more).

Conformance: use `AlertNotifierTestHarness`. Details, attributes and rules: [plugin-groups.md](plugin-groups.md#alertnotifier).

---

## MaintenanceAction

**Subclass to add a step of an Iceberg table's maintenance.** Needs forge-cli 0.38.0 or later (group `fluid_build.maintenance_actions`).

Implement `statements(table, options)`, which returns SQL (each statement one `DELETE`, `UPDATE` or `MERGE` on the action's own table), and `check(options)`, which returns the problems with the options. forge-cli compiles the statements into the plan and runs them before compaction.

```python
from fluid_sdk import MaintenanceAction, sql_literal

class ErasePurpose(MaintenanceAction):
    def statements(self, table, options):
        return [f"DELETE FROM {table} WHERE purpose = {sql_literal(options['purpose'])}"]
```

Conformance: use `MaintenanceActionTestHarness`. Details and rules: [plugin-groups.md](plugin-groups.md#maintenanceaction).

---

## CommandPlugin

**Subclass to add a `fluid <name>` subcommand.** Group `fluid_build.commands`, read by forge-cli 0.8.3 and later.

Set `name` and `help`, override `configure(parser)` and `run(args, logger)`, and register an *instance*: forge-cli calls the loaded object with the CLI's subparsers.

```python
from fluid_sdk import CommandPlugin

class HelloCommand(CommandPlugin):
    name = "acme-hello"
    help = "Print a greeting"

    def run(self, args, logger):
        print("hello")
        return 0

command = HelloCommand()
```

Conformance: use `CommandPluginTestHarness`. Details: [plugin-groups.md](plugin-groups.md#commandplugin).

---

## When to subclass `BasePlugin` directly

Rare. Pick this only if:

- Your plugin's lifecycle doesn't fit any of the seven roles.
- You're prototyping a fifth role that doesn't exist yet.
- You want to mix two roles in one plugin (e.g. a custom-scaffold + validator hybrid).

Forge-cli's discovery may still need to know how to route you — register under whichever entry-point group most closely matches your behaviour, or propose a new group via SDK contribution.
