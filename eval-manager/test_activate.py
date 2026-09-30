from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent
ACTIVATE = ROOT / "activate.py"


class ActivateTest(unittest.TestCase):
    def test_generates_contract_and_runner_routing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ACTIVATE),
                    "--repo-root",
                    str(root),
                    "--repository",
                    "example/repo",
                    "--mode",
                    "audit",
                    "--python-version",
                    "3.12",
                    "--runner-json",
                    '["self-hosted","linux","x64","example-ci"]',
                    "--bootstrap",
                    "python -m pip install -e '.[dev]'",
                    "--suite",
                    "tests::pytest -q",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            contract = json.loads(
                (root / ".evidencebound" / "eval.json").read_text(encoding="utf-8")
            )
            workflow = (
                root / ".github" / "workflows" / "eval-manager.yml"
            ).read_text(encoding="utf-8")
            self.assertEqual(contract["repository"], "example/repo")
            self.assertEqual(contract["policy"]["development"], "audit")
            self.assertEqual(contract["suites"][0]["id"], "tests")
            self.assertIn('"example-ci"', workflow)
            self.assertIn("evidencebound/.github/.github/workflows/eval-development.yml@main", workflow)

    def test_refuses_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / ".evidencebound" / "eval.json"
            path.parent.mkdir(parents=True)
            path.write_text("{}\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ACTIVATE),
                    "--repo-root",
                    str(root),
                    "--repository",
                    "example/repo",
                    "--suite",
                    "tests::pytest -q",
                ],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(path.read_text(encoding="utf-8"), "{}\n")


if __name__ == "__main__":
    unittest.main()
