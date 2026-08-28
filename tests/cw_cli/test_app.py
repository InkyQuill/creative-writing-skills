import io
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from .helpers import app, findings


class AppTests(unittest.TestCase):
    def test_invalid_arguments_use_injected_stderr_and_return_failure(self):
        stderr = io.StringIO()
        global_stderr = io.StringIO()
        with redirect_stderr(global_stderr):
            status = app.run(["--format", "invalid"], cwd=Path.cwd(), stdout=io.StringIO(), stderr=stderr)
        self.assertEqual(status, 2)
        self.assertIn("cw: error:", stderr.getvalue())
        self.assertEqual("", global_stderr.getvalue())

    def test_version_is_machine_readable(self):
        stdout = io.StringIO()
        status = app.run(["--version", "--format", "json"], cwd=Path.cwd(), stdout=stdout, stderr=io.StringIO())
        self.assertEqual(status, 0)
        self.assertEqual({"name": "cw", "version": "0.1.0"}, __import__("json").loads(stdout.getvalue()))

    def test_strict_warning_returns_one_without_changing_severity(self):
        report = findings.Report([findings.Finding("CW-DEMO-001", "warning", "demo")])
        self.assertEqual(report.exit_status(strict=False), 0)
        self.assertEqual(report.exit_status(strict=True), 1)
        self.assertEqual(report.as_json(strict=True)["findings"][0]["severity"], "warning")
        self.assertTrue(report.as_json(strict=True)["strict_failure"])
