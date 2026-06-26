# End-to-end — from `pip install` to generated files

**Time:** 10 minutes | **Difficulty:** Intermediate | **Prerequisites:** [Your first real plugin](your-first-real-plugin.md)

You've built a plugin, you've tested it, you've published it to PyPI. Now what does the **end user** experience look like? This walkthrough is from the user's perspective — what they install, what they configure, what they run.

## What the end-user has to do

Three pip installs + one contract change:

```bash
# 1. Install the FLUID CLI (~40 deps — most are providers like google-cloud-bigquery)
pip install data-product-forge

# 2. Install the custom-scaffold engine (the rendering layer)
pip install data-product-forge-custom-scaffold

# 3. Install YOUR plugin
pip install gitlab-ci-scaffold

# 4. Verify the FLUID CLI discovered your plugin
fluid plugins list
```

```
NAME              ROLE              VERSION  AUTHOR              DESCRIPTION
local             provider          0.8.0    (built-in)          Local DuckDB provider
gcp               provider          0.8.0    (built-in)          GCP BigQuery / GCS / Pub/Sub
snowflake         provider          0.8.0    (built-in)          Snowflake provider
gitlab-ci         custom_scaffold   0.1.0    Example Author      Generates a complete GitLab CI scaffold
```

Your plugin shows up under its role. Discovery worked.

## Step 1 — User's existing contract

```yaml
# contract.fluid.yaml
fluidVersion: "0.7.4"
kind: DataProduct
id: my-data-product
name: My Data Product
description: A nightly aggregation of yesterday's events.
metadata:
  owner: {team: platform, email: platform@example.com}
exposes:
  - exposeId: events
    binding: {platform: local, format: parquet, location: {path: ./out/events.parquet}}
environments:
  dev:
    metadata:
      labels: {"cloud.accountId": "111111111111", "cloud.region": "eu-west-1"}
  staging:
    metadata:
      labels: {"cloud.accountId": "222222222222", "cloud.region": "eu-west-1"}
  prod:
    metadata:
      labels: {"cloud.accountId": "333333333333", "cloud.region": "eu-west-1"}
```

This contract works fine on its own. Adding your scaffold is a 6-line opt-in:

## Step 2 — User declares the scaffold

```yaml
# contract.fluid.yaml — added at the bottom
extensions:
  customScaffold:
    libraries:
      - id: ci
        source: { kind: pypi, package: gitlab-ci-scaffold, version: ">=0.1" }
    patterns:
      - use: ci:gitlab-ci
```

## Step 3 — User runs `fluid generate custom-scaffold`

```bash
fluid generate custom-scaffold
```

> **Illustrative output** — the lines below sketch the *shape* of a successful run
> (resolve libraries → plan the pattern → write files). The exact wording and
> formatting are produced by the `data-product-forge-custom-scaffold` engine and
> may differ from what you see here; treat this as a mental model, not a literal
> transcript.

```text
[INFO] Resolving customScaffold libraries...
[INFO]   gitlab-ci-scaffold 0.1.0 — already installed (pypi)
[INFO] Planning pattern: gitlab-ci:gitlab-ci
[INFO]   ✓ README.md
[INFO]   ✓ .gitlab-ci.yml
[INFO]   ✓ config/dev.json
[INFO]   ✓ config/prod.json
[INFO]   ✓ config/staging.json
[INFO] Applying 5 actions...
[INFO] ✓ 5 files written, 0 failed (0.04s)

Wrote:
  README.md                     (442 bytes)
  .gitlab-ci.yml                (652 bytes)
  config/dev.json               (231 bytes)
  config/prod.json              (231 bytes)
  config/staging.json           (231 bytes)
```

The files appear on disk, ready to commit.

## Step 4 — User changes the contract → regenerates

```yaml
# contract.fluid.yaml — added a new env
environments:
  qa:                           # NEW
    metadata:
      labels: {"cloud.accountId": "444444444444", "cloud.region": "eu-west-1"}
  dev:    {...}
  staging:    {...}
  prod:    {...}
```

```bash
fluid generate custom-scaffold
```

```
[INFO] Wrote:
  README.md                     (modified — env list updated)
  .gitlab-ci.yml                (modified — new deploy:qa: job)
  config/dev.json               (unchanged)
  config/prod.json              (unchanged)
  config/qa.json                (new)
  config/staging.json           (unchanged)
```

The output adapts to the contract. Determinism guarantees: same contract → same bytes. The user can commit these files knowing CI will regenerate exactly the same output.

## What happens behind the scenes

