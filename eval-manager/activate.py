#!/usr/bin/env python3
"""Generate the two repo-local files required by EvidenceBound Eval Manager."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_suite(value: str) -> dict[str, object]:
    try:
        suite_id, command = value.split("::", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("suite must be ID::COMMAND") from exc
    if not suite_id.strip() or not command.strip():
        raise argparse.ArgumentTypeError("suite must contain non-empty ID and COMMAND")
    return {
        "id": suite_id.strip(),
        "phase": "development",
        "command": command.strip(),
        "hard_gate": True,
        "timeout_seconds": 1200,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--repository", required=True, help="owner/name")
    parser.add_argument("--mode", choices=("audit", "required"), default="audit")
    parser.add_argument("--python-version", default="3.12")
    parser.add_argument("--runner-json", default='["ubuntu-latest"]')
    parser.add_argument("--bootstrap", action="append", default=[])
    parser.add_argument("--suite", action="append", type=parse_suite, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if "/" not in args.repository:
        parser.error("--repository must be owner/name")
    try:
        runner = json.loads(args.runner_json)
    except json.JSONDecodeError as exc:
        parser.error(f"--runner-json must be valid JSON: {exc}")
    if not isinstance(runner, list) or not runner or not all(
        isinstance(item, str) and item for item in runner
    ):
        parser.error("--runner-json must be a non-empty JSON array of labels")

    root = Path(args.repo_root).resolve()
    contract_path = root / ".evidencebound" / "eval.json"
    workflow_path = root / ".github" / "workflows" / "eval-manager.yml"

    for path in (contract_path, workflow_path):
        if path.exists() and not args.force:
            parser.error(f"refusing to overwrite existing file: {path}")

    bootstrap = [
        {
            "id": f"bootstrap-{index}",
            "command": command,
            "timeout_seconds": 900,
        }
        for index, command in enumerate(args.bootstrap, start=1)
    ]

    contract = {
        "schema_version": 1,
        "repository": args.repository,
        "policy": {"development": args.mode, "frozen": "audit"},
        "bootstrap": bootstrap,
        "suites": args.suite,
        "freeze": {"enabled": False},
    }

    workflow = f"""name: Shared Eval Manager

on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  development:
    uses: evidencebound/.github/.github/workflows/eval-development.yml@main
    with:
      contract: .evidencebound/eval.json
      python_version: \"{args.python_version}\"
      runner_json: '{json.dumps(runner, separators=(",", ":"))}'
"""

    contract_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    workflow_path.write_text(workflow, encoding="utf-8")

    print(contract_path)
    print(workflow_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
