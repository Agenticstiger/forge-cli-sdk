# acme-chat-alerts

Example alert route kind (`AlertNotifier`) and organisation default route (`alert_route`). Needs
forge-cli 0.38.0 or later, which first reads the `fluid_build.alert_notifiers` and
`fluid_build.alert_defaults` entry-point groups.

- `acme_alerts.forge.ChatNotifier` is the kind. A contract route with `kind: acme-chat` renders
  `acme_alerts.notifiers.ChatNotifier(**kwargs)` into the DAGs `fluid generate schedule` writes.
- `acme_alerts.notifiers.ChatNotifier` is the Airflow notifier those DAGs import. Only Airflow
  imports it; it posts to the webhook URL held in an Airflow connection.
- `acme_alerts.defaults.default_routes` adds an `org-oncall` route to every product that does not
  set `alerts.defaults: false`.

```yaml
# in a contract
alerts:
  sla: PT4H
  routes:
    - name: team
      kind: acme-chat
      connection: acme_chat_team
      events: [failure, sla_miss]
      options: {channel: data-team}
```

```bash
pip install -e ".[dev]"
pytest -v
```
