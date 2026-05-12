# Build a Validator — custom governance rules

**Time:** 10 minutes | **Difficulty:** Beginner | **Prerequisites:** [Getting Started](../getting-started/README.md)

A `Validator` is the simplest kind of plugin — it doesn't generate files or talk to clouds, it just **inspects a contract and emits findings**. Use it to encode any governance, compliance, cost, or hygiene rule your organisation cares about.

This walkthrough builds a real validator: `steward-validator`. It fails any contract that doesn't declare a data steward. ~80 lines of plugin code, 22 conformance tests.

## What you'll build

A plugin that, when installed:

- Auto-enrols in every team's `fluid validate` run (no opt-in per project).
- Emits an `error` finding if `metadata.labels["principal.steward.id"]` is missing.
- Emits a `warn` finding if a steward ID is present but `principal.steward.email` is missing.
- Causes `fluid validate` to exit non-zero on `error`.

When a developer runs `fluid validate`:

```
[ERROR] STEWARD_ID_MISSING: Contract 'my-product' is missing the required label 'principal.steward.id'.
        ↳ Add metadata.labels['principal.steward.id'] with the employee/user identifier of the data steward.
[WARN]  STEWARD_EMAIL_MISSING: Contract 'my-product' declares a steward id but no email — operations notifications will go nowhere.
        ↳ Add metadata.labels['principal.steward.email'] with the steward's email address.

1 error, 1 warning. Exit code: 1.
```

The rule self-deploys to every team that installs your validator. Powerful.

## Step 1 — Skeleton

```bash
mkdir steward-validator && cd steward-validator
mkdir -p src/steward_validator tests
touch src/steward_validator/__init__.py
```

## Step 2 — `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "steward-validator"
version = "0.1.0"
requires-python = ">=3.9"
dependencies = ["data-product-forge-sdk>=0.9,<1"]

[project.optional-dependencies]
dev = ["pytest>=7.0"]

[project.entry-points."fluid_build.validators"]
steward-required = "steward_validator.validator:StewardValidator"

[tool.setuptools.packages.find]
where = ["src"]
```

Key line: the entry-point group is **`fluid_build.validators`** (not `fluid_build.custom_scaffolds`). The FLUID CLI walks this group at `fluid validate` time.

## Step 3 — The validator (`src/steward_validator/validator.py`)

```python
"""Steward Validator — fails contracts that don't declare a data steward."""

from __future__ import annotations

from typing import Any, List, Mapping

from fluid_sdk import (
    ContractHelper,
    Finding,
    PluginMetadata,
    Validator,
)


class StewardValidator(Validator):
    name = "steward-required"

    @classmethod
    def get_plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name=cls.name,
            role=cls.role,
            display_name="Steward Required Validator",
            description="Enforces metadata.labels['principal.steward.id'] on every contract.",
            version="0.1.0",
            author="Your Org Platform Team",
            tags=["governance", "compliance"],
        )

    def plan(self, contract: Mapping[str, Any]) -> List[dict]:
        c = ContractHelper(contract)
        findings: List[Finding] = []

        labels = (c.metadata.get("labels") or {})
        steward_id = labels.get("principal.steward.id")
        steward_email = labels.get("principal.steward.email")

        if not steward_id:
            findings.append(
                Finding(
                    severity="error",
                    code="STEWARD_ID_MISSING",
                    message=(
                        f"Contract {c.id!r} is missing the required label "
                        f"'principal.steward.id'."
                    ),
                    path='metadata.labels["principal.steward.id"]',
                    remediation=(
                        "Add metadata.labels['principal.steward.id'] with the "
                        "employee/user identifier of the data steward."
                    ),
                )
            )

        if steward_id and not steward_email:
            findings.append(
                Finding(
                    severity="warn",
                    code="STEWARD_EMAIL_MISSING",
                    message=(
                        f"Contract {c.id!r} declares a steward id but no email — "
                        "operations notifications will go nowhere."
                    ),
                    path='metadata.labels["principal.steward.email"]',
                    remediation=(
                        "Add metadata.labels['principal.steward.email'] with the "
                        "steward's email address."
                    ),
                )
            )

        return [f.to_action().to_dict() for f in findings]
```

That's the whole validator. `apply()` is inherited from `Validator` — it walks the findings, counts by severity, returns an `ExecutionResult` where `failed = error+critical count`. The FLUID CLI uses `failed > 0` to decide the exit code.

## Step 4 — Tests (`tests/test_validator.py`)

```python
from __future__ import annotations

from fluid_sdk.testing import ValidatorTestHarness

from steward_validator.validator import StewardValidator


