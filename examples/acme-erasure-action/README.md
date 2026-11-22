# acme-erasure-action

Example maintenance action (`MaintenanceAction`). Needs forge-cli 0.38.0 or later, which first
reads the `fluid_build.maintenance_actions` entry-point group.

A contract names the kind in an Iceberg expose's maintenance block:

```yaml
exposes:
  - exposeId: orders
    binding:
      platform: aws
      format: iceberg
      location: {database: silver, table: orders}
    iceberg:
      maintenance:
        backend: spark
        schedule: "0 3 * * *"
        actions:
          - {name: erase, kind: acme-erase, options: {requests: gdpr.requests}}
```

forge-cli compiles the action's statements into the job config the plan binds. Its Spark runner
runs them before compaction, so the rows' files are rewritten and the snapshots that held them
expire in the same run:

```sql
DELETE FROM fluid.silver.orders WHERE customer_id IN
  (SELECT customer_id FROM fluid.gdpr.requests WHERE status = 'approved')
```

```bash
pip install -e ".[dev]"     # sqlglot makes the harness parse statements as forge-cli does
pytest -v
```
