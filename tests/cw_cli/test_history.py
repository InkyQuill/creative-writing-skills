import io
import json
import tempfile
import unittest
from pathlib import Path

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import app, project, transactions


class HistoryCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "project"
        self.target = self.root / "story" / "chapters" / "ch-001.md"
        self.target.parent.mkdir(parents=True)
        (self.root / "project.md").write_text(
            "---\nschema-version: 1\ntitle: Test\nlanguage: en\nstatus: drafting\n---\n",
            encoding="utf-8",
        )
        self.before = b"---\nnumber: 1\n---\nRain.\n"
        self.after = b"---\nnumber: 1\n---\nSnow.\n"
        self.target.write_bytes(self.before)
        self.story_project = project.discover_project(self.root)
        self.engine = transactions.TransactionEngine(self.story_project)

    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        status = app.run(argv, cwd=self.root, stdout=stdout, stderr=stderr)
        return status, stdout.getvalue(), stderr.getvalue()

    def apply_edit(self, transaction_id: str = "tx-edit") -> None:
        self.engine.apply(
            transactions.TransactionPlan(
                ("edit", "replace"),
                (transactions.Change("story/chapters/ch-001.md", self.before, self.after),),
                {"undoable": True},
            ),
            transaction_id=transaction_id,
        )

    def test_history_lists_newest_first_and_show_includes_stored_diff(self):
        self.apply_edit("tx-older")
        inverse = self.engine.inverse("tx-older")
        self.engine.apply(inverse, transaction_id="tx-newer")

        status, output, error = self.run_cli(["history", "--format", "json"])

        self.assertEqual(0, status)
        self.assertEqual("", error)
        history = json.loads(output)["transactions"]
        self.assertEqual(["tx-newer", "tx-older"], [entry["id"] for entry in history])
        self.assertEqual(1, history[0]["change_count"])
        self.assertNotIn("changes", history[0])

        status, output, error = self.run_cli(
            ["history", "show", "tx-older", "--format", "json"]
        )
        self.assertEqual(0, status)
        self.assertEqual("", error)
        shown = json.loads(output)["transaction"]
        self.assertEqual("committed", shown["state"])
        self.assertIn("-Rain.", shown["changes"][0]["diff"])
        self.assertIn("+Snow.", shown["changes"][0]["diff"])

    def test_undo_preview_and_apply_round_trip_create_a_new_transaction(self):
        self.apply_edit()

        status, output, _ = self.run_cli(["undo", "tx-edit", "--format", "json"])
        self.assertEqual(0, status)
        self.assertEqual("preview", json.loads(output)["status"])
        self.assertEqual(self.after, self.target.read_bytes())

        status, output, _ = self.run_cli(
            ["undo", "tx-edit", "--format", "json", "--apply"]
        )
        self.assertEqual(0, status)
        result = json.loads(output)
        self.assertEqual("committed", result["status"])
        self.assertNotEqual("tx-edit", result["transaction_id"])
        self.assertEqual(self.before, self.target.read_bytes())
        inverse_manifest = self.engine.store.manifest(result["transaction_id"])
        self.assertEqual("tx-edit", inverse_manifest["metadata"]["undo-of"])

    def test_manual_edit_makes_undo_a_conflict_without_overwriting_it(self):
        self.apply_edit()
        self.target.write_bytes(b"manual\n")

        status, output, error = self.run_cli(
            ["undo", "tx-edit", "--format", "json", "--apply"]
        )

        self.assertEqual(1, status)
        self.assertEqual("", error)
        self.assertEqual("conflict", json.loads(output)["status"])
        self.assertEqual(b"manual\n", self.target.read_bytes())
        self.assertEqual(1, len(self.engine.store.history()))

    def test_nonundoable_and_noncommitted_transactions_are_refused(self):
        plan = transactions.TransactionPlan(
            ("init",),
            (transactions.Change("story/chapters/ch-001.md", self.before, self.after),),
            {"undoable": False},
        )
        self.engine.apply(plan, transaction_id="tx-bootstrap")
        status, output, _ = self.run_cli(
            ["undo", "tx-bootstrap", "--format", "json"]
        )
        self.assertEqual(1, status)
        self.assertIn("not undoable", json.loads(output)["message"])

        self.target.write_bytes(self.before)
        self.engine.store.prepare(plan, transaction_id="tx-prepared")
        status, output, _ = self.run_cli(
            ["undo", "tx-prepared", "--format", "json"]
        )
        self.assertEqual(1, status)
        self.assertIn("state prepared", json.loads(output)["message"])


if __name__ == "__main__":
    unittest.main()
