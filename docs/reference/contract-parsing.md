# Contract parsing — `ContractHelper`

The FLUID contract schema evolves across versions (0.4.0 → 0.5.7 → 0.7.x → …). Plugin authors should never have to detect schema versions themselves or branch on legacy field names.

`ContractHelper` is a read-only, typed facade over any contract dict. It absorbs version drift; plugin code stays stable.

## Basic usage

```python
from fluid_sdk import ContractHelper

helper = ContractHelper(contract_dict)

# Identity
helper.id                # "billing-source"
helper.name              # "Billing Source"
helper.fluid_version     # "0.7.4"
helper.kind              # "DataProduct"
helper.description       # str | None
helper.domain            # str | None

# Metadata
helper.metadata          # full metadata dict
helper.owner             # metadata.owner dict
helper.product_type      # "SDP" / "ADP" / "CDP" / None
helper.layer             # "bronze" / "silver" / "gold" / None
helper.tags              # top-level tags list
helper.labels            # top-level labels dict

# Exposes / consumes / builds
for expose in helper.exposes():   # List[ExposeSpec]
    print(expose.id, expose.platform, expose.format)

for consume in helper.consumes(): # List[ConsumeSpec]
    print(consume.id, consume.ref)

for build in helper.builds():     # List[BuildSpec]
    print(build.engine, build.pattern)

# Sovereignty / security / binding
helper.sovereignty       # dict
helper.security          # dict
helper.access_policy     # dict
helper.binding           # dict (top-level binding)
helper.binding_location  # dict (binding.location)

# Environments
helper.environments         # Dict[str, EnvironmentConfig]
helper.environment_names()  # sorted list of env names

# Plugin-namespace extensions
helper.extensions                       # full extensions: block
helper.extension("customScaffold")      # one sub-key, or empty dict
```

## Parsed entry types

### ExposeSpec

A typed view of one `exposes[]` entry. Handles both 0.4.0 (`location`-based) and 0.5.7+ (`binding`-based) shapes uniformly.

```python
expose = helper.exposes()[0]

expose.id                # str
expose.kind              # "table" | "view" | "topic" | None
expose.title, expose.version, expose.description

# Routing
expose.platform          # "gcp" | "aws" | "snowflake" | "local" | None
expose.format            # "bigquery_table" | "snowflake_table" | "parquet" | ...

# Location (normalised across binding shapes)
expose.database, expose.schema_name, expose.table
expose.bucket, expose.path
expose.dataset, expose.project, expose.region
expose.topic, expose.cluster, expose.view, expose.query

# Full location dict for plugin-specific fields
expose.location          # Dict[str, Any]

# Schema
expose.columns           # List[ColumnSpec]

# Governance
expose.policy, expose.tags, expose.labels

# Original dict (always available)
expose.raw               # Dict[str, Any]
```

### ColumnSpec

A single column / field definition.

```python
column = expose.columns[0]

column.name              # "id"
column.type              # "string"
column.required          # bool
column.nullable          # bool
column.description       # str | None
column.sensitivity       # "pii" | "restricted" | None
column.semantic_type     # str | None  (semanticType in 0.5.7+)
column.tags              # List[str]
column.labels            # Dict[str, str]
column.raw               # Dict[str, Any]
```

### ConsumeSpec

One `consumes[]` entry.

```python
consume = helper.consumes()[0]

consume.id               # str
consume.ref              # productId or ref
consume.path             # str | None
consume.format           # str | None
consume.required         # bool
consume.raw              # Dict[str, Any]
```

### BuildSpec

One `builds[]` entry — handles both `builds` (array) and `build` (single object) legacy shapes.

```python
build = helper.builds()[0]  # or helper.primary_build()

build.id                 # str
build.description        # str | None
build.pattern            # "embedded-logic" | "hybrid-reference" | "acquisition" | ...
build.engine             # "sql" | "dbt" | "python" | "spark" | ...
build.sql                # extracted from properties.sql OR transformation.properties.model
build.sql_file           # str | None
build.repository         # str | None
build.properties         # full properties dict
build.execution          # full execution dict
build.outputs            # List[str]
build.tags, build.labels
build.raw                # Dict[str, Any]
```

## The `extensions:` block

`extensions:` is the FLUID schema's plugin namespace. Each plugin claims a sub-key and stores its config there. Reading it from a plugin is one line:

```python
class MyScaffold(CustomScaffold):
    def plan(self, contract):
        c = ContractHelper(contract)
        my_config = c.extension("customScaffold")
        # my_config is a dict — the plugin's own JSON-Schema validates its shape
        ...
```

This pattern means a contract can configure many plugins simultaneously without schema drift in fluid core:

```yaml
extensions:
  customScaffold:
    libraries: [...]
    patterns: [...]
  myCustomCatalog:
    endpoint: https://catalog.example.com
    auth: {secretRef: CATALOG_TOKEN}
  governanceValidator:
    strictMode: true
```

## Why a typed facade, not raw dict access?

Plugins that reach into raw `contract["exposes"][0]["binding"]["location"]["path"]` break when:

- The contract version changes (binding shape changes — and it has, multiple times).
- A required key is missing (you get `KeyError`, not a graceful default).
- Optional keys move around (legacy `location` vs new `binding.location`).

`ContractHelper` smooths over all of that. The `.raw` attribute is always available if you need to drop down to raw dict access for plugin-specific fields.

## Backwards-compatible evolution

When the fluid contract schema bumps (0.7.4 → 0.8 → …):

- The SDK is updated to absorb the new shape in `ContractHelper.from_dict` paths.
- The SDK's version is bumped.
- Plugin authors pin `data-product-forge-sdk>=X.Y.Z` and get the new parsing for free.
- **Plugin code stays unchanged.**

This is the entire reason `ContractHelper` exists.
