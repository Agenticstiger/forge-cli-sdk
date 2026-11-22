# Alert, maintenance and command plugins

Three roles describe plugin groups that have no `plan` / `apply` lifecycle. The FLUID CLI
(forge-cli) reads a few attributes, or calls one method, on whatever an entry point loads. The SDK
gives each a typed class with forge-cli's own names and signatures, plus a conformance harness.
None of the classes subclasses `BasePlugin`, and forge-cli does not require the SDK: a package may
write the same attributes by hand and register it the same way.

| Role | Entry-point group | First read by | What it adds |
|---|---|---|---|
| `AlertNotifier` | `fluid_build.alert_notifiers` | forge-cli 0.38.0 | A route kind for the alerts of generated DAGs |
| `alert_route` helper | `fluid_build.alert_defaults` | forge-cli 0.38.0 | An organisation's default alert routes |
| `MaintenanceAction` | `fluid_build.maintenance_actions` | forge-cli 0.38.0 | A step of an Iceberg table's maintenance that returns SQL |
| `CommandPlugin` | `fluid_build.commands` | forge-cli 0.8.3 (first as 0.8.3rc1) | An extra `fluid <name>` subcommand |

All three groups follow the operator's plugin policy, as every plugin does: an entry point is read
by name, never imported by `fluid --help` or by listing plugins, and `FLUID_PLUGINS_ALLOWLIST` /
`FLUID_PLUGINS_BLOCKLIST` apply to the entry-point name before anything is imported. A plugin that
fails to load is reported by exception type only, never by its message.

Runnable packages: [`examples/acme-chat-alerts`](../../examples/acme-chat-alerts/),
[`examples/acme-erasure-action`](../../examples/acme-erasure-action/),
[`examples/acme-hello-command`](../../examples/acme-hello-command/).

---

## AlertNotifier

A contract declares alert routes (`alerts.routes`): who hears about a failed task, a retry, a
success or a missed SLA of the DAGs `fluid generate schedule` writes, and how. A route's `kind` is
`email`, `slack`, `webhook`, `pagerduty`, or the name of an entry point in
`fluid_build.alert_notifiers`. The kind names an Airflow notifier (a `BaseNotifier` subclass the
Airflow workers can import) and builds its keyword arguments for one alert. The DAG instantiates
`Notifier(**kwargs)` when the event happens; forge-cli never runs the notifier.

```python
from fluid_sdk import Alert, AlertNotifier, AlertRoute

class ChatNotifier(AlertNotifier):
    notifier = "acme_alerts.notifiers:ChatNotifier"   # what the DAG imports
    requirements = ("acme-chat-alerts>=0.1",)         # what Airflow must install
    requires_connection = False
    default_connection = "acme_chat_default"

    def check(self, route: AlertRoute):
        return []   # problems with the route, each a sentence

    def kwargs(self, route: AlertRoute, alert: Alert):
        return {
            "message": alert.title,
            "chat_conn_id": route.connection or self.default_connection,
        }
```

```toml
[project.entry-points."fluid_build.alert_notifiers"]
acme-chat = "acme_alerts.forge:ChatNotifier"
```

The attributes, with their defaults:

| Attribute | Default | Meaning |
|---|---|---|
| `notifier` | `""` | `"<module>:<class>"` of the Airflow notifier. Dotted identifiers only, since it is written into the DAG as an import |
| `requirements` | `()` | Plain pip requirements the Airflow environment needs (no quote, backslash or newline) |
| `supports_async` | `False` | Whether the notifier implements `async_notify`. Airflow 3 has no SLAs, so an `sla_miss` route alerts there through a deadline alert, which runs the notifier in the triggerer and needs it |
| `async_requirements` | `()` | What the triggerer needs, when newer than `requirements` |
| `events` | all four | The events the kind can send (`failure`, `retry`, `success`, `sla_miss`). A route that asks for another is refused |
| `requires_connection` | `True` | Whether a route must name an Airflow connection. `default_connection` does not satisfy this: a kind whose routes may omit the connection sets it to `False` |
| `default_connection` | `None` | The connection the notifier uses when a route names none |

What forge-cli enforces, and what `AlertNotifierTestHarness` checks the same way:

- The entry-point name is a kind name (lower case letters, digits, `_`, `-`) and is not a built-in
  kind's name. A plugin adds a kind and never replaces one. Two packages shipping one name are both
  refused.
- `kwargs` returns literals only (str, int, float, bool, None, and lists and string-keyed dicts of
  them), keyed by Python identifiers. `context` is reserved: Airflow passes it.
- `kwargs` is called once for each event the route sends, so a route that passes `fluid validate`
  renders. A string may hold Jinja for Airflow's context (`{{ ti.task_id }}`); a route's own values
  are already checked to hold no template syntax, URL or secret.
- A route never carries a secret. `connection` names the Airflow connection that holds the URL or
  key. `check` must not quote a route value.

### Default routes (`alert_defaults`)

An organisation's pack adds routes to every product's DAGs. A contract opts out with
`alerts.defaults: false`, or replaces one by naming a route of its own the same. The entry point
loads to a list of routes written as a contract writes them, or to a function that returns one.
`alert_route` builds one and refuses a shape forge-cli would refuse, never quoting a value:

