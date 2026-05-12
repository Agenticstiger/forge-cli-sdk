# steward-validator

Example FLUID `Validator` plugin. Fails any contract that doesn't declare a data steward.

Three findings the validator emits, demonstrating the full severity range:

| Contract shape | Finding | Severity | CLI effect |
|---|---|---|---|
| No steward declared | `STEWARD_ID_MISSING` | `error` | Non-zero exit |
| Steward ID but no email | `STEWARD_EMAIL_MISSING` | `warn` | Reported, no exit-code change |
| Both ID + email present | (none) | — | Clean pass |

## Try it

```bash
cd examples/steward-validator/
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest -v
python demo.py
```

Demo output:

```
=== missing steward ===
  [ERROR] STEWARD_ID_MISSING: Contract 'p1' is missing the required label 'principal.steward.id'.
          ↳ Add metadata.labels['principal.steward.id'] with the employee/user identifier of the data steward.
  → applied=0 failed=1

=== no steward email ===
  [WARN] STEWARD_EMAIL_MISSING: Contract 'p2' declares a steward id but no email — operations notifications will go nowhere.
          ↳ Add metadata.labels['principal.steward.email'] with the steward's email address.
  → applied=1 failed=0

=== fully compliant ===
  ✓ no findings
```

## End-user flow (when published)

```bash
pip install data-product-forge steward-validator

# The FLUID CLI auto-discovers this plugin via the fluid_build.validators
# entry-point. Run `fluid validate` and the rule fires automatically:

fluid validate
# [WARN] STEWARD_EMAIL_MISSING: ...
# [ERROR] STEWARD_ID_MISSING: ...
# 1 error, 1 warning. Exit code 1.
```

## Fork this pattern

This is a template for any contract-inspection rule. Copy the directory, rename, replace the assertion logic in `validator.py::plan()`. Other natural fits:

- Data classification required (`metadata.classification` not empty)
- Owner email must match a domain (`metadata.owner.email` ends with `@your-org.com`)
- Sovereignty region whitelist (`sovereignty.regulatoryFramework` ⊂ allowed list)
- Cost guardrails (warn if `binding.location` requests an expensive region)

Whatever rule your org needs, package it as a `Validator` plugin, publish to PyPI, and `pip install`-ing it auto-enrols every team running `fluid validate`.
