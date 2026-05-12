# gitlab-ci-scaffold

Realistic FLUID `CustomScaffold` example. Given any fluid contract, emits:

- `README.md` — derived from contract identity + envs
- `.gitlab-ci.yml` — validate + one deploy job per declared environment (prod is `when: manual`)
- `config/<env>.json` — per-env config carrying cloud account/region

**~150 lines of plugin code, 22 passing tests** (15 inherited + 5 domain).

## Try it

```bash
cd examples/gitlab-ci-scaffold/
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# All 22 tests
pytest -v

# See it actually generate a project
python demo.py
```

## Sample output

Given the 3-environment contract in `demo.py`:

```
✓ 5 files written, 0 failed

=== .gitlab-ci.yml ===
stages:
  - validate
  - deploy

validate:
  stage: validate
  script:
    - fluid validate

deploy:dev:
  stage: deploy
  script:
    - fluid apply --env dev
  only:
    - main

deploy:staging:
  stage: deploy
  script:
    - fluid apply --env staging
  only:
    - main

deploy:prod:
  stage: deploy
  script:
    - fluid apply --env prod
  when: manual            ← prod is gated
  only:
    - main
```

## End-user flow (when published)

```bash
# 1. User installs the FLUID CLI + the engine + this plugin
pip install data-product-forge data-product-forge-custom-scaffold gitlab-ci-scaffold

# 2. User declares the binding in their contract
cat >> contract.fluid.yaml <<'EOF'
extensions:
  customScaffold:
    libraries:
      - id: ci
        source: { kind: pypi, package: gitlab-ci-scaffold, version: ">=0.1" }
    patterns:
      - use: ci:gitlab-ci
EOF

# 3. Generate
fluid generate custom-scaffold

# README.md, .gitlab-ci.yml, config/{dev,staging,prod}.json all appear
```

Change the contract's `environments` block → re-run → output adapts.
