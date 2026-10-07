"""SQLite retention, legacy migration and crash recovery regressions."""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from . import helpers  # isort: skip

from cwcli import documents
from cwcli import transactions as tx
from cwcli.checks import journal

from .test_transactions_store import make_project


class SQLiteStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.project = make_project(self.root)
        (self.root / "story").mkdir()
        self.store = tx.TransactionStore(self.project)
        self.engine = tx.TransactionEngine(self.project)

    def plan(self, before=None, after=b"new\n", **metadata):
        return tx.TransactionPlan(
            ("edit",), (tx.Change("story/a.md", before, after),), metadata
        )

    def advance(self, count=51):
        for index in range(count):
            path = self.root / "story/a.md"
            before = path.read_bytes() if path.exists() else None
            self.engine.apply(
                self.plan(before, str(index).encode()), transaction_id=f"edit-{index}"
            )

    def test_prepare_stores_deduplicated_bytes_and_context_in_two_files(self):
        plan = tx.TransactionPlan(
            ("edit",),
            (
                tx.Change("story/a.md", b"old", b"new"),
                tx.Change("story/b.md", b"old", b"new"),
            ),
            {"translation-packet": {"direction": "ru"}},
        )
        self.store.prepare(plan, transaction_id="first")
        self.assertEqual({"direction": "ru"}, self.store.packet("first"))
        with closing(sqlite3.connect(self.store.database_path)) as db, db:
            self.assertEqual(2, db.execute("SELECT count(*) FROM blobs").fetchone()[0])
        self.assertEqual(
            {"transactions.sqlite3", "context.sqlite3"},
            {p.name for p in self.store.database_path.parent.iterdir()},
        )
        self.assertEqual("prepared", self.store.load("first").state)
        with self.assertRaises(FileExistsError):
            self.store.prepare(plan, transaction_id="first")

    def test_retention_preserves_50_commits_and_exact_undo(self):
        self.advance()
        entries = self.store.history()
        self.assertEqual(50, len(entries))
        self.assertEqual("edit-50", entries[0]["id"])
        self.assertEqual("edit-1", entries[-1]["id"])
        with self.assertRaisesRegex(tx.TransactionError, "outside the undo history"):
            self.engine.inverse("edit-0")
        self.engine.apply(self.engine.inverse("edit-50"))
        self.assertEqual(b"49", (self.root / "story/a.md").read_bytes())
        self.assertTrue(journal.is_committed_decision(self.project, "edit-0"))
        self.assertFalse(journal.check_journal(self.project))

    def test_context_and_revisions_survive_retention(self):
        data = b"base\r\n"
        revision = documents.logical_hash(data)
        self.store.remember_revision(revision, data)
        self.store.remember_revision(revision, b"base\n")
        self.store.prepare(
            tx.TransactionPlan(
                ("context-test",), (), {"translation-packet": {"units": ["ja:u1"]}}
            ),
            transaction_id="context",
        )
        self.store.write_state("context", "committed")
        self.advance()
        self.assertEqual({"units": ["ja:u1"]}, self.store.packet("context"))
        self.assertEqual(data, self.store.load_revision(revision))
        with self.assertRaises(tx.TransactionError):
            self.store.manifest("context")

    def test_prepared_and_applying_snapshots_are_not_pruned(self):
        self.store.prepare(
            tx.TransactionPlan(
                ("edit",), (tx.Change("story/pending.md", b"before", b"after"),), {}
            ),
            transaction_id="pending",
        )
        self.store.write_state("pending", "applying", intents=("story/pending.md",))
        (self.root / "story/pending.md").write_bytes(b"after")
        self.advance()
        self.assertEqual(51, len(self.store.history()))
        self.engine.recover("pending")
        self.assertEqual(b"before", (self.root / "story/pending.md").read_bytes())

    def test_pruning_deletes_unreferenced_blobs_and_reclaims_database_space(self):
        payload = os.urandom(1024 * 1024)
        self.engine.apply(self.plan(after=payload))
        large_size = self.store.database_path.stat().st_size
        self.advance(52)
        with closing(sqlite3.connect(self.store.database_path)) as db, db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM blobs WHERE id=?",
                    (hashlib.sha256(payload).hexdigest(),),
                ).fetchone()
            )
        self.assertLess(self.store.database_path.stat().st_size, large_size // 2)

    def test_reads_and_preview_do_not_create_databases(self):
        self.assertEqual((), self.store.history())
        self.engine.preview(self.plan())
        self.assertFalse(self.store.database_path.parent.exists())

    def legacy(self):
        legacy = tx.LegacyTransactionStore(self.project)
        legacy.prepare(self.plan(translation_packet="unused"), transaction_id="old")
        legacy.write_state("old", "committed")
        (self.root / "story/a.md").write_bytes(b"new\n")
        return legacy

    def test_legacy_migration_preserves_ids_packets_revisions_and_undo(self):
        legacy = self.legacy()
        manifest = legacy._read_manifest("old")
        manifest["metadata"]["translation-packet"] = {"direction": "ru"}
        (legacy.root / "old/manifest.json").write_text(json.dumps(manifest))
        revision = documents.logical_hash(b"revision\n")
        legacy.remember_revision(revision, b"revision\n")
        self.assertEqual("old", self.store.history()[0]["id"])
        self.assertEqual({"direction": "ru"}, self.store.packet("old"))
        self.assertFalse(self.store.database_path.exists())
        self.engine.apply(self.plan(b"new\n", b"next\n"), transaction_id="next")
        self.assertFalse(legacy.root.exists())
        self.assertEqual({"direction": "ru"}, self.store.packet("old"))
        self.assertEqual(b"revision\n", self.store.load_revision(revision))
        self.engine.apply(self.engine.inverse("next"))
        self.engine.apply(self.engine.inverse("old"))
        self.assertFalse((self.root / "story/a.md").exists())

    def test_corrupt_legacy_import_preserves_files_and_can_retry(self):
        legacy = self.legacy()
        blob = legacy.root / "blobs" / hashlib.sha256(b"new\n").hexdigest()
        blob.write_bytes(b"corrupt")
        with self.assertRaises(tx.TransactionError):
            self.engine.apply(self.plan(b"new\n", b"next\n"))
        self.assertEqual(b"new\n", (self.root / "story/a.md").read_bytes())
        self.assertTrue(blob.exists())
        self.assertEqual("old", self.store.history()[0]["id"])
        blob.write_bytes(b"new\n")
        self.engine.apply(self.plan(b"new\n", b"next\n"))
        self.assertFalse(legacy.root.exists())

    def test_import_resumes_after_commit_before_legacy_cleanup(self):
        legacy = self.legacy()
        with (
            mock.patch.object(
                tx.TransactionStore,
                "_remove_imported_legacy",
                side_effect=OSError("interrupted cleanup"),
            ),
            self.assertRaises(OSError),
        ):
            self.engine.apply(self.plan(b"new\n", b"next\n"))
        self.assertTrue(legacy.root.exists())
        self.assertEqual("old", self.store.history()[0]["id"])
        self.engine.apply(self.plan(b"new\n", b"next\n"))
        self.assertFalse(legacy.root.exists())
        self.assertEqual(2, len(self.store.history()))

    def test_unknown_legacy_files_are_preserved(self):
        legacy = self.legacy()
        unknown = legacy.root / "old/notes.txt"
        unknown.write_text("keep me")
        with self.assertRaisesRegex(tx.TransactionError, "unexpected files"):
            self.store.blob(b"new")
        self.assertEqual("keep me", unknown.read_text())

    def test_database_and_sidecar_symlinks_are_rejected(self):
        self.store.database_path.parent.mkdir()
        outside = Path(self.temp.name) / "outside"
        outside.write_bytes(b"untouched")
        for name in (
            "transactions.sqlite3",
            "context.sqlite3",
            "transactions.sqlite3-journal",
            "context.sqlite3-wal",
        ):
            with self.subTest(name=name):
                linked = self.store.database_path.parent / name
                linked.symlink_to(outside)
                with self.assertRaisesRegex(tx.TransactionError, "without links"):
                    self.store.prepare(self.plan())
                linked.unlink()
                self.assertEqual(b"untouched", outside.read_bytes())

    def test_missing_context_database_is_not_silently_recreated(self):
        self.store.prepare(self.plan())
        self.store.context_path.unlink()
        with self.assertRaisesRegex(tx.TransactionError, "context.sqlite3 is missing"):
            self.store.blob(b"next")
        self.assertFalse(self.store.context_path.exists())

    def test_database_revision_and_blob_corruption_are_reported(self):
        self.store.prepare(self.plan(), transaction_id="prepared")
        revision = documents.logical_hash(b"base")
        self.store.remember_revision(revision, b"base")
        with closing(sqlite3.connect(self.store.database_path)) as db, db:
            db.execute("UPDATE blobs SET data=?", (b"corrupt",))
        with closing(sqlite3.connect(self.store.context_path)) as db, db:
            db.execute("UPDATE revisions SET data=?", (b"corrupt",))
        codes = {finding.code for finding in journal.check_journal(self.project)}
        self.assertTrue(
            {journal.INVALID_BLOB, journal.INVALID_REVISION}.issubset(codes)
        )
        with self.assertRaisesRegex(tx.TransactionError, "exact-byte hash"):
            self.store.load_revision(revision)

    def test_failed_prepare_rolls_back_both_databases(self):
        with (
            mock.patch.object(
                tx.TransactionStore,
                "_save_context",
                side_effect=RuntimeError("interrupt"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.store.prepare(self.plan(), transaction_id="retry")
        self.assertEqual((), self.store.history())
        with closing(sqlite3.connect(self.store.database_path)) as db, db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM blobs").fetchone()[0])
        self.store.prepare(self.plan(), transaction_id="retry")

    def test_process_exit_after_file_replacement_is_recoverable(self):
        script = """
import os, sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from cwcli.project import discover_project
from cwcli.transactions import TransactionEngine, TransactionPlan, Change
root = Path(sys.argv[2])
engine = TransactionEngine(discover_project(root))
def crash(source, destination):
    os.replace(source, destination)
    os._exit(73)
engine.replace_hook = crash
engine.apply(TransactionPlan(('edit',), (Change('story/a.md', None, b'new'),), {}), transaction_id='crash')
"""
        result = subprocess.run(
            [sys.executable, "-c", script, str(helpers.CLI_ROOT), str(self.root)],
            timeout=20,
            check=False,
        )
        self.assertEqual(73, result.returncode)
        self.assertEqual(b"new", (self.root / "story/a.md").read_bytes())
        self.assertEqual("applying", self.store.load("crash").state)
        self.engine.recover("crash")
        self.assertFalse((self.root / "story/a.md").exists())
        self.assertEqual("rolled-back", self.store.load("crash").state)

    def test_changed_legacy_copy_after_import_is_not_deleted(self):
        legacy = self.legacy()
        with (
            mock.patch.object(
                tx.TransactionStore,
                "_remove_imported_legacy",
                side_effect=OSError("interrupt"),
            ),
            self.assertRaises(OSError),
        ):
            self.store.blob(b"new")
        old_manifest = legacy.root / "old/manifest.json"
        old_manifest.write_text("changed by an older cw")
        with self.assertRaisesRegex(tx.TransactionError, "changed after import"):
            self.store.blob(b"new")
        self.assertEqual("changed by an older cw", old_manifest.read_text())
        self.assertEqual("old", self.store.history()[0]["id"])

    def test_legacy_unfinished_transaction_migrates_and_recovers(self):
        legacy = tx.LegacyTransactionStore(self.project)
        legacy.prepare(self.plan(), transaction_id="pending")
        legacy.write_state("pending", "applying", intents=("story/a.md",))
        (self.root / "story/a.md").write_bytes(b"new\n")
        self.engine.recover("pending")
        self.assertFalse((self.root / "story/a.md").exists())
        self.assertEqual("rolled-back", self.store.load("pending").state)
        self.assertFalse(legacy.root.exists())

    def test_revision_logical_corruption_and_bad_digest_are_rejected(self):
        revision = documents.logical_hash(b"base")
        self.store.remember_revision(revision, b"base")
        with closing(sqlite3.connect(self.store.context_path)) as db, db:
            db.execute(
                "UPDATE revisions SET data=?, byte_hash=?",
                (b"other", hashlib.sha256(b"other").hexdigest()),
            )
        with self.assertRaisesRegex(tx.TransactionError, "logical hash"):
            self.store.load_revision(revision)
        with self.assertRaises(ValueError):
            self.store.load_revision("../escape")

    def test_retained_decision_still_requires_valid_snapshots(self):
        self.engine.apply(self.plan(), transaction_id="decision")
        with closing(sqlite3.connect(self.store.database_path)) as db, db:
            db.execute("UPDATE blobs SET data=?", (b"corrupt",))
        self.assertFalse(journal.is_committed_decision(self.project, "decision"))

    def test_process_exit_during_database_write_recovers_both_databases(self):
        self.store.prepare(self.plan(), transaction_id="pending")
        script = """
import os, sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from cwcli.project import discover_project
from cwcli.transactions import TransactionStore
store = TransactionStore(discover_project(Path(sys.argv[2])))
with store._write_database() as db:
    db.execute('PRAGMA main.cache_size=10')
    db.execute('PRAGMA context.cache_size=10')
    db.execute('INSERT INTO blobs VALUES (?, ?)', ('uncommitted', b'x' * 5000000))
    db.execute('INSERT INTO context.revisions VALUES (?, ?, ?)', ('uncommitted', 'invalid', b'y' * 5000000))
    os._exit(74)
"""
        result = subprocess.run(
            [sys.executable, "-c", script, str(helpers.CLI_ROOT), str(self.root)],
            timeout=20,
            check=False,
        )
        self.assertEqual(74, result.returncode)
        self.engine.recover("pending")
        self.assertEqual("rolled-back", self.store.load("pending").state)
        with closing(sqlite3.connect(self.store.database_path)) as db:
            self.assertIsNone(
                db.execute("SELECT 1 FROM blobs WHERE id='uncommitted'").fetchone()
            )
        with closing(sqlite3.connect(self.store.context_path)) as db:
            self.assertIsNone(
                db.execute("SELECT 1 FROM revisions WHERE id='uncommitted'").fetchone()
            )
        self.assertFalse(journal.check_journal(self.project))

    def test_equal_packets_are_deduplicated_and_checked_on_read(self):
        packet = {"direction": "ru", "units": ["ja:u1"]}
        plan = tx.TransactionPlan(("context",), (), {"translation-packet": packet})
        self.store.prepare(plan, transaction_id="first")
        self.store.prepare(plan, transaction_id="second")
        with closing(sqlite3.connect(self.store.context_path)) as db, db:
            self.assertEqual(
                1, db.execute("SELECT count(*) FROM packets").fetchone()[0]
            )
            self.assertEqual(
                2, db.execute("SELECT count(*) FROM packet_refs").fetchone()[0]
            )
        self.assertEqual(packet, self.store.packet("first"))
        self.assertEqual(packet, self.store.packet("second"))
        self.assertEqual(packet, self.store.packet(self.store.packet_id(packet)))
        with closing(sqlite3.connect(self.store.context_path)) as db, db:
            db.execute("UPDATE packets SET packet='{}'")
        with self.assertRaisesRegex(tx.TransactionError, "checksum mismatch"):
            self.store.packet("first")

    def test_legacy_change_during_import_is_preserved_and_not_committed(self):
        legacy = self.legacy()
        original = self.store._save_context
        added = legacy.root / "late-note.txt"

        def change_during_copy(db, identifier, manifest):
            original(db, identifier, manifest)
            added.write_text("concurrent data")

        with (
            mock.patch.object(
                self.store, "_save_context", side_effect=change_during_copy
            ),
            self.assertRaisesRegex(tx.TransactionError, "changed during import"),
        ):
            self.store.blob(b"next")
        self.assertEqual("concurrent data", added.read_text())
        self.assertFalse(self.store._ready())

    def test_cleanup_failure_keeps_committed_result_successful(self):
        with (
            mock.patch.object(
                self.engine.store, "prune", side_effect=KeyError("damaged old record")
            ),
            self.assertWarnsRegex(RuntimeWarning, "transaction committed"),
        ):
            record = self.engine.apply(self.plan(), transaction_id="committed")
        self.assertEqual("committed", record.state)
        self.assertEqual("committed", self.store.load("committed").state)
        self.assertEqual(b"new\n", (self.root / "story/a.md").read_bytes())