```python
from fluid_sdk import alert_route

def default_routes():
    return [
        alert_route("org-oncall", "acme-chat", connection="acme_chat_oncall",
                    events=["failure"], severity="critical", options={"channel": "ops-oncall"}),
    ]
```

```toml
[project.entry-points."fluid_build.alert_defaults"]
acme = "acme_alerts.defaults:default_routes"
```

`check_alert_route(raw)` returns the problems as a list. It checks the route's shape (keys, `name`,
`kind`, `events`, `connection`, `severity`, the email keys, and `options`, which holds JSON values
with no template syntax, URL or secret-named key). It cannot ask the route's kind, so forge-cli
remains the authority. The defaults are loaded when a DAG is rendered or a contract validated, and
a defaults entry point that fails refuses the render.

### Testing

```python
from fluid_sdk import AlertRoute
from fluid_sdk.testing import AlertNotifierTestHarness

class TestChat(AlertNotifierTestHarness):
    notifier_class = ChatNotifier
    entry_point_name = "acme-chat"
    sample_routes = [AlertRoute(name="team", kind="acme-chat", connection="acme_chat_team")]
```

---

## MaintenanceAction

A contract declares, per Iceberg expose, what keeps the table healthy
(`exposes[].iceberg.maintenance`): compaction, manifests, snapshot expiry, orphan removal and a
package's own actions, such as erasing the rows a request names. An action's `kind` is the name of
an entry point in `fluid_build.maintenance_actions`. Its `statements(table, options)` returns SQL;
forge-cli compiles it into the job config the plan binds, and its Spark runner runs it before
compaction, so the rows' files are rewritten and the snapshots that held them expire in the same
run.

```python
from fluid_sdk import MaintenanceAction, sql_literal

class ErasePurpose(MaintenanceAction):
    def check(self, options):
        if not isinstance(options.get("purpose"), str):
            return ["options.purpose must be a string"]
        return []

    def statements(self, table, options):
        return [f"DELETE FROM {table} WHERE purpose = {sql_literal(options['purpose'])}"]
```

```toml
[project.entry-points."fluid_build.maintenance_actions"]
erase-purpose = "acme_pack.maintenance:ErasePurpose"
```

The entry point names a class (built with no arguments), an instance, or a function that returns
one. What forge-cli enforces on the statements, and what `statement_problem` and
`MaintenanceActionTestHarness` check the same way:

- Each statement is exactly one `DELETE`, `UPDATE` or `MERGE` whose target is the action's own
  table, named as the runner's catalog holds it (`fluid.<database>.<table>`). It may read other
  tables. Anything else (DDL, a second statement) is refused.
- No `${...}` variable, no comment (`--` or `/*`, even inside a string), no backslash, no control
  character, and at most 20,000 characters.
- `statements` returns a non-empty list, and the same table and options give the same statements:
  they are part of the plan, which the plan digest binds.
- `sql_literal(value)` writes a string as a literal that passes, and refuses a value holding a
  quote or any of the characters above.
- `check` returns sentences and never quotes an option value, which may be a secret.

forge-cli parses statements as Spark SQL through `sqlglot`. The SDK has no dependencies, so
`statement_problem` always applies the text rules above and parses with `sqlglot` only when it is
installed; without it the target check is a text match. forge-cli stays the authority.

### Testing

```python
from fluid_sdk.testing import MaintenanceActionTestHarness

class TestErase(MaintenanceActionTestHarness):
    action_class = ErasePurpose
    table = "fluid.silver.orders"
    sample_options = [{"purpose": "marketing"}]
    bad_options = [{"purpose": 42}]
```

---

## CommandPlugin

A package adds a `fluid <name>` subcommand through `fluid_build.commands`. forge-cli reads the
entry-point names from metadata and imports a plugin only when the invoked command is not one of
its own, so `fluid --help` and every core command import nothing from it. The loaded object is
called with the CLI's argparse `subparsers`; each parser it adds carries a `func` default, which
forge-cli calls as `func(args, logger)` (or `func(args)` when `func` takes one positional argument)
and whose return value is the exit code.

```python
from fluid_sdk import CommandPlugin

class HelloCommand(CommandPlugin):
    name = "acme-hello"
    help = "Print a greeting"

    def configure(self, parser):
        parser.add_argument("--who", default="world")

    def run(self, args, logger):
        print(f"hello {args.who}")
        return 0

command = HelloCommand()   # name the instance, not the class
```

```toml
[project.entry-points."fluid_build.commands"]
acme = "acme_cli.command:command"
```

forge-cli calls `entry_point.load()(subparsers)`, so the entry point must name a function or an
instance. An instance of `CommandPlugin` is callable; the class is not, and forge-cli would call it
with the subparsers as its constructor argument. `CommandPluginTestHarness` checks that, and that
registering adds a command and prints nothing, leaves the working directory and environment alone,
sets a runnable `func` on every parser, and that `--help` exits cleanly. Importing the module is
checked the same way. Set `reserved_command_names` to the CLI's own commands to check that the
plugin does not add one again.

```python
from fluid_sdk.testing import CommandPluginTestHarness

class TestHello(CommandPluginTestHarness):
    command_entry_point = command
    expected_commands = ("acme-hello",)
```
