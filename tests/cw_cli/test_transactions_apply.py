import json
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
        self.assertEqual("applying", engine.store.load("tx-rollback-fail").state)
        self.assertFalse(list((root / "story").glob(".cw-transaction-*.tmp")))

        engine.replace_hook = os.replace
        recovered = engine.recover("tx-rollback-fail")
        self.assertEqual("rolled-back", recovered.state)
        self.assertEqual(b"A\n", (root / "story/a.md").read_bytes())

    def test_durable_intent_precedes_mutation_and_recovers_mutation_then_raise(self):
        root, engine = self.make_engine({"story/a.md": b"A\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (transactions.Change("story/a.md", b"A\n", b"A2\n"),),
            {},
        )
        observed: list[tuple[str, list[str], list[str]]] = []

        def mutate_then_raise(source: os.PathLike[str], destination: os.PathLike[str]) -> None:
            manifest = json.loads(
                (engine.store.root / "tx-mutate-raise/manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            observed.append((manifest["state"], manifest["intents"], manifest["completed"]))
            os.replace(source, destination)
            raise OSError("raised after mutation")

        engine.replace_hook = mutate_then_raise

        with self.assertRaisesRegex(transactions.TransactionError, "raised after mutation"):
            engine.apply(plan, transaction_id="tx-mutate-raise")

        self.assertEqual(("applying", ["story/a.md"], []), observed[0])
        self.assertEqual(b"A\n", (root / "story/a.md").read_bytes())
        self.assertEqual("rolled-back", engine.store.load("tx-mutate-raise").state)

    def test_mutation_then_raise_rolls_back_create_and_delete(self):
        cases = (
            (
                "create",
                {"story/existing.md": b"existing\n"},
                transactions.Change("story/a.md", None, b"A2\n"),
            ),
            ("delete", {"story/a.md": b"A\n"}, transactions.Change("story/a.md", b"A\n", None)),
        )
        for label, files, change in cases:
            with self.subTest(label=label):
                root, engine = self.make_engine(files)
                plan = transactions.TransactionPlan(("edit", "apply"), (change,), {})
                if label == "create":
                    def mutate_then_raise(
                        source: os.PathLike[str], destination: os.PathLike[str]
                    ) -> None:
                        os.replace(source, destination)
                        raise OSError("create raised after mutation")

                    engine.replace_hook = mutate_then_raise
                else:
                    def unlink_then_raise(target: os.PathLike[str]) -> None:
                        os.unlink(target)
                        raise OSError("delete raised after mutation")

                    engine.unlink_hook = unlink_then_raise

                with self.assertRaisesRegex(transactions.TransactionError, "raised after mutation"):
                    engine.apply(plan, transaction_id=f"tx-{label}-mutate-raise")

                target = root / "story/a.md"
                if label == "create":
                    self.assertFalse(target.exists())
                else:
                    self.assertEqual(b"A\n", target.read_bytes())
                self.assertEqual(
                    "rolled-back",
                    engine.store.load(f"tx-{label}-mutate-raise").state,
                )

    def test_applying_state_failure_leaves_prepared_transaction_recoverable(self):
        root, engine = self.make_engine({"story/a.md": b"A\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (transactions.Change("story/a.md", b"A\n", b"A2\n"),),
            {},
        )
        write_state = engine.store.write_state

        def fail_applying(
            transaction_id: str,
            state: str,
            *,
            completed: tuple[str, ...] = (),
            intents: tuple[str, ...] | None = None,
        ) -> transactions.TransactionRecord:
            kwargs: dict[str, object] = {"completed": completed}
            if intents is not None:
                kwargs["intents"] = intents
            record = write_state(transaction_id, state, **kwargs)
            if state == "applying":
                raise OSError("applying durability injected after install")
            return record

        engine.store.write_state = fail_applying

        with self.assertRaisesRegex(transactions.TransactionError, "applying durability injected"):
            engine.apply(plan, transaction_id="tx-applying-state-fail")

        self.assertEqual(b"A\n", (root / "story/a.md").read_bytes())
        self.assertEqual("applying", engine.store.load("tx-applying-state-fail").state)

    def test_intent_state_failure_prevents_mutation_and_remains_recoverable(self):
        root, engine = self.make_engine({"story/a.md": b"A\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (transactions.Change("story/a.md", b"A\n", b"A2\n"),),
            {},
        )
        write_state = engine.store.write_state

        def fail_intent(
            transaction_id: str,
            state: str,
            *,
            completed: tuple[str, ...] = (),
            intents: tuple[str, ...] | None = None,
        ) -> transactions.TransactionRecord:
            kwargs: dict[str, object] = {"completed": completed}
            if intents is not None:
                kwargs["intents"] = intents
            record = write_state(transaction_id, state, **kwargs)
            if state == "applying" and intents:
                raise OSError("intent durability injected after install")
            return record

        engine.store.write_state = fail_intent

        with self.assertRaisesRegex(transactions.TransactionError, "intent durability injected"):
            engine.apply(plan, transaction_id="tx-intent-state-fail")

        self.assertEqual(b"A\n", (root / "story/a.md").read_bytes())
        self.assertEqual("applying", engine.store.load("tx-intent-state-fail").state)

    def test_completed_progress_failure_rolls_back_and_remains_recoverable(self):
        root, engine = self.make_engine({"story/a.md": b"A\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (transactions.Change("story/a.md", b"A\n", b"A2\n"),),
            {},
        )
        write_state = engine.store.write_state

        def fail_completed_progress(
            transaction_id: str,
            state: str,
            *,
            completed: tuple[str, ...] = (),
            intents: tuple[str, ...] | None = None,
        ) -> transactions.TransactionRecord:
            kwargs: dict[str, object] = {"completed": completed}
            if intents is not None:
                kwargs["intents"] = intents
            record = write_state(transaction_id, state, **kwargs)
            if state == "applying" and completed:
                raise OSError("completed progress durability injected after install")
            return record

        engine.store.write_state = fail_completed_progress

        with self.assertRaisesRegex(
            transactions.TransactionError, "completed progress durability injected"
        ):
            engine.apply(plan, transaction_id="tx-completed-progress-fail")

        self.assertEqual(b"A\n", (root / "story/a.md").read_bytes())
        record = engine.store.load("tx-completed-progress-fail")
        self.assertEqual("applying", record.state)
        self.assertEqual(("story/a.md",), record.completed)

        engine.store.write_state = write_state
        self.assertEqual(
            "rolled-back", engine.recover("tx-completed-progress-fail").state
        )

    def test_committed_state_failure_rolls_back_but_stays_nonterminal_until_recovery(self):
        root, engine = self.make_engine({"story/a.md": b"A\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (transactions.Change("story/a.md", b"A\n", b"A2\n"),),
            {},
        )
        write_state = engine.store.write_state

        def fail_committed(
            transaction_id: str,
            state: str,
            *,
            completed: tuple[str, ...] = (),
            intents: tuple[str, ...] | None = None,
        ) -> transactions.TransactionRecord:
            kwargs: dict[str, object] = {"completed": completed}
            if intents is not None:
                kwargs["intents"] = intents
            record = write_state(transaction_id, state, **kwargs)
            if state == "committed":
                raise OSError("committed durability injected after install")
            return record

        engine.store.write_state = fail_committed

        with self.assertRaisesRegex(transactions.TransactionError, "committed durability injected"):
            engine.apply(plan, transaction_id="tx-committed-state-fail")

        self.assertEqual(b"A\n", (root / "story/a.md").read_bytes())
        self.assertEqual("applying", engine.store.load("tx-committed-state-fail").state)
        self.assertEqual(
            "rolled-back", engine.recover("tx-committed-state-fail").state
        )

    def test_committed_state_reversion_failure_honors_installed_terminal_state(self):
        root, engine = self.make_engine({"story/a.md": b"A\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (transactions.Change("story/a.md", b"A\n", b"A2\n"),),
            {},
        )
        write_state = engine.store.write_state
        terminal_installed = False

        def fail_committed_and_reversion(
            transaction_id: str,
            state: str,
            *,
            completed: tuple[str, ...] = (),
            intents: tuple[str, ...] | None = None,
        ) -> transactions.TransactionRecord:
            nonlocal terminal_installed
            if terminal_installed and state == "applying":
                raise OSError("committed reversion injected")
            kwargs: dict[str, object] = {"completed": completed}
            if intents is not None:
                kwargs["intents"] = intents
            record = write_state(transaction_id, state, **kwargs)
            if state == "committed":
                terminal_installed = True
                raise OSError("committed installed then raised")
            return record

        engine.store.write_state = fail_committed_and_reversion

        with self.assertRaises(transactions.TransactionError) as raised:
            engine.apply(plan, transaction_id="tx-committed-reversion-fail")

        self.assertIn("committed installed then raised", str(raised.exception))
        self.assertIn("committed state is terminal and was honored", str(raised.exception))
        self.assertNotIn("remains recoverable", str(raised.exception))
        self.assertEqual(b"A2\n", (root / "story/a.md").read_bytes())
        self.assertEqual(
            "committed", engine.store.load("tx-committed-reversion-fail").state
        )
        with self.assertRaisesRegex(transactions.TransactionError, "cannot recover"):
            engine.recover("tx-committed-reversion-fail")

    def test_rolled_back_state_failure_stays_nonterminal_and_retryable(self):
        root, engine = self.make_engine({"story/a.md": b"A\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (transactions.Change("story/a.md", b"A\n", b"A2\n"),),
            {},
        )
        write_state = engine.store.write_state

        def fail_rolled_back(
            transaction_id: str,
            state: str,
            *,
            completed: tuple[str, ...] = (),
            intents: tuple[str, ...] | None = None,
        ) -> transactions.TransactionRecord:
            kwargs: dict[str, object] = {"completed": completed}
            if intents is not None:
                kwargs["intents"] = intents
            record = write_state(transaction_id, state, **kwargs)
            if state == "rolled-back":
                raise OSError("rolled-back durability injected after install")
            return record

        engine.store.write_state = fail_rolled_back
        engine.replace_hook = lambda _source, _destination: (_ for _ in ()).throw(
            OSError("forward injected")
        )

        with self.assertRaises(transactions.TransactionError) as raised:
            engine.apply(plan, transaction_id="tx-rolled-back-state-fail")

        self.assertIn("rolled-back durability injected", str(raised.exception))
        self.assertEqual(b"A\n", (root / "story/a.md").read_bytes())
        self.assertEqual("applying", engine.store.load("tx-rolled-back-state-fail").state)

        engine.store.write_state = write_state
        engine.replace_hook = os.replace
        self.assertEqual(
            "rolled-back", engine.recover("tx-rolled-back-state-fail").state
        )

    def test_rolled_back_state_reversion_failure_honors_installed_terminal_state(self):
        root, engine = self.make_engine({"story/a.md": b"A\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (transactions.Change("story/a.md", b"A\n", b"A2\n"),),
            {},
        )
        write_state = engine.store.write_state
        terminal_installed = False

        def fail_rolled_back_and_reversion(
            transaction_id: str,
            state: str,
            *,
            completed: tuple[str, ...] = (),
            intents: tuple[str, ...] | None = None,
        ) -> transactions.TransactionRecord:
            nonlocal terminal_installed
            if terminal_installed and state == "applying":
                raise OSError("rolled-back reversion injected")
            kwargs: dict[str, object] = {"completed": completed}
            if intents is not None:
                kwargs["intents"] = intents
            record = write_state(transaction_id, state, **kwargs)
            if state == "rolled-back":
                terminal_installed = True
                raise OSError("rolled-back installed then raised")
            return record

        engine.store.write_state = fail_rolled_back_and_reversion
        engine.replace_hook = lambda _source, _destination: (_ for _ in ()).throw(
            OSError("forward injected")
        )

        with self.assertRaises(transactions.TransactionError) as raised:
            engine.apply(plan, transaction_id="tx-rolled-back-reversion-fail")

        self.assertIn("rolled-back installed then raised", str(raised.exception))
        self.assertIn("rolled-back state is terminal and was honored", str(raised.exception))
        self.assertNotIn("remains recoverable", str(raised.exception))
        self.assertEqual(b"A\n", (root / "story/a.md").read_bytes())
        self.assertEqual(
            "rolled-back", engine.store.load("tx-rolled-back-reversion-fail").state
        )
        with self.assertRaisesRegex(transactions.TransactionError, "cannot recover"):
            engine.recover("tx-rolled-back-reversion-fail")

    def test_cleanup_failure_keeps_transaction_nonterminal_for_retry(self):
        root, engine = self.make_engine({"story/a.md": b"A\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (transactions.Change("story/a.md", b"A\n", b"A2\n"),),
            {},
        )
        remove_temporary = engine._remove_temporary
        engine.replace_hook = lambda _source, _destination: (_ for _ in ()).throw(
            OSError("forward injected")
        )
        engine._remove_temporary = lambda _transaction_id, _path: (_ for _ in ()).throw(
            OSError("cleanup injected")
        )

        with self.assertRaisesRegex(transactions.TransactionError, "cleanup injected"):
            engine.apply(plan, transaction_id="tx-cleanup-fail")

        self.assertEqual("applying", engine.store.load("tx-cleanup-fail").state)

        engine._remove_temporary = remove_temporary
        engine.replace_hook = os.replace
        self.assertEqual("rolled-back", engine.recover("tx-cleanup-fail").state)

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

    def test_transactional_directories_apply_rollback_recover_and_undo_exactly(self):
        root, engine = self.make_engine({})
        (root / "story").mkdir()
        parent = root / "story/new/deep"
        plan = transactions.TransactionPlan(
            command=("migrate", "apply"),
            changes=(transactions.Change("story/new/deep/chapter.md", None, b"chapter\n"),),
            metadata={
                "directory-changes": {"create": ["story/new", "story/new/deep"], "remove": []},
                "undoable": True,
            },
        )

        record = engine.apply(plan, transaction_id="tx-directories")
        self.assertEqual(b"chapter\n", (parent / "chapter.md").read_bytes())

        inverse = engine.inverse(record.id)
        self.assertEqual(
            {"create": (), "remove": ("story/new", "story/new/deep")},
            dict(inverse.metadata["directory-changes"]),
        )
        engine.apply(inverse, transaction_id="tx-directories-undo")
        self.assertFalse(root.joinpath("story/new").exists())

        original_install = engine._install_change

        def fail_install(transaction_id, change):
            raise OSError("injected after directory creation")

        engine._install_change = fail_install
        with self.assertRaisesRegex(transactions.TransactionError, "injected"):
            engine.apply(plan, transaction_id="tx-directory-rollback")
        engine._install_change = original_install
        self.assertFalse(root.joinpath("story/new").exists())

        prepared = engine.store.prepare(plan, transaction_id="tx-directory-recover")
        root.joinpath("story/new/deep").mkdir(parents=True)
        engine.store.write_state(
            prepared.id,
            "applying",
            intents=("@directory:create:story/new", "@directory:create:story/new/deep"),
        )
        recovered = engine.recover(prepared.id)
        self.assertEqual("rolled-back", recovered.state)
        self.assertFalse(root.joinpath("story/new").exists())

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
            intents=("story/created.md", "story/deleted.md", "story/updated.md"),
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

    def test_recover_preserves_unexpected_manual_create_delete_and_update_content(self):
        root, engine = self.make_engine(
            {
                "story/deleted.md": b"before-delete\n",
                "story/updated.md": b"before-update\n",
            }
        )
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (
                transactions.Change("story/created.md", None, b"after-create\n"),
                transactions.Change("story/deleted.md", b"before-delete\n", None),
                transactions.Change(
                    "story/updated.md", b"before-update\n", b"after-update\n"
                ),
            ),
            {},
        )
        engine.store.prepare(plan, transaction_id="tx-manual-conflicts")
        engine.store.write_state(
            "tx-manual-conflicts",
            "applying",
            intents=("story/created.md", "story/deleted.md", "story/updated.md"),
        )
        (root / "story/created.md").write_bytes(b"manual-create\n")
        (root / "story/deleted.md").write_bytes(b"manual-delete\n")
        (root / "story/updated.md").write_bytes(b"manual-update\n")

        with self.assertRaises(transactions.TransactionError) as raised:
            engine.recover("tx-manual-conflicts")

        message = str(raised.exception)
        self.assertIn("story/created.md", message)
        self.assertIn("story/deleted.md", message)
        self.assertIn("story/updated.md", message)
        self.assertEqual(b"manual-create\n", (root / "story/created.md").read_bytes())
        self.assertEqual(b"manual-delete\n", (root / "story/deleted.md").read_bytes())
        self.assertEqual(b"manual-update\n", (root / "story/updated.md").read_bytes())
        self.assertEqual("applying", engine.store.load("tx-manual-conflicts").state)

    def test_recover_final_state_failure_has_transaction_context_and_remains_retryable(self):
        root, engine = self.make_engine({"story/a.md": b"A\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (transactions.Change("story/a.md", b"A\n", b"A2\n"),),
            {},
        )
        engine.store.prepare(plan, transaction_id="tx-recovery-state-fail")
        engine.store.write_state(
            "tx-recovery-state-fail", "applying", intents=("story/a.md",)
        )
        (root / "story/a.md").write_bytes(b"A2\n")
        write_state = engine.store.write_state

        def fail_rolled_back(
            transaction_id: str,
            state: str,
            *,
            completed: tuple[str, ...] = (),
            intents: tuple[str, ...] | None = None,
        ) -> transactions.TransactionRecord:
            kwargs: dict[str, object] = {"completed": completed}
            if intents is not None:
                kwargs["intents"] = intents
            record = write_state(transaction_id, state, **kwargs)
            if state == "rolled-back":
                raise OSError("recovery state durability injected after install")
            return record

        engine.store.write_state = fail_rolled_back

        with self.assertRaises(transactions.TransactionError) as raised:
            engine.recover("tx-recovery-state-fail")

        self.assertIn("tx-recovery-state-fail", str(raised.exception))
        self.assertIn("recovery state durability injected", str(raised.exception))
        self.assertEqual(b"A\n", (root / "story/a.md").read_bytes())
        self.assertEqual("applying", engine.store.load("tx-recovery-state-fail").state)

        engine.store.write_state = write_state
        self.assertEqual(
            "rolled-back", engine.recover("tx-recovery-state-fail").state
        )

    def test_recover_rolled_back_reversion_failure_honors_installed_terminal_state(self):
        root, engine = self.make_engine({"story/a.md": b"A\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (transactions.Change("story/a.md", b"A\n", b"A2\n"),),
            {},
        )
        engine.store.prepare(plan, transaction_id="tx-recovery-reversion-fail")
        engine.store.write_state(
            "tx-recovery-reversion-fail", "applying", intents=("story/a.md",)
        )
        (root / "story/a.md").write_bytes(b"A2\n")
        write_state = engine.store.write_state
        terminal_installed = False

        def fail_rolled_back_and_reversion(
            transaction_id: str,
            state: str,
            *,
            completed: tuple[str, ...] = (),
            intents: tuple[str, ...] | None = None,
        ) -> transactions.TransactionRecord:
            nonlocal terminal_installed
            if terminal_installed and state == "applying":
                raise OSError("recovery reversion injected")
            kwargs: dict[str, object] = {"completed": completed}
            if intents is not None:
                kwargs["intents"] = intents
            record = write_state(transaction_id, state, **kwargs)
            if state == "rolled-back":
                terminal_installed = True
                raise OSError("recovery rolled-back installed then raised")
            return record

        engine.store.write_state = fail_rolled_back_and_reversion

        with self.assertRaises(transactions.TransactionError) as raised:
            engine.recover("tx-recovery-reversion-fail")

        self.assertIn(
            "recovery rolled-back installed then raised", str(raised.exception)
        )
        self.assertIn("rolled-back state is terminal and was honored", str(raised.exception))
        self.assertNotIn("remains recoverable", str(raised.exception))
        self.assertEqual(b"A\n", (root / "story/a.md").read_bytes())
        self.assertEqual(
            "rolled-back", engine.store.load("tx-recovery-reversion-fail").state
        )
        with self.assertRaisesRegex(transactions.TransactionError, "cannot recover"):
            engine.recover("tx-recovery-reversion-fail")

    def test_target_directory_sync_failure_after_mutation_is_rolled_back(self):
        root, engine = self.make_engine({"story/a.md": b"A\n"})
        plan = transactions.TransactionPlan(
            ("edit", "apply"),
            (transactions.Change("story/a.md", b"A\n", b"A2\n"),),
            {},
        )
        calls = 0

        def fail_after_forward_mutation(_directory: Path) -> bool:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("target directory fsync injected")
            return True

        engine.directory_sync_hook = fail_after_forward_mutation

        with self.assertRaisesRegex(transactions.TransactionError, "target directory fsync injected"):
            engine.apply(plan, transaction_id="tx-target-fsync-fail")

        self.assertEqual(b"A\n", (root / "story/a.md").read_bytes())
        self.assertEqual("rolled-back", engine.store.load("tx-target-fsync-fail").state)

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
