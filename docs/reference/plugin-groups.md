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
| `CommandPlugin` | `fluid_build.commands` | forge-cli 0.8.3 (first as 0.8.3rc1); lazy loading and the allow/block policy from 0.11.0 | An extra `fluid <name>` subcommand |

The two alert groups and the maintenance group follow the operator's plugin policy from their first
release: an entry point is read by name, never imported by `fluid --help` or by listing plugins,
and `FLUID_PLUGINS_ALLOWLIST` / `FLUID_PLUGINS_BLOCKLIST` apply to the entry-point name before
anything is imported. A plugin that fails to load is reported by exception type only, never by its
message. For `fluid_build.commands` that policy, lazy loading and the one-argument `func(args)`
adapter arrive with forge-cli 0.11.0 (see [CommandPlugin](#commandplugin)).

forge-cli is the authority on every rule below. The SDK carries a conservative copy of them so a
plugin can be tested without forge-cli installed; a plugin that passes the SDK's checks can still
be refused by forge-cli, which has rules the zero-dependency SDK cannot carry.

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
    requires_connection = True              # the default below satisfies it
    default_connection = "acme_chat_default"

    def check(self, route: AlertRoute):
        return []   # problems with the route, each a sentence

    def kwargs(self, route: AlertRoute, alert: Alert):
        return {
            "message": alert.title,
            "chat_conn_id": route.connection,   # the route's own, else default_connection
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
| `requires_connection` | `True` | Whether a route must name an Airflow connection. A route needs to name one only when this is `True` and `default_connection` is `None` (forge-cli 0.39.0; 0.38.0 required it whenever this was `True`) |
| `default_connection` | `None` | The connection a route that names none uses. forge-cli 0.39.0 hands `check` and `kwargs` this as `route.connection`, so the kind needs no fallback; a connection the route names wins |

What forge-cli enforces, and what `AlertNotifierTestHarness` checks the same way:

- The entry-point name is a kind name (lower case letters, digits, `_`, `-`) and is not a built-in
  kind's name. A plugin adds a kind and never replaces one. (forge-cli also refuses a name two
  packages both ship; the harness cannot see other packages, so it does not check that.)
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
`alert_route` builds one and raises `ValueError` for a shape the SDK's copy of forge-cli's route
rules refuses, never quoting a value (forge-cli may refuse more):

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
with no template syntax, URL or secret-named key). A string the route gives (`name`, `kind`,
`connection`, `format` and every option string) is also refused when it has a shape forge-cli's
redactor masks: provider key prefixes, `Bearer`, a JWT, a PEM block, URL user info, a `key=value`
with a credential-named key, and the incident and chat webhook URLs. Option keys follow forge-cli's
`secret_option_key`, by whole words (`private_key`, `signingKey`, `auth`, `key` and `pwd` are
credential names; `max_tokens` and `secretary` are not). These are vendored copies of forge-cli's
own patterns, kept in step with it, but its redactor has more rules than a zero-dependency SDK
can carry, and it also asks the route's kind. forge-cli remains the authority and may refuse
more. The defaults are loaded when a DAG is rendered or a contract validated, and
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
- `check` returns a list of sentences (forge-cli refuses a bare string). A missing `check` means no
  problems.
- Not quoting an option value in a `check` message is the SDK's own rule, not forge-cli's:
  forge-cli prints the first problem as the action returns it, so a quoted value would be printed,
  and a value may be a secret. The harness checks it.

forge-cli parses statements as Spark SQL through `sqlglot`. The SDK has no dependencies, so
`statement_problem` always applies the text rules above and parses with `sqlglot` only when it is
installed. Without it the target is read by text, right after `DELETE FROM`, `UPDATE` or
`MERGE INTO` (after a leading `WITH` clause, with backticks and spaces around dots accepted), and
a statement that does not parse as Spark SQL, or whose target an unusual spelling hides, can
pass; the harness warns when `sqlglot` is absent. forge-cli stays the authority and parses.

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

A package adds a `fluid <name>` subcommand through `fluid_build.commands`. The group appeared in
forge-cli 0.8.3rc1 and 0.8.3. From forge-cli 0.11.0 on, forge-cli reads the entry-point names from
metadata and imports a plugin only when the invoked command is not one of its own, so
`fluid --help` and every core command import nothing from it; the operator's allow/block policy
applies to the entry-point name; and `func` may take one argument. Before 0.11.0 forge-cli imported
every command plugin when it built the parser and called `func(args, logger)`. The loaded object
is called with the CLI's argparse `subparsers`; each parser it adds carries a `func` default,
which forge-cli 0.11.0 and later calls as `func(args, logger)` (or `func(args)` when `func` has
fewer than two positional parameters and no `*args`) and whose return value is the exit code.

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
sets a runnable `func` on every parser (forge-cli's arity rule: with two or more positional
parameters the third and later need a default), and that `--help` exits cleanly. Importing the
module is checked the same way. forge-cli sets no pattern for a command name, so the harness has
none either. forge-cli 0.39.0 refuses a plugin that registers the name or an alias of one of its own
commands, skipping that plugin and loading the others (earlier, argparse let the last registration
win on Python 3.10 and raised on 3.11 and later); the harness checks every added name against the
core command names the SDK vendors from forge-cli. `reserved_command_names` adds names of your own on
top of those, and `check_core_command_names = False` turns the core check off for a forge-cli before
0.39.0. The entry point is a callable `(subparsers) -> None`.

```python
from fluid_sdk.testing import CommandPluginTestHarness

class TestHello(CommandPluginTestHarness):
    command_entry_point = command
    expected_commands = ("acme-hello",)
```
