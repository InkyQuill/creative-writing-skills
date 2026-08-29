import hashlib
import json
import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import app, documents, project, scaffold, transactions
from cwcli.checks import journal


def make_project(root: Path) -> project.Project:
    for relative, data in scaffold.render_scaffold("Journal", "en").items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (root / ".creative-writing/context").mkdir(parents=True, exist_ok=True)
    (root / ".creative-writing/transactions").mkdir(parents=True, exist_ok=True)
    return project.discover_project(root)


class JournalCheckTests(unittest.TestCase):
    def test_symlinked_protected_ancestor_is_reported_without_reading_outside(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            outside = Path(directory) / "outside"
            outside.mkdir()
            (outside / "transactions").mkdir()
            sentinel = outside / "transactions" / "secret"
            sentinel.mkdir()
            (sentinel / "manifest.json").write_text("not json", encoding="utf-8")
            protected = root / ".creative-writing"
            for child in tuple(protected.iterdir()):
                if child.is_dir():
                    child.rmdir()
            protected.rmdir()
            os.symlink(outside, protected)

            findings = journal.check_journal(model)

            self.assertEqual([journal.INVALID_LAYOUT], [item.code for item in findings])
            self.assertNotIn("secret", " ".join(item.path or "" for item in findings))

    def test_recovery_critical_manifest_corruption_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            store = transactions.TransactionStore(model)
            plan = transactions.TransactionPlan(
                command=("edit",),
                changes=(transactions.Change("story/new.md", None, b"new\n"),),
                metadata={"directory-changes": {"create": ["work/new"], "remove": []}},
            )
            store.prepare(plan, transaction_id="tx-corrupt")
            manifest_path = store.root / "tx-corrupt/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["changes"].append(dict(manifest["changes"][0]))
            manifest["changes"].append(dict(manifest["changes"][0]))
            manifest["changes"][0]["path"] = "../outside.md"
            manifest["metadata"]["directory-changes"] = {
                "create": ["work/new", "work/new"],
                "remove": ["work/new"],
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            findings = journal.check_journal(model)

            messages = " ".join(item.message for item in findings)
            self.assertIn("invalid path", messages)
            self.assertIn("duplicate change", messages)
            self.assertIn("duplicates", messages)
            self.assertIn("both created and removed", messages)

    def test_recover_cli_previews_then_applies_and_refuses_terminal_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            store = transactions.TransactionStore(model)
            plan = transactions.TransactionPlan(command=("edit",), changes=(), metadata={})
            store.prepare(plan, transaction_id="tx-recover")

            stdout, stderr = StringIO(), StringIO()
            preview_status = app.run(["recover", "tx-recover", "--format", "json"], cwd=root, stdout=stdout, stderr=stderr)
            self.assertEqual(0, preview_status)
            self.assertEqual("prepared", store.load("tx-recover").state)
            self.assertEqual("preview", json.loads(stdout.getvalue())["status"])

            stdout, stderr = StringIO(), StringIO()
            apply_status = app.run(["recover", "tx-recover", "--apply", "--format", "json"], cwd=root, stdout=stdout, stderr=stderr)
            self.assertEqual(0, apply_status)
            self.assertEqual("rolled-back", json.loads(stdout.getvalue())["status"])

            stdout, stderr = StringIO(), StringIO()
            refused = app.run(["recover", "tx-recover", "--apply"], cwd=root, stdout=stdout, stderr=stderr)
            self.assertEqual(2, refused)
            self.assertIn("cannot recover", stderr.getvalue())

    def test_recovery_preflight_conflict_is_read_only_and_never_advertises_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            target = root / "story/existing.md"
            target.write_bytes(b"before\n")
            store = transactions.TransactionStore(model)
            plan = transactions.TransactionPlan(("edit",), (transactions.Change("story/existing.md", b"before\n", b"after\n"),), {})
            store.prepare(plan, transaction_id="tx-conflict")
            store.write_state("tx-conflict", "applying", intents=("story/existing.md",))
            target.write_bytes(b"manual\n")
            before = target.read_bytes()
            stdout, stderr = StringIO(), StringIO()
            status = app.run(["recover", "tx-conflict", "--format", "json"], cwd=root, stdout=stdout, stderr=stderr)
            self.assertEqual(1, status)
            self.assertEqual(before, target.read_bytes())
            findings = journal.check_journal(model)
            self.assertNotIn(journal.INCOMPLETE_TRANSACTION, {item.code for item in findings})
            self.assertFalse(any(item.next_action and "--apply" in item.next_action for item in findings))

    def test_missing_manifest_and_symlinked_revision_descriptor_do_not_abort_peers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            store = transactions.TransactionStore(model)
            (store.root / "tx-missing").mkdir()
            data = b"chapter\n"
            revision = store.remember_revision(documents.logical_hash(data), data)
            descriptor = store.root / "revisions" / revision / "descriptor.json"
            descriptor.unlink()
            os.symlink(Path(directory) / "outside.json", descriptor)

            findings = journal.check_journal(model)

            codes = {item.code for item in findings}
            self.assertTrue({journal.INVALID_MANIFEST, journal.INVALID_REVISION}.issubset(codes))

    def test_incomplete_transaction_has_exact_recovery_action_and_terminal_does_not(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            store = transactions.TransactionStore(model)
            plan = transactions.TransactionPlan(command=("edit",), changes=(), metadata={"undoable": True})
            store.prepare(plan, transaction_id="tx-prepared")
            store.prepare(plan, transaction_id="tx-terminal")
            store.write_state("tx-terminal", "committed")

            findings = journal.check_journal(model)

            incomplete = [item for item in findings if item.code == journal.INCOMPLETE_TRANSACTION]
            self.assertEqual(1, len(incomplete))
            self.assertEqual("cw recover tx-prepared --apply", incomplete[0].next_action)
            stdout, stderr = StringIO(), StringIO()
            command_status = app.run(
                incomplete[0].next_action.split()[1:],
                cwd=root,
                stdout=stdout,
                stderr=stderr,
            )
            self.assertEqual(0, command_status)
            self.assertEqual("rolled-back", store.load("tx-prepared").state)

    def test_missing_corrupt_and_symlink_blobs_are_independent_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            store = transactions.TransactionStore(model)
            plan = transactions.TransactionPlan(command=("edit",), changes=(transactions.Change("story/new.md", None, b"new\n"),), metadata={})
            store.prepare(plan, transaction_id="tx")
            manifest = json.loads((store.root / "tx/manifest.json").read_text(encoding="utf-8"))
            identifier = manifest["changes"][0]["after"]["blob"]
            (store.root / "blobs" / identifier).write_bytes(b"corrupt")
            os.symlink(Path(directory) / "outside", store.root / "blobs" / ("f" * 64))

            findings = journal.check_journal(model)

            self.assertGreaterEqual(sum(item.code == journal.INVALID_BLOB for item in findings), 2)

    def test_revision_descriptor_exact_and_logical_hashes_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            store = transactions.TransactionStore(model)
            data = b"chapter\r\n"
            revision = store.remember_revision(documents.logical_hash(data), data)
            descriptor = store.root / "revisions" / revision / "descriptor.json"
            payload = json.loads(descriptor.read_text(encoding="utf-8"))
            payload["byte_hash"] = "0" * 64
            descriptor.write_text(json.dumps(payload), encoding="utf-8")

            findings = journal.check_journal(model)

            self.assertIn(journal.INVALID_REVISION, {item.code for item in findings})
