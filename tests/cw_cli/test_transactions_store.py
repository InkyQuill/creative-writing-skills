import hashlib
import json
import tempfile
import unittest
from pathlib import Path

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
        self.assertEqual(["changes", "command", "completed", "metadata", "state", "timestamp"], list(manifest))
        self.assertEqual(["edit", "replace"], manifest["command"])
        self.assertEqual({"reason": "replace repeated heading"}, manifest["metadata"])
        self.assertRegex(manifest["timestamp"], r"^\d{4}-\d{2}-\d{2}T.*\+00:00$")
        self.assertEqual("prepared", manifest["state"])
        self.assertEqual([], manifest["completed"])
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

    def test_write_state_preserves_prepared_manifest_content(self):
        store = self.make_store()
        plan = transactions.TransactionPlan(
            command=("edit", "replace"),
            changes=(transactions.Change("story/chapters/ch-001.md", b"old\n", b"new\n"),),
            metadata={"undoable": True},
        )
        store.prepare(plan, transaction_id="tx-state")
        before = json.loads((store.root / "tx-state" / "manifest.json").read_text(encoding="utf-8"))

        record = store.write_state("tx-state", "applying", completed=("story/chapters/ch-001.md",))
        after = json.loads((store.root / "tx-state" / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(transactions.TransactionRecord("tx-state", "applying", ("story/chapters/ch-001.md",)), record)
        self.assertEqual(record, store.load("tx-state"))
        self.assertEqual(before["timestamp"], after["timestamp"])
        self.assertEqual(before["command"], after["command"])
        self.assertEqual(before["changes"], after["changes"])
        self.assertEqual(before["metadata"], after["metadata"])
        self.assertEqual("applying", after["state"])
        self.assertEqual(["story/chapters/ch-001.md"], after["completed"])
        self.assertFalse(list((store.root / "tx-state").glob(".manifest.json.*.tmp")))


if __name__ == "__main__":
    unittest.main()
