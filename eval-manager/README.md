# EvidenceBound Eval Manager

Reusable cross-repository evaluation control plane.

The manager is intentionally separate from repository business logic. Each repository owns a small `.evidencebound/eval.json` contract; the shared manager executes it, applies hard gates, verifies frozen identities, and emits a machine-readable receipt.

## Modes

- `development`: deterministic PR/main regression and adversarial evals.
- `frozen`: manually invoked research/release evaluation with precommitted file/tree SHA-256 identities.

Each phase is independently `audit` or `required`.

`audit` records failures without blocking the workflow. `required` exits non-zero on `FAIL` or `INVALID`.

## Repository contract

```json
{
  "schema_version": 1,
  "repository": "owner/repository",
  "policy": {
    "development": "required",
    "frozen": "required"
  },
  "bootstrap": [
    {
      "id": "install",
      "command": "python -m pip install -e '.[dev]'",
      "timeout_seconds": 900
    }
  ],
  "suites": [
    {
      "id": "tests",
      "phase": "development",
      "command": "pytest -q",
      "hard_gate": true
    }
  ],
  "freeze": {
    "enabled": false
  }
}
```

For a frozen benchmark, set `freeze.enabled=true`, provide a stable `freeze_id`, and list every precommitted protocol/case/verifier path with its exact SHA-256. Directory identities are canonical tree hashes over sorted relative paths and bytes.

## Thin caller

```yaml
name: eval
on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  eval:
    uses: evidencebound/.github/.github/workflows/eval-development.yml@main
    with:
      contract: .evidencebound/eval.json
```

A self-hosted repository can override `runner_json`, for example:

```yaml
with:
  runner_json: '["self-hosted","linux","x64","autofinisher-ci"]'
```

## Trust boundary

The manager does not define project acceptance criteria. The repository contract does.

The manager does not grant production authority, receive production secrets, mutate deployments, or publish claims. Frozen eval is a verifier/evidence operation only.

Activation order is:

`contract -> development eval -> optional required check -> freeze -> frozen eval -> retained receipt -> external claim`

Branch/ruleset enforcement is a separate repository-governance action and should only be enabled after the eval check is observed green on the target repository.