```
┌──────────────────────────────────────────────────────────────┐
│  User runs: fluid generate custom-scaffold                    │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  data-product-forge CLI                                              │
│    1. Loads contract.fluid.yaml                              │
│    2. Validates against fluid-schema-0.7.4.json              │
│    3. Discovers entry-point fluid_build.commands             │
│       → fluid_build_custom_scaffold.cli:register             │
│    4. Dispatches to the engine                               │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  data-product-forge-custom-scaffold (the engine)                     │
│    1. Reads contract.extensions.customScaffold                │
│    2. Resolves each library (PyPI / npm / git / path)         │
│    3. For each pattern, instantiates the plugin via the       │
│       fluid_build.custom_scaffolds entry-point                │
│    4. Calls plugin.plan(contract)                             │
│    5. Calls plugin.apply(actions)                             │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  Your plugin (gitlab-ci-scaffold)                             │
│    plan(contract) → list of write_file actions               │
│    apply(actions) → atomically writes each file              │
└──────────────────────────────────────────────────────────────┘
```

You never wrote any of this dispatch logic. The FLUID CLI knew how to find your plugin because of two entry-points:

1. `[project.entry-points."fluid_build.commands"] generate-custom-scaffold = ...` (in the engine package — adds the subcommand to the CLI)
2. `[project.entry-points."fluid_build.custom_scaffolds"] gitlab-ci = ...` (in YOUR package — registers the plugin)

The first gives the CLI a new command; the second gives that command something to dispatch to.

## What goes in CI

The user commits:

- `contract.fluid.yaml` (their source of truth)
- The generated files (`README.md`, `.gitlab-ci.yml`, `config/*.json`)

Their `.gitlab-ci.yml` looks like this (because your scaffold generated it):

```yaml
stages:
  - validate
  - deploy

validate:
  stage: validate
  script:
    - pip install data-product-forge data-product-forge-custom-scaffold gitlab-ci-scaffold
    - fluid validate
    - fluid generate custom-scaffold --check  # fails if generated files drift from contract

deploy:dev:
  stage: deploy
  script:
    - fluid apply --env dev
  only:
    - main

# ... staging, prod ...
```

The `--check` flag (provided by the engine) re-runs the scaffold in memory and asserts byte-identity with the committed files. If a developer hand-edited a generated file, CI fails. If a developer changed the contract but forgot to regenerate, CI fails. **The contract is the source of truth.**

## Pin versions for reproducibility

Production users typically pin the plugin version in the contract:

```yaml
extensions:
  customScaffold:
    libraries:
      - id: ci
        source: { kind: pypi, package: gitlab-ci-scaffold, version: "==0.1.0" }  # exact pin
```

…and also write a `fluid-scaffold.lock.json` (auto-generated by `fluid generate custom-scaffold --lock`) that records exact hashes. CI verifies the lock on every run.

## Multi-plugin contracts

A contract can use multiple plugins:

```yaml
extensions:
  customScaffold:
    libraries:
      - id: ci
        source: { kind: pypi, package: gitlab-ci-scaffold, version: ">=0.1" }
      - id: governance
        source: { kind: pypi, package: steward-validator, version: ">=0.1" }
      - id: tf
        source: { kind: pypi, package: terraform-scaffold, version: ">=0.2" }
    patterns:
      - use: ci:gitlab-ci
      - use: tf:terraform
      # steward-validator is a Validator, not a CustomScaffold — it auto-runs
      # under `fluid validate` because of its role, no patterns: entry needed.
```

## Distribution alternatives

Not every plugin needs PyPI. The engine supports four source kinds:

| Kind | When to use |
|---|---|
| `pypi` | Public or internal PyPI — standard distribution |
| `npm` | Your plugin is shipped as an npm package (engine pulls + extracts) |
| `git` | Plugin lives in a git repo — no PyPI release needed |
| `path` | Local development — point at a checked-out clone |

All four are first-class in the engine. The contract just changes one line:

```yaml
# git
source: { kind: git, url: "https://github.com/me/my-scaffold", ref: "v1.0" }

# local (dev only)
source: { kind: path, path: "../my-scaffold-checkout" }

# npm
source: { kind: npm, package: "@me/my-scaffold", version: "1.0" }
```

## Summary

- **Plugin author** writes ~150 LOC and runs `python -m build && twine upload`.
- **End user** runs three `pip install` commands and adds 6 lines to their contract.
- **FLUID CLI** discovers everything via entry-points, no manual registration anywhere.

That's the whole story.

## What's next?

| If you want to... | Go to |
|---|---|
| Build a Validator plugin | [walkthrough/build-a-validator.md](build-a-validator.md) (uses the `steward-validator` example as the basis) |
| Understand the engine's resolver / lockfile | [`data-product-forge-custom-scaffold` docs](#) — separate repo |
| See more real examples | [`examples/`](../../examples/) |
