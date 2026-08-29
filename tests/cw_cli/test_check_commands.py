import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import app, scaffold
from cwcli import checks
from cwcli.findings import Finding


def make_project(root: Path) -> None:
    for relative, data in scaffold.render_scaffold("Checks", "en").items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (root / ".creative-writing/context").mkdir(parents=True, exist_ok=True)
    (root / ".creative-writing/transactions").mkdir(parents=True, exist_ok=True)


class CheckCommandTests(unittest.TestCase):
    def run_cli(self, root: Path, argv: list[str]) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        status = app.run(argv, cwd=root, stdout=stdout, stderr=stderr)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_all_has_sorted_complete_envelope_and_malformed_peer_does_not_abort(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            make_project(root)
            (root / "kb/world/broken.md").write_text("---\nsources: [bad]\n---\n", encoding="utf-8")
            (root / "README.md").write_text("outside", encoding="utf-8")

            status, output, error = self.run_cli(root, ["check", "all", "--format", "json"])
            payload = json.loads(output)

            self.assertEqual("", error)
            self.assertIn(status, {0, 1})
            self.assertEqual(sorted(checks.CHECKERS), payload["checks"])
            self.assertEqual({"checks", "findings", "execution_errors", "strict_failure"}, set(payload))
            self.assertGreater(len(payload["findings"]), 1)

    def test_checker_exception_is_contained_and_exit_status_is_two(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            make_project(root)
            (root / "README.md").write_text("outside", encoding="utf-8")
            original = checks.CHECKERS["kb"]
            checks.CHECKERS["kb"] = mock.Mock(side_effect=RuntimeError("injected"))
            try:
                status, output, _ = self.run_cli(root, ["check", "all", "--format", "json"])
            finally:
                checks.CHECKERS["kb"] = original

            payload = json.loads(output)
            self.assertEqual(2, status)
            self.assertEqual([{"check": "kb", "message": "injected"}], payload["execution_errors"])
            self.assertTrue(payload["findings"])

    def test_exit_matrix_preserves_warning_and_info_severities(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            make_project(root)
            original = checks.CHECKERS["kb"]
            checks.CHECKERS["kb"] = lambda _project: [
                Finding("INFO", "info", "info"), Finding("WARN", "warning", "warning")
            ]
            try:
                normal, normal_output, _ = self.run_cli(root, ["check", "kb", "--format", "json"])
                strict, strict_output, _ = self.run_cli(root, ["check", "kb", "--strict", "--format", "json"])
            finally:
                checks.CHECKERS["kb"] = original

            self.assertEqual(0, normal)
            self.assertEqual(1, strict)
            self.assertFalse(json.loads(normal_output)["strict_failure"])
            self.assertTrue(json.loads(strict_output)["strict_failure"])
