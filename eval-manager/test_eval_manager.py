from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent
MANAGER = ROOT / "eval_manager.py"


class EvalManagerTest(unittest.TestCase):
    def run_manager(self, contract: dict, *, phase: str, source_sha: str = "a" * 40):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / ".evidencebound").mkdir()
            (repo / ".evidencebound" / "eval.json").write_text(
                json.dumps(contract), encoding="utf-8"
            )
            env = os.environ.copy()
            env["GITHUB_REPOSITORY"] = contract["repository"]
            env["GITHUB_SHA"] = source_sha
            completed = subprocess.run(
                [
                    sys.executable,
                    str(MANAGER),
                    "--repo-root",
                    str(repo),
                    "--contract",
                    ".evidencebound/eval.json",
                    "--phase",
                    phase,
                ],
                text=True,
                capture_output=True,
                env=env,
            )
            receipt = json.loads(
                (repo / ".evidencebound" / "eval-receipt.json").read_text(
                    encoding="utf-8"
                )
            )
            return completed, receipt

    @staticmethod
    def base_contract(*, enforcement: str, command: str) -> dict:
        return {
            "schema_version": 1,
            "repository": "example/repository",
            "policy": {"development": enforcement, "frozen": "required"},
            "bootstrap": [],
            "suites": [
                {
                    "id": "suite",
                    "phase": "development",
                    "command": command,
                    "hard_gate": True,
                }
            ],
            "freeze": {"enabled": False},
        }

    def test_required_pass(self):
        completed, receipt = self.run_manager(
            self.base_contract(
                enforcement="required",
                command=f'{sys.executable} -c "print(123)"',
            ),
            phase="development",
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(receipt["verdict"], "PASS")

    def test_required_failure_blocks(self):
        completed, receipt = self.run_manager(
            self.base_contract(
                enforcement="required",
                command=f'{sys.executable} -c "raise SystemExit(9)"',
            ),
            phase="development",
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(receipt["verdict"], "FAIL")

    def test_audit_failure_records_without_blocking(self):
        completed, receipt = self.run_manager(
            self.base_contract(
                enforcement="audit",
                command=f'{sys.executable} -c "raise SystemExit(7)"',
            ),
            phase="development",
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(receipt["verdict"], "FAIL")
        self.assertEqual(receipt["enforcement"], "audit")

    def test_frozen_binds_file_and_source_identity(self):
        source_sha = "b" * 40
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / ".evidencebound").mkdir()
            protocol = repo / "protocol.json"
            protocol.write_text('{"frozen":true}\n', encoding="utf-8")
            digest = hashlib.sha256(protocol.read_bytes()).hexdigest()
            contract = {
                "schema_version": 1,
                "repository": "example/repository",
                "policy": {"development": "audit", "frozen": "required"},
                "bootstrap": [],
                "suites": [
                    {
                        "id": "frozen-suite",
                        "phase": "frozen",
                        "command": f'{sys.executable} -c "print(456)"',
                        "hard_gate": True,
                    }
                ],
                "freeze": {
                    "enabled": True,
                    "freeze_id": "TEST-FREEZE-1",
                    "source_sha": source_sha,
                    "identities": [
                        {"name": "protocol", "path": "protocol.json", "sha256": digest}
                    ],
                },
            }
            (repo / ".evidencebound" / "eval.json").write_text(
                json.dumps(contract), encoding="utf-8"
            )
            env = os.environ.copy()
            env["GITHUB_REPOSITORY"] = "example/repository"
            env["GITHUB_SHA"] = source_sha
            completed = subprocess.run(
                [
                    sys.executable,
                    str(MANAGER),
                    "--repo-root",
                    str(repo),
                    "--contract",
                    ".evidencebound/eval.json",
                    "--phase",
                    "frozen",
                ],
                text=True,
                capture_output=True,
                env=env,
            )
            receipt = json.loads(
                (repo / ".evidencebound" / "eval-receipt.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(receipt["verdict"], "PASS")
            self.assertTrue(all(i["match"] for i in receipt["freeze"]["identities"]))

            env["GITHUB_SHA"] = "c" * 40
            mismatch = subprocess.run(
                [
                    sys.executable,
                    str(MANAGER),
                    "--repo-root",
                    str(repo),
                    "--contract",
                    ".evidencebound/eval.json",
                    "--phase",
                    "frozen",
                ],
                text=True,
                capture_output=True,
                env=env,
            )
            mismatch_receipt = json.loads(
                (repo / ".evidencebound" / "eval-receipt.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertNotEqual(mismatch.returncode, 0)
            self.assertEqual(mismatch_receipt["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()
