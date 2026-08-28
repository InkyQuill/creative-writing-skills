import os
import tempfile
import unittest
from pathlib import Path

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import project, transactions


def make_project(root: Path) -> project.Project:
    root.mkdir(parents=True, exist_ok=True)
    (root / "project.md").write_text("---\ntitle: Test project\n---\n", encoding="utf-8")
    return project.discover_project(root)


class TransactionEngineTests(unittest.TestCase):
    def make_engine(
        self, files: dict[str, bytes]
    ) -> tuple[Path, transactions.TransactionEngine]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name) / "project"
        story_project = make_project(root)
        for relative, content in files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        return root, transactions.TransactionEngine(story_project)

    def test_preview_validates_and_describes_plan_without_writing(self):
        root, engine = self.make_engine({"story/a.md": b"A\n"})
        plan = transactions.TransactionPlan(
            ("edit", "replace"),
            (transactions.Change("story/a.md", b"A\n", b"A2\n"),),
            {"reason": "revision"},
        )

        preview = engine.preview(plan)

        self.assertEqual(
            {
                "changes": [
                    {
                        "action": "update",
                        "diff": "--- story/a.md\n+++ story/a.md\n@@ -1 +1 @@\n-A\n+A2\n",
                        "path": "story/a.md",
                    }
                ],
                "command": ["edit", "replace"],
                "metadata": {"reason": "revision"},
            },
            preview,
        )
        self.assertEqual(b"A\n", (root / "story/a.md").read_bytes())
        self.assertFalse(engine.store.root.exists())

    def test_apply_replaces_every_target_and_commits_completed_paths(self):
        root, engine = self.make_engine({"story/a.md": b"A\n", "story/b.md": b"B\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (
                transactions.Change("story/a.md", b"A\n", b"A2\n"),
                transactions.Change("story/b.md", b"B\n", b"B2\n"),
            ),
            {},
        )

        record = engine.apply(plan, transaction_id="tx-success")

        self.assertEqual(
            transactions.TransactionRecord(
                "tx-success", "committed", ("story/a.md", "story/b.md")
            ),
            record,
        )
        self.assertEqual(b"A2\n", (root / "story/a.md").read_bytes())
        self.assertEqual(b"B2\n", (root / "story/b.md").read_bytes())
        self.assertFalse(list((root / "story").glob(".cw-transaction-*.tmp")))

    def test_stale_precondition_preserves_manual_edit_without_journaling(self):
        root, engine = self.make_engine({"story/a.md": b"manual\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (transactions.Change("story/a.md", b"expected\n", b"replacement\n"),),
            {},
        )

        with self.assertRaisesRegex(transactions.TransactionError, "stale precondition"):
            engine.apply(plan, transaction_id="tx-stale")

        self.assertEqual(b"manual\n", (root / "story/a.md").read_bytes())
        self.assertFalse((engine.store.root / "tx-stale").exists())

    def test_stale_precondition_after_prepare_rolls_back_without_replacing_any_target(self):
        root, engine = self.make_engine({"story/a.md": b"A\n", "story/b.md": b"B\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (
                transactions.Change("story/a.md", b"A\n", b"A2\n"),
                transactions.Change("story/b.md", b"B\n", b"B2\n"),
            ),
            {},
        )
        prepare = engine.store.prepare

        def prepare_then_edit(
            prepared_plan: transactions.TransactionPlan, *, transaction_id: str | None = None
        ) -> transactions.TransactionRecord:
            record = prepare(prepared_plan, transaction_id=transaction_id)
            (root / "story/b.md").write_bytes(b"manual\n")
            return record

        engine.store.prepare = prepare_then_edit

        with self.assertRaisesRegex(transactions.TransactionError, "stale precondition"):
            engine.apply(plan, transaction_id="tx-stale-after-prepare")

        self.assertEqual(b"A\n", (root / "story/a.md").read_bytes())
        self.assertEqual(b"manual\n", (root / "story/b.md").read_bytes())
        self.assertEqual(
            "rolled-back", engine.store.load("tx-stale-after-prepare").state
        )
        self.assertFalse(list((root / "story").glob(".cw-transaction-*.tmp")))

    def test_failure_after_first_replace_restores_every_target(self):
        root, engine = self.make_engine({"story/a.md": b"A\n", "story/b.md": b"B\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (
                transactions.Change("story/a.md", b"A\n", b"A2\n"),
                transactions.Change("story/b.md", b"B\n", b"B2\n"),
            ),
            {},
        )
        calls = 0

        def fail_on_second_replace(source: os.PathLike[str], destination: os.PathLike[str]) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected")
            os.replace(source, destination)

        engine.replace_hook = fail_on_second_replace

        with self.assertRaisesRegex(transactions.TransactionError, "rolled back"):
            engine.apply(plan, transaction_id="tx-fail")

        self.assertEqual(b"A\n", (root / "story/a.md").read_bytes())
        self.assertEqual(b"B\n", (root / "story/b.md").read_bytes())
        self.assertEqual("rolled-back", engine.store.load("tx-fail").state)
        self.assertFalse(list((root / "story").glob(".cw-transaction-*.tmp")))

    def test_transaction_error_reports_forward_and_rollback_failures(self):
        root, engine = self.make_engine({"story/a.md": b"A\n", "story/b.md": b"B\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (
                transactions.Change("story/a.md", b"A\n", b"A2\n"),
                transactions.Change("story/b.md", b"B\n", b"B2\n"),
            ),
            {},
        )
        calls = 0

        def fail_forward_and_rollback(
            source: os.PathLike[str], destination: os.PathLike[str]
        ) -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                os.replace(source, destination)
            elif calls == 2:
                raise OSError("forward injected")
            else:
                raise OSError("rollback injected")

        engine.replace_hook = fail_forward_and_rollback

        with self.assertRaises(transactions.TransactionError) as raised:
            engine.apply(plan, transaction_id="tx-rollback-fail")

        message = str(raised.exception)
        self.assertIn("forward injected", message)
        self.assertIn("rollback failed", message)
        self.assertIn("rollback injected", message)
        self.assertEqual(b"A2\n", (root / "story/a.md").read_bytes())
        self.assertEqual("rolled-back", engine.store.load("tx-rollback-fail").state)
        self.assertFalse(list((root / "story").glob(".cw-transaction-*.tmp")))

    def test_apply_supports_create_and_delete(self):
        root, engine = self.make_engine({"story/old.md": b"old\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (
                transactions.Change("story/new.md", None, b"new\n"),
                transactions.Change("story/old.md", b"old\n", None),
            ),
            {},
        )

        record = engine.apply(plan, transaction_id="tx-create-delete")

        self.assertEqual("committed", record.state)
        self.assertEqual(("story/new.md", "story/old.md"), record.completed)
        self.assertEqual(b"new\n", (root / "story/new.md").read_bytes())
        self.assertFalse((root / "story/old.md").exists())

    def test_failure_after_create_and_delete_restores_both_in_reverse(self):
        root, engine = self.make_engine(
            {"story/old.md": b"old\n", "story/final.md": b"before\n"}
        )
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (
                transactions.Change("story/new.md", None, b"new\n"),
                transactions.Change("story/old.md", b"old\n", None),
                transactions.Change("story/final.md", b"before\n", b"after\n"),
            ),
            {},
        )
        calls = 0

        def fail_on_second_replace(source: os.PathLike[str], destination: os.PathLike[str]) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected after create and delete")
            os.replace(source, destination)

        engine.replace_hook = fail_on_second_replace

        with self.assertRaisesRegex(transactions.TransactionError, "rolled back"):
            engine.apply(plan, transaction_id="tx-create-delete-fail")

        self.assertFalse((root / "story/new.md").exists())
        self.assertEqual(b"old\n", (root / "story/old.md").read_bytes())
        self.assertEqual(b"before\n", (root / "story/final.md").read_bytes())
        self.assertEqual(
            ("story/new.md", "story/old.md"),
            engine.store.load("tx-create-delete-fail").completed,
        )

    def test_recover_restores_recorded_create_delete_and_update_without_rolling_forward(self):
        root, engine = self.make_engine(
            {"story/deleted.md": b"deleted\n", "story/updated.md": b"before\n", "story/pending.md": b"pending\n"}
        )
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (
                transactions.Change("story/created.md", None, b"created\n"),
                transactions.Change("story/deleted.md", b"deleted\n", None),
                transactions.Change("story/updated.md", b"before\n", b"after\n"),
                transactions.Change("story/pending.md", b"pending\n", b"not-installed\n"),
            ),
            {},
        )
        engine.store.prepare(plan, transaction_id="tx-recover")
        (root / "story/created.md").write_bytes(b"created\n")
        (root / "story/deleted.md").unlink()
        (root / "story/updated.md").write_bytes(b"after\n")
        engine.store.write_state(
            "tx-recover",
            "applying",
            completed=("story/created.md", "story/deleted.md", "story/updated.md"),
        )
        pending_temporary = engine._temporary_path("tx-recover", "story/pending.md")
        pending_temporary.write_bytes(b"not-installed\n")

        record = engine.recover("tx-recover")

        self.assertEqual("rolled-back", record.state)
        self.assertEqual(
            ("story/created.md", "story/deleted.md", "story/updated.md"), record.completed
        )
        self.assertFalse((root / "story/created.md").exists())
        self.assertEqual(b"deleted\n", (root / "story/deleted.md").read_bytes())
        self.assertEqual(b"before\n", (root / "story/updated.md").read_bytes())
        self.assertEqual(b"pending\n", (root / "story/pending.md").read_bytes())
        self.assertFalse(pending_temporary.exists())

    def test_recover_prepared_transaction_removes_staged_siblings(self):
        root, engine = self.make_engine({"story/a.md": b"A\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (transactions.Change("story/a.md", b"A\n", b"A2\n"),),
            {},
        )
        engine.store.prepare(plan, transaction_id="tx-prepared")
        temporary = engine._temporary_path("tx-prepared", "story/a.md")
        temporary.write_bytes(b"A2\n")

        record = engine.recover("tx-prepared")

        self.assertEqual(transactions.TransactionRecord("tx-prepared", "rolled-back", ()), record)
        self.assertEqual(b"A\n", (root / "story/a.md").read_bytes())
        self.assertFalse(temporary.exists())

    def test_recover_rejects_terminal_transaction(self):
        _root, engine = self.make_engine({"story/a.md": b"A\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (transactions.Change("story/a.md", b"A\n", b"A2\n"),),
            {},
        )
        engine.apply(plan, transaction_id="tx-committed")

        with self.assertRaisesRegex(transactions.TransactionError, "cannot recover"):
            engine.recover("tx-committed")

        self.assertEqual("committed", engine.store.load("tx-committed").state)

    def test_apply_refuses_symlink_target_without_touching_external_file(self):
        root, engine = self.make_engine({})
        outside = root.parent / "outside.md"
        outside.write_bytes(b"outside\n")
        (root / "story").mkdir()
        (root / "story/link.md").symlink_to(outside)
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (transactions.Change("story/link.md", b"outside\n", b"changed\n"),),
            {},
        )

        with self.assertRaises(transactions.TransactionError):
            engine.apply(plan, transaction_id="tx-symlink")

        self.assertEqual(b"outside\n", outside.read_bytes())
        self.assertFalse((engine.store.root / "tx-symlink").exists())


if __name__ == "__main__":
    unittest.main()