MISSING = {
    "fluidVersion": "0.7.4",
    "id": "missing-steward-product",
    "metadata": {"owner": {"team": "x", "email": "x@example.com"}, "labels": {}},
}

WARN_ONLY = {
    "fluidVersion": "0.7.4",
    "id": "no-email-product",
    "metadata": {
        "owner": {"team": "x", "email": "x@example.com"},
        "labels": {"principal.steward.id": "emp-12345"},
    },
}

CLEAN = {
    "fluidVersion": "0.7.4",
    "id": "good-product",
    "metadata": {
        "owner": {"team": "x", "email": "x@example.com"},
        "labels": {
            "principal.steward.id": "emp-12345",
            "principal.steward.email": "steward@example.com",
        },
    },
}


class TestStewardValidator(ValidatorTestHarness):
    plugin_class = StewardValidator
    sample_contracts = [MISSING, WARN_ONLY, CLEAN]

    # ── domain-specific assertions ──────────────────────────────

    def test_missing_steward_emits_error(self):
        plugin = self.get_plugin()
        actions = plugin.plan(MISSING)
        assert len(actions) == 1
        assert actions[0]["params"]["severity"] == "error"
        assert actions[0]["params"]["code"] == "STEWARD_ID_MISSING"

    def test_warn_only(self):
        plugin = self.get_plugin()
        actions = plugin.plan(WARN_ONLY)
        assert len(actions) == 1
        assert actions[0]["params"]["severity"] == "warn"

    def test_clean(self):
        plugin = self.get_plugin()
        actions = plugin.plan(CLEAN)
        assert actions == []
```

## Step 5 — Run

```bash
pip install -e ".[dev]"
pytest -v
```

You'll see ~22 tests pass:

- ~13 from `ValidatorTestHarness` (subclass, name, role, finding severity validation, plan determinism, apply returns ExecutionResult, etc.)
- 3 you wrote

## Step 6 — How it surfaces for end users

User installs your plugin alongside the FLUID CLI:

```bash
pip install data-product-forge steward-validator
```

The FLUID CLI auto-discovers it via the `fluid_build.validators` entry-point. **No contract change required** — validators auto-enrol globally. The user just runs:

```bash
fluid validate
```

```
Validating contract.fluid.yaml...
[ERROR] STEWARD_ID_MISSING: Contract 'my-product' is missing the required label 'principal.steward.id'.
        ↳ Add metadata.labels['principal.steward.id'] with the employee/user identifier of the data steward.

1 error, 0 warnings. Exit code: 1.
```

CI fails. The user adds the label. Validation passes. **Your rule shipped.**

## Severity → CLI behaviour

| Severity | CLI behaviour |
|---|---|
| `info` | Reported (`[INFO]` prefix). Does not affect exit code. |
| `warn` | Reported (`[WARN]` prefix). Does not affect exit code. |
| `error` | Reported (`[ERROR]` prefix). Causes non-zero exit. |
| `critical` | Reported (`[CRITICAL]` prefix). Halts pipeline immediately. |

Pick severity based on the rule's importance — `error` is the right call for "must have a steward"; `warn` is right for "should have an email"; `info` is right for "consider documenting this".

## Common validators to build

- **Steward / owner required** (the example above)
- **Data classification not blank** (`metadata.classification` must be one of `[public, internal, confidential, restricted]`)
- **Owner email domain whitelist** (`metadata.owner.email` ends with `@your-org.com`)
- **Sovereignty constraint** (`sovereignty.regulatoryFramework` ⊂ `[GDPR, CCPA]` for products in regulated regions)
- **Cost guardrail** (warn if `binding.location.region` is an expensive region for this product type)
- **No PII in tags** (`tags` list contains no `pii-*` entries)
- **Min/max columns** (every expose has between 1 and 200 columns)

Each is a copy-and-rename of the example. ~50 lines of plugin code each.

## Why distribute as a plugin, not a CI script?

Two reasons:

1. **Self-deployment.** Every team that uses your validator gets it the moment they `pip install`. No "every team needs to add this CI step" memo.

2. **Local feedback.** Developers run `fluid validate` locally; your rule fires before they ever push. Catches violations seconds after they're introduced, not after CI fails 20 minutes later.

## What's next?

| If you want to... | Go to |
|---|---|
| See the full working example | [`examples/steward-validator/`](../../examples/steward-validator/) |
| Build a CustomScaffold (file generator) | [walkthrough/your-first-real-plugin.md](your-first-real-plugin.md) |
| Understand the end-to-end flow | [walkthrough/plug-into-fluid-cli.md](plug-into-fluid-cli.md) |
