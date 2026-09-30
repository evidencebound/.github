#!/usr/bin/env python3
"""EvidenceBound Eval Manager.

Repository-local contracts declare bootstrap commands and eval suites.
This runner executes them, enforces hard gates, verifies frozen identities,
and writes a machine-readable receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

MANAGER_VERSION = "1.0.0"


class ContractError(ValueError):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _sha256_tree(path: Path) -> str:
    if path.is_file():
        return _sha256_file(path)
    if not path.is_dir():
        raise ContractError(f"freeze path does not exist: {path}")
    digest = hashlib.sha256()
    files = sorted(p for p in path.rglob("*") if p.is_file())
    for file_path in files:
        rel = file_path.relative_to(path).as_posix().encode("utf-8")
        digest.update(rel)
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _load_contract(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON contract: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError("contract root must be an object")
    if data.get("schema_version") != 1:
        raise ContractError("schema_version must equal 1")
    repository = data.get("repository")
    if not isinstance(repository, str) or "/" not in repository:
        raise ContractError("repository must be owner/name")
    policy = data.get("policy")
    if not isinstance(policy, dict):
        raise ContractError("policy object is required")
    suites = data.get("suites")
    if not isinstance(suites, list):
        raise ContractError("suites must be a list")
    seen: set[str] = set()
    for suite in suites:
        if not isinstance(suite, dict):
            raise ContractError("each suite must be an object")
        suite_id = suite.get("id")
        if not isinstance(suite_id, str) or not suite_id:
            raise ContractError("suite id is required")
        if suite_id in seen:
            raise ContractError(f"duplicate suite id: {suite_id}")
        seen.add(suite_id)
        if suite.get("phase") not in {"development", "frozen"}:
            raise ContractError(f"{suite_id}: phase must be development or frozen")
        if not isinstance(suite.get("command"), str) or not suite["command"].strip():
            raise ContractError(f"{suite_id}: command is required")
    return data, _sha256_bytes(raw)


def _run_command(command: str, cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            env=os.environ.copy(),
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if stdout:
            print(stdout, end="" if stdout.endswith("\n") else "\n")
        if stderr:
            print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
        return {
            "exit_code": completed.returncode,
            "timed_out": False,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "stdout_sha256": _sha256_bytes(stdout.encode("utf-8")),
            "stderr_sha256": _sha256_bytes(stderr.encode("utf-8")),
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {
            "exit_code": None,
            "timed_out": True,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "stdout_sha256": _sha256_bytes(stdout.encode("utf-8")),
            "stderr_sha256": _sha256_bytes(stderr.encode("utf-8")),
        }


def _verify_freeze(contract: dict[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    freeze = contract.get("freeze")
    if not isinstance(freeze, dict) or not freeze.get("enabled"):
        raise ContractError("frozen phase requires freeze.enabled=true")
    freeze_id = freeze.get("freeze_id")
    if not isinstance(freeze_id, str) or not freeze_id:
        raise ContractError("frozen phase requires freeze_id")
    identities = freeze.get("identities")
    if not isinstance(identities, list) or not identities:
        raise ContractError("frozen phase requires at least one identity")
    results = []
    for item in identities:
        if not isinstance(item, dict):
            raise ContractError("freeze identity must be an object")
        name = item.get("name")
        rel = item.get("path")
        expected = item.get("sha256")
        if not all(isinstance(v, str) and v for v in (name, rel, expected)):
            raise ContractError("freeze identity requires name, path, sha256")
        actual = _sha256_tree(repo_root / rel)
        results.append(
            {
                "name": name,
                "path": rel,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "match": actual == expected,
            }
        )
    return results


def _source_identity(repo_root: Path) -> str | None:
    env_sha = os.environ.get("GITHUB_SHA")
    if env_sha:
        return env_sha
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
        ).strip()
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--contract", default=".evidencebound/eval.json")
    parser.add_argument("--phase", choices=("development", "frozen"), required=True)
    parser.add_argument("--receipt", default=".evidencebound/eval-receipt.json")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    contract_path = Path(args.contract)
    if not contract_path.is_absolute():
        contract_path = repo_root / contract_path
    receipt_path = Path(args.receipt)
    if not receipt_path.is_absolute():
        receipt_path = repo_root / receipt_path

    receipt: dict[str, Any] = {
        "manager": "EvidenceBound Eval Manager",
        "manager_version": MANAGER_VERSION,
        "phase": args.phase,
        "repository": os.environ.get("GITHUB_REPOSITORY"),
        "source_sha": _source_identity(repo_root),
        "contract": str(contract_path.relative_to(repo_root)) if contract_path.is_relative_to(repo_root) else str(contract_path),
        "contract_sha256": None,
        "enforcement": None,
        "freeze": None,
        "bootstrap": [],
        "suites": [],
        "verdict": "INVALID",
    }

    try:
        contract, contract_sha = _load_contract(contract_path)
        receipt["contract_sha256"] = contract_sha
        receipt["declared_repository"] = contract["repository"]

        actual_repository = os.environ.get("GITHUB_REPOSITORY")
        if actual_repository and actual_repository != contract["repository"]:
            raise ContractError(
                f"repository mismatch: contract={contract['repository']} runtime={actual_repository}"
            )

        enforcement = contract["policy"].get(args.phase, "audit")
        if enforcement not in {"audit", "required"}:
            raise ContractError(f"policy.{args.phase} must be audit or required")
        receipt["enforcement"] = enforcement

        freeze_ok = True
        if args.phase == "frozen":
            freeze_results = _verify_freeze(contract, repo_root)
            receipt["freeze"] = {
                "freeze_id": contract["freeze"]["freeze_id"],
                "identities": freeze_results,
            }
            freeze_ok = all(item["match"] for item in freeze_results)

        bootstrap = contract.get("bootstrap", [])
        if not isinstance(bootstrap, list):
            raise ContractError("bootstrap must be a list")
        bootstrap_ok = True
        for index, item in enumerate(bootstrap, start=1):
            if isinstance(item, str):
                command = item
                item_id = f"bootstrap-{index}"
                timeout = 900
            elif isinstance(item, dict):
                command = item.get("command")
                item_id = item.get("id", f"bootstrap-{index}")
                timeout = int(item.get("timeout_seconds", 900))
            else:
                raise ContractError("bootstrap entries must be strings or objects")
            if not isinstance(command, str) or not command.strip():
                raise ContractError(f"{item_id}: bootstrap command is required")
            print(f"::group::bootstrap {item_id}")
            result = _run_command(command, repo_root, timeout)
            print("::endgroup::")
            result.update({"id": item_id, "command": command})
            receipt["bootstrap"].append(result)
            if result["timed_out"] or result["exit_code"] != 0:
                bootstrap_ok = False
                break

        selected = [s for s in contract["suites"] if s["phase"] == args.phase]
        if not selected:
            raise ContractError(f"no {args.phase} suites declared")

        hard_failure = not freeze_ok or not bootstrap_ok
        soft_failure = False
        if bootstrap_ok:
            for suite in selected:
                suite_id = suite["id"]
                command = suite["command"]
                timeout = int(suite.get("timeout_seconds", 1200))
                hard_gate = bool(suite.get("hard_gate", True))
                print(f"::group::eval {suite_id}")
                result = _run_command(command, repo_root, timeout)
                print("::endgroup::")
                passed = (not result["timed_out"]) and result["exit_code"] == 0
                result.update(
                    {
                        "id": suite_id,
                        "command": command,
                        "hard_gate": hard_gate,
                        "status": "PASS" if passed else "FAIL",
                    }
                )
                receipt["suites"].append(result)
                if not passed:
                    if hard_gate:
                        hard_failure = True
                    else:
                        soft_failure = True

        if hard_failure:
            receipt["verdict"] = "FAIL"
        elif soft_failure:
            receipt["verdict"] = "CAUTION"
        else:
            receipt["verdict"] = "PASS"

    except (ContractError, OSError, ValueError) as exc:
        receipt["verdict"] = "INVALID"
        receipt["error"] = str(exc)

    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))

    enforcement = receipt.get("enforcement")
    if enforcement == "audit":
        return 0
    return 0 if receipt["verdict"] in {"PASS", "CAUTION"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
