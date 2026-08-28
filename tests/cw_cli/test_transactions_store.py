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
