import errno
import hashlib
import json
import os
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import documents, project, transactions


def make_project(root: Path) -> project.Project:
    root.mkdir(parents=True, exist_ok=True)
    (root / "project.md").write_text("---\ntitle: Test project\n---\n", encoding="utf-8")
    return project.discover_project(root)


class TransactionStoreTests(unittest.TestCase):
    def make_store(self) -> transactions.TransactionStore:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        return transactions.TransactionStore(make_project(Path(self.directory.name) / "project"))

    def test_prepare_persists_immutable_manifest_with_deduplicated_before_after_blobs(self):
        store = self.make_store()
        old = b"old\n"
        new = b"new\n"
        plan = transactions.TransactionPlan(
            command=("edit", "replace"),
            changes=(
                transactions.Change("story/chapters/ch-001.md", old, new),
                transactions.Change("story/chapters/ch-002.md", old, new),
            ),
            metadata={"reason": "replace repeated heading"},
        )

        record = store.prepare(plan, transaction_id="tx-test")
        manifest_path = store.root / "tx-test" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(transactions.TransactionRecord("tx-test", "prepared", ()), record)
        self.assertEqual(
            ["changes", "command", "completed", "intents", "metadata", "state", "timestamp"],
            list(manifest),
        )
        self.assertEqual(["edit", "replace"], manifest["command"])
        self.assertEqual({"reason": "replace repeated heading"}, manifest["metadata"])
        self.assertRegex(manifest["timestamp"], r"^\d{4}-\d{2}-\d{2}T.*\+00:00$")
        self.assertEqual("prepared", manifest["state"])
        self.assertEqual([], manifest["completed"])
        self.assertEqual([], manifest["intents"])
        self.assertEqual(
            ["story/chapters/ch-001.md", "story/chapters/ch-002.md"],
            [change["path"] for change in manifest["changes"]],
        )

        old_id = hashlib.sha256(old).hexdigest()
        new_id = hashlib.sha256(new).hexdigest()
        first_change = manifest["changes"][0]
        self.assertEqual(
            {"blob": old_id, "byte_hash": old_id, "logical_hash": documents.logical_hash(old)},
            first_change["before"],
        )
        self.assertEqual(
            {"blob": new_id, "byte_hash": new_id, "logical_hash": documents.logical_hash(new)},
            first_change["after"],
        )
        self.assertEqual(
            "--- story/chapters/ch-001.md\n"
            "+++ story/chapters/ch-001.md\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n",
            first_change["diff"],
        )
        self.assertEqual(old, (store.root / "blobs" / old_id).read_bytes())
        self.assertEqual(new, (store.root / "blobs" / new_id).read_bytes())
        self.assertEqual(2, len(list((store.root / "blobs").iterdir())))

        with self.assertRaises(FileExistsError):
            store.prepare(plan, transaction_id="tx-test")

    def test_prepare_rejects_symlinked_protected_components_without_snapshot_leakage(self):
        for component in (".creative-writing", ".creative-writing/transactions"):
            with self.subTest(component=component):
                store = self.make_store()
                external = Path(self.directory.name) / "external"
                external.mkdir()
                linked = store.project.root / component
                linked.parent.mkdir(parents=True, exist_ok=True)
                linked.symlink_to(external, target_is_directory=True)

                with self.assertRaisesRegex(transactions.TransactionError, "without links"):
                    store.prepare(
                        transactions.TransactionPlan(
                            ("edit", "replace"),
                            (transactions.Change("story/a.md", b"secret", b"changed"),),
                            {},
                        ),
                        transaction_id="tx-link",
                    )

                self.assertEqual([], list(external.iterdir()))

    def test_prepare_rejects_symlinked_blobs_and_transaction_directory(self):
        for component in ("blobs", "tx-link"):
            with self.subTest(component=component):
                store = self.make_store()
                (store.project.root / ".creative-writing/transactions").mkdir(parents=True)
                external = Path(self.directory.name) / "external"
                external.mkdir()
                (store.root / component).symlink_to(external, target_is_directory=True)

                error = transactions.TransactionError if component == "blobs" else FileExistsError
                with self.assertRaises(error):
                    store.prepare(
                        transactions.TransactionPlan(
                            ("edit", "replace"),
                            (transactions.Change("story/a.md", b"secret", b"changed"),),
                            {},
                        ),
                        transaction_id="tx-link",
                    )

                self.assertEqual([], list(external.iterdir()))

    def test_load_and_blob_read_reject_symlinked_journal_files(self):
        store = self.make_store()
        plan = transactions.TransactionPlan(
            ("edit", "replace"),
            (transactions.Change("story/a.md", b"old\n", b"new\n"),),
            {},
        )
        store.prepare(plan, transaction_id="tx-files")
        external_manifest = Path(self.directory.name) / "outside-manifest.json"
        external_manifest.write_text('{"state": "committed"}\n', encoding="utf-8")
        manifest = store.root / "tx-files/manifest.json"
        manifest.unlink()
        manifest.symlink_to(external_manifest)

        with self.assertRaisesRegex(transactions.TransactionError, "without links"):
            store.load("tx-files")
        self.assertEqual('{"state": "committed"}\n', external_manifest.read_text())

        blob_id = hashlib.sha256(b"old\n").hexdigest()
        external_blob = Path(self.directory.name) / "outside-blob"
        external_blob.write_bytes(b"outside secret")
        blob = store.root / "blobs" / blob_id
        blob.unlink()
        blob.symlink_to(external_blob)

        with self.assertRaisesRegex(transactions.TransactionError, "without links"):
            store.read_blob(blob_id)
        self.assertEqual(b"outside secret", external_blob.read_bytes())

    def test_blob_read_requires_digest_before_constructing_a_path(self):
        store = self.make_store()
        payload = b"valid snapshot\n"
        blob_id = store.blob(payload)
        outside_relative = store.root / "outside"
        outside_relative.write_bytes(b"relative escape")
        outside_absolute = Path(self.directory.name) / "absolute-escape"
        outside_absolute.write_bytes(b"absolute escape")

        self.assertEqual(payload, store.read_blob(blob_id))
        for identifier in (
            "../outside",
            str(outside_absolute),
            "0" * 63,
            "A" * 64,
            "g" * 64,
        ):
            with self.subTest(identifier=identifier), self.assertRaisesRegex(
                ValueError, "lowercase SHA-256 digest"
            ):
                store.read_blob(identifier)

        self.assertEqual(b"relative escape", outside_relative.read_bytes())
        self.assertEqual(b"absolute escape", outside_absolute.read_bytes())

    def test_history_rejects_symlinked_transaction_entry(self):
        store = self.make_store()
        (store.project.root / ".creative-writing/transactions/blobs").mkdir(parents=True)
        external = Path(self.directory.name) / "outside-history"
        external.mkdir()
        (store.root / "tx-link").symlink_to(external, target_is_directory=True)

        with self.assertRaisesRegex(transactions.TransactionError, "without links"):
            store.history()

        self.assertEqual([], list(external.iterdir()))

    def test_apply_rejects_symlinked_staged_sibling_before_journal_write(self):
        store = self.make_store()
        target = store.project.root / "story/a.md"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"old\n")
        engine = transactions.TransactionEngine(store.project)
        staged = engine._temporary_path("tx-stage", "story/a.md")
        external = Path(self.directory.name) / "outside-stage"
        external.write_bytes(b"outside secret")
        staged.symlink_to(external)

        with self.assertRaisesRegex(transactions.TransactionError, "staged transaction sibling"):
            engine.apply(
                transactions.TransactionPlan(
                    ("edit", "replace"),
                    (transactions.Change("story/a.md", b"old\n", b"new\n"),),
                    {},
                ),
                transaction_id="tx-stage",
            )

        self.assertFalse(store.root.exists())
        self.assertEqual(b"old\n", target.read_bytes())
        self.assertEqual(b"outside secret", external.read_bytes())

    def test_plan_metadata_is_an_immutable_snapshot_of_nested_json_data(self):
        metadata = {"nested": {"items": ["first"]}}
        plan = transactions.TransactionPlan(
            command=("edit", "replace"),
            changes=(transactions.Change("story/chapters/ch-001.md", b"old\n", b"new\n"),),
            metadata=metadata,
        )
        metadata["nested"]["items"].append("later")

        with self.assertRaises(TypeError):
            plan.metadata["new"] = "value"
        with self.assertRaises(TypeError):
            plan.metadata["nested"]["new"] = "value"
        with self.assertRaises(AttributeError):
            plan.metadata["nested"]["items"].append("later")

        store = self.make_store()
        store.prepare(plan, transaction_id="tx-metadata")
        manifest = json.loads((store.root / "tx-metadata" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual({"nested": {"items": ["first"]}}, manifest["metadata"])

    def test_change_rejects_non_project_relative_paths(self):
        paths = (
            "",
            "/story/chapters/ch-001.md",
            "C:/story/chapters/ch-001.md",
            "story\\chapter.md",
            ".",
            "..",
            "story/./chapter.md",
            "story/../chapter.md",
            "story//chapter.md",
            "story/chapter.md/",
        )
        for path in paths:
            with self.subTest(path=path), self.assertRaises(ValueError):
                transactions.Change(path, b"old\n", b"new\n")

    def test_prepare_failure_before_manifest_write_leaves_transaction_id_reusable(self):
        store = self.make_store()
        invalid_plan = transactions.TransactionPlan(
            command=("edit", "replace"),
            changes=(transactions.Change("story/chapters/ch-001.md", b"old\n", b"new\n"),),
            metadata={"unsupported": object()},
        )

        with self.assertRaises(TypeError):
            store.prepare(invalid_plan, transaction_id="tx-retry")
        self.assertFalse((store.root / "tx-retry").exists())

        record = store.prepare(
            transactions.TransactionPlan(
                command=("edit", "replace"),
                changes=(transactions.Change("story/chapters/ch-001.md", b"old\n", b"new\n"),),
                metadata={},
            ),
            transaction_id="tx-retry",
        )
        self.assertEqual(transactions.TransactionRecord("tx-retry", "prepared", ()), record)

    def test_prepare_records_create_and_delete_with_null_snapshot_references(self):
        store = self.make_store()
        created = b"created\n"
        deleted = b"deleted\n"
        store.prepare(
            transactions.TransactionPlan(
                command=("edit", "apply"),
                changes=(
                    transactions.Change("story/chapters/new.md", None, created),
                    transactions.Change("story/chapters/old.md", deleted, None),
                ),
                metadata={},
            ),
            transaction_id="tx-create-delete",
        )
        manifest = json.loads(
            (store.root / "tx-create-delete" / "manifest.json").read_text(encoding="utf-8")
        )

        null_reference = {"blob": None, "byte_hash": None, "logical_hash": None}
        created_id = hashlib.sha256(created).hexdigest()
        deleted_id = hashlib.sha256(deleted).hexdigest()
        self.assertEqual(null_reference, manifest["changes"][0]["before"])
        self.assertEqual(
            {
                "blob": created_id,
                "byte_hash": created_id,
                "logical_hash": documents.logical_hash(created),
            },
            manifest["changes"][0]["after"],
        )
        self.assertEqual(
            "--- story/chapters/new.md\n+++ story/chapters/new.md\n@@ -0,0 +1 @@\n+created\n",
            manifest["changes"][0]["diff"],
        )
        self.assertEqual(
            {
                "blob": deleted_id,
                "byte_hash": deleted_id,
                "logical_hash": documents.logical_hash(deleted),
            },
            manifest["changes"][1]["before"],
        )
        self.assertEqual(null_reference, manifest["changes"][1]["after"])
        self.assertEqual(
            "--- story/chapters/old.md\n+++ story/chapters/old.md\n@@ -1 +0,0 @@\n-deleted\n",
            manifest["changes"][1]["diff"],
        )
        self.assertEqual(2, len(list((store.root / "blobs").iterdir())))

    def test_write_state_preserves_prepared_manifest_content(self):
        store = self.make_store()
        plan = transactions.TransactionPlan(
            command=("edit", "replace"),
            changes=(transactions.Change("story/chapters/ch-001.md", b"old\n", b"new\n"),),
            metadata={"undoable": True},
        )
        store.prepare(plan, transaction_id="tx-state")
        before = json.loads((store.root / "tx-state" / "manifest.json").read_text(encoding="utf-8"))

        record = store.write_state(
            "tx-state",
            "applying",
            completed=("story/chapters/ch-001.md",),
            intents=("story/chapters/ch-001.md",),
        )
        after = json.loads((store.root / "tx-state" / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(transactions.TransactionRecord("tx-state", "applying", ("story/chapters/ch-001.md",)), record)
        self.assertEqual(record, store.load("tx-state"))
        self.assertEqual(before["timestamp"], after["timestamp"])
        self.assertEqual(before["command"], after["command"])
        self.assertEqual(before["changes"], after["changes"])
        self.assertEqual(before["metadata"], after["metadata"])
        self.assertEqual("applying", after["state"])
        self.assertEqual(["story/chapters/ch-001.md"], after["completed"])
        self.assertEqual(["story/chapters/ch-001.md"], after["intents"])
        self.assertFalse(list((store.root / "tx-state").glob(".manifest.json.*.tmp")))

    def test_atomic_blob_install_syncs_parent_before_and_after_replace(self):
        store = self.make_store()
        destination = store.root / "blobs" / "blob"
        destination.parent.mkdir(parents=True)
        events: list[str] = []
        replace = os.replace

        def sync_parent(_directory: Path) -> bool:
            events.append("sync")
            return True

        def record_replace(source: os.PathLike[str], target: os.PathLike[str]) -> None:
            events.append("replace")
            replace(source, target)

        store.directory_sync_hook = sync_parent
        with mock.patch.object(transactions.os, "replace", side_effect=record_replace):
            store._write_bytes(destination, b"content\n")

        self.assertEqual(["sync", "replace", "sync"], events)
        self.assertEqual(b"content\n", destination.read_bytes())

    def test_directory_fsync_warns_when_platform_cannot_sync_directories(self):
        store = self.make_store()
        unsupported = OSError(errno.EINVAL, "directory fsync unsupported")

        with (
            mock.patch.object(transactions.os, "open", side_effect=unsupported),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            supported = transactions._fsync_directory(store.root)

        self.assertFalse(supported)
        self.assertTrue(
            any("directory fsync is unsupported" in str(warning.message) for warning in caught)
        )


if __name__ == "__main__":
    unittest.main()
