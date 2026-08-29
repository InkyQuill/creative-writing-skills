import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import documents, project, scaffold, transactions
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
            self.assertEqual("Run cw recover tx-prepared --apply to restore before-snapshots and mark it rolled-back.", incomplete[0].next_action)

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
