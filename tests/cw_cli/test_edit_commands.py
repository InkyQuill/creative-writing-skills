import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import app, transactions


class EditCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        outer = Path(self.directory.name)
        self.root = outer / "project"
        self.caller = outer / "caller"
        self.caller.mkdir()
        self.target = self.root / "story" / "chapters" / "ch-001.md"
        self.target.parent.mkdir(parents=True)
        (self.root / "project.md").write_text(
            "---\nschema-version: 1\ntitle: Test\nlanguage: en\nstatus: drafting\n---\n",
            encoding="utf-8",
        )
        self.target.write_text(
            "---\nnumber: 1\n---\nRain.\n", encoding="utf-8"
        )

    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        status = app.run(argv, cwd=self.root, stdout=stdout, stderr=stderr)
        return status, stdout.getvalue(), stderr.getvalue()

    def content_file(self, name: str, content: str) -> str:
        path = self.caller / name
        path.write_text(content, encoding="utf-8")
        return str(path)

    def replace_argv(self, *, output_format: str = "json") -> list[str]:
        return [
            "edit",
            "replace",
            str(self.target),
            "--old-file",
            self.content_file("old.txt", "Rain."),
            "--new-file",
            self.content_file("new.txt", "Snow."),
            "--format",
            output_format,
        ]

    def test_edit_preview_is_read_only_and_apply_is_journaled(self):
        before = self.target.read_bytes()
        argv = self.replace_argv()

        status, output, error = self.run_cli(argv)

        self.assertEqual(0, status)
        self.assertEqual("", error)
        preview = json.loads(output)
        self.assertEqual("preview", preview["status"])
        self.assertIsNone(preview["transaction_id"])
        self.assertEqual("story/chapters/ch-001.md", preview["changes"][0]["path"])
        self.assertEqual(before, self.target.read_bytes())
        self.assertFalse((self.root / ".creative-writing/transactions").exists())

        status, output, error = self.run_cli(argv + ["--apply"])

        self.assertEqual(0, status)
        self.assertEqual("", error)
        applied = json.loads(output)
        self.assertEqual("committed", applied["status"])
        self.assertTrue(applied["transaction_id"])
        self.assertIn(b"Snow.", self.target.read_bytes())
        manifests = list(
            (self.root / ".creative-writing/transactions").glob("*/manifest.json")
        )
        self.assertEqual(1, len(manifests))

    def test_simple_insert_delete_and_batch_apply_use_shared_transaction_output(self):
        anchor = self.content_file("anchor.txt", "Rain.")
        addition = self.content_file("addition.txt", "Cold ")
        status, output, _ = self.run_cli(
            [
                "edit", "insert-before", "story/chapters/ch-001.md",
                "--anchor-file", anchor, "--new-file", addition,
                "--format", "json", "--apply",
            ]
        )
        self.assertEqual(0, status)
        self.assertEqual("committed", json.loads(output)["status"])
        self.assertIn(b"Cold Rain.", self.target.read_bytes())

        operations = self.caller / "operations.json"
        operations.write_text(
            json.dumps(
                [{
                    "op": "replace",
                    "path": "story/chapters/ch-001.md",
                    "old": "Cold Rain.",
                    "new": "Warm rain.",
                }]
            ),
            encoding="utf-8",
        )
        status, output, _ = self.run_cli(
            ["edit", "apply", str(operations), "--format", "json", "--apply"]
        )
        self.assertEqual(0, status)
        self.assertEqual(["edit", "apply"], json.loads(output)["command"])
        self.assertIn(b"Warm rain.", self.target.read_bytes())

    def test_conflict_is_status_one_and_runtime_plan_error_is_status_two(self):
        missing = self.content_file("missing-anchor.txt", "Sun.")
        replacement = self.content_file("replacement.txt", "Snow.")
        status, output, error = self.run_cli(
            [
                "edit", "replace", str(self.target), "--old-file", missing,
                "--new-file", replacement, "--format", "json",
            ]
        )
        self.assertEqual(1, status)
        self.assertEqual("", error)
        self.assertEqual("conflict", json.loads(output)["status"])
        self.assertIn("found 0", json.loads(output)["message"])

        status, output, error = self.run_cli(
            ["edit", "apply", str(self.caller / "absent.json"), "--format", "json"]
        )
        self.assertEqual(2, status)
        self.assertEqual("", error)
        self.assertEqual("error", json.loads(output)["status"])

    def test_text_and_json_previews_expose_identical_structured_facts(self):
        json_status, json_output, _ = self.run_cli(self.replace_argv())
        text_status, text_output, _ = self.run_cli(self.replace_argv(output_format="text"))

        self.assertEqual(json_status, text_status)
        self.assertEqual(json.loads(json_output), json.loads(text_output))

    def test_stale_apply_is_a_conflict_and_preserves_manual_bytes(self):
        original_apply = transactions.TransactionEngine.apply

        def edit_then_apply(engine, plan, *, transaction_id=None):
            self.target.write_text("manual\n", encoding="utf-8")
            return original_apply(engine, plan, transaction_id=transaction_id)

        with mock.patch.object(
            transactions.TransactionEngine, "apply", edit_then_apply
        ):
            status, output, _ = self.run_cli(self.replace_argv() + ["--apply"])

        self.assertEqual(1, status)
        self.assertEqual("conflict", json.loads(output)["status"])
        self.assertEqual(b"manual\n", self.target.read_bytes())


if __name__ == "__main__":
    unittest.main()
