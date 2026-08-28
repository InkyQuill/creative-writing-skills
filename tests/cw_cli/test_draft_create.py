import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import documents, drafts, project, scaffold, transactions


class DraftCreateTests(unittest.TestCase):
    def make_project(self) -> tuple[Path, project.Project, transactions.TransactionStore]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name) / "story-project"
        for relative, data in scaffold.render_scaffold("Draft Test", "ru").items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        model = project.discover_project(root)
        return root, model, transactions.TransactionStore(model)

    def test_existing_target_copies_content_and_records_recoverable_base(self):
        root, model, store = self.make_project()
        accepted = b"\xef\xbb\xbf---\r\nnumber: 4\r\ntitle: Harbor\r\nstatus: accepted\r\n---\r\nOld\r\n"
        target = root / "story/chapters/ch-004.md"
        target.write_bytes(accepted)

        plan = drafts.plan_create_draft(model, "story/chapters/ch-004.md", None, store)

        self.assertEqual(("draft", "create", "story/chapters/ch-004.md"), plan.command)
        self.assertEqual(1, len(plan.changes))
        change = plan.changes[0]
        self.assertEqual("work/drafts/ch-004.md", change.path)
        self.assertIsNone(change.before)
        created = documents.parse_document(change.after)
        self.assertTrue(created.bom)
        self.assertTrue(change.after.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(4, created.metadata["number"])
        self.assertEqual("Harbor", created.metadata["title"])
        self.assertEqual("working", created.metadata["status"])
        self.assertEqual("story/chapters/ch-004.md", created.metadata["target"])
        revision = documents.logical_hash(accepted)
        self.assertEqual(revision, created.metadata["base-revision"])
        self.assertEqual(accepted, store.load_revision(revision))
        self.assertEqual("Old\r\n", created.body)
        self.assertEqual(accepted, target.read_bytes())
        self.assertFalse((root / change.path).exists())

    def test_new_target_uses_custom_path_and_omits_base_revision(self):
        root, model, store = self.make_project()
        plan = drafts.plan_create_draft(
            model,
            "story/chapters/ch-005.md",
            "work/drafts/fifth-pass.md",
            store,
        )
        change = plan.changes[0]
        created = documents.parse_document(change.after)
        self.assertEqual("work/drafts/fifth-pass.md", change.path)
        self.assertEqual("", created.body)
        self.assertNotIn("base-revision", created.metadata)
        self.assertEqual("working", created.metadata["status"])
        self.assertFalse((root / "story/chapters/ch-005.md").exists())
        self.assertFalse(store.root.exists())

    def test_rejects_outside_duplicate_and_colliding_draft_paths(self):
        root, model, store = self.make_project()
        with self.assertRaisesRegex(drafts.DraftError, "story/chapters"):
            drafts.plan_create_draft(model, "kb/canon/ch-004.md", None, store)

        first = drafts.plan_create_draft(model, "story/chapters/ch-004.md", None, store)
        destination = root / first.changes[0].path
        destination.write_bytes(first.changes[0].after)
        with self.assertRaisesRegex(drafts.DraftError, "already"):
            drafts.plan_create_draft(
                model, "story/chapters/ch-004.md", "work/drafts/other.md", store
            )

        collision = root / "work/drafts/existing.md"
        collision.write_text("mine\n", encoding="utf-8")
        with self.assertRaisesRegex(drafts.DraftError, "already exists"):
            drafts.plan_create_draft(
                model, "story/chapters/ch-006.md", "work/drafts/existing.md", store
            )

        with self.assertRaisesRegex(drafts.DraftError, "work/drafts"):
            drafts.plan_create_draft(
                model, "story/chapters/ch-007.md", "", store
            )

    def test_duplicate_targets_use_portable_casefolded_identity(self):
        root, model, store = self.make_project()
        first = drafts.plan_create_draft(
            model, "story/chapters/Harbor.md", "work/drafts/harbor-first.md", store
        )
        (root / first.changes[0].path).write_bytes(first.changes[0].after)

        with self.assertRaisesRegex(drafts.DraftError, "already targets"):
            drafts.plan_create_draft(
                model, "story/chapters/harbor.md", "work/drafts/harbor-second.md", store
            )

    def test_load_draft_rejects_targets_that_project_cannot_safely_resolve(self):
        root, model, _store = self.make_project()
        draft = root / "work/drafts/ch-unsafe.md"

        for target in (
            "story/chapters/CON.md",
            "story/chapters/not<portable.md",
            "story/chapters/back\\slash.md",
            "story/chapters/e\u0301.md",
        ):
            with self.subTest(target=target):
                draft.write_text(
                    f"---\ntarget: {target}\nstatus: working\n---\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(drafts.DraftError, "unsafe draft target"):
                    drafts.load_draft(model, "work/drafts/ch-unsafe.md")

        outside = root.parent / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        linked_target = root / "story/chapters/linked.md"
        linked_target.symlink_to(outside)
        draft.write_text(
            "---\ntarget: story/chapters/linked.md\nstatus: working\n---\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(drafts.DraftError, "symlink"):
            drafts.load_draft(model, "work/drafts/ch-unsafe.md")

        nested_manifest = root / "story/chapters/project.md"
        nested_manifest.write_text("---\ntitle: Nested\n---\n", encoding="utf-8")
        draft.write_text(
            "---\ntarget: story/chapters/new.md\nstatus: working\n---\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(drafts.DraftError, "nested project"):
            drafts.load_draft(model, "work/drafts/ch-unsafe.md")

    def test_load_draft_is_strict_about_location_target_base_and_status(self):
        root, model, _store = self.make_project()
        draft = root / "work/drafts/ch-001.md"
        cases = (
            (b"---\ntarget: kb/canon/ch.md\nstatus: working\n---\n", "target"),
            (b"---\ntarget: story/chapters/ch.md\nbase-revision: nope\nstatus: working\n---\n", "base-revision"),
            (b"---\ntarget: story/chapters/ch.md\nstatus: abandoned\n---\n", "status"),
        )
        for data, message in cases:
            with self.subTest(message=message):
                draft.write_bytes(data)
                with self.assertRaisesRegex(drafts.DraftError, message):
                    drafts.load_draft(model, "work/drafts/ch-001.md")

    def test_revision_normalization_collision_keeps_first_exact_snapshot(self):
        _root, _model, store = self.make_project()
        first = b"\xef\xbb\xbf---\r\ntitle: Same\r\n---\r\nBody\r\n"
        equivalent = b"---\ntitle: Same\n---\nBody\n"
        revision = documents.logical_hash(first)
        self.assertEqual(revision, documents.logical_hash(equivalent))

        store.remember_revision(revision, first)
        store.remember_revision(revision, equivalent)

        self.assertEqual(first, store.load_revision(revision))
        descriptor = json.loads(
            (store.root / "revisions" / revision / "descriptor.json").read_text()
        )
        self.assertEqual(hashlib.sha256(first).hexdigest(), descriptor["byte_hash"])

    def test_revision_store_rejects_mismatch_corruption_and_links(self):
        root, _model, store = self.make_project()
        data = b"---\ntitle: Base\n---\nBody\n"
        revision = documents.logical_hash(data)
        with self.assertRaisesRegex(ValueError, "does not match"):
            store.remember_revision("0" * 64, data)

        store.remember_revision(revision, data)
        snapshot = store.root / "revisions" / revision / "snapshot"
        snapshot.write_bytes(b"corrupt")
        with self.assertRaisesRegex(transactions.TransactionError, "byte hash"):
            store.load_revision(revision)
        descriptor = store.root / "revisions" / revision / "descriptor.json"
        descriptor.write_text(
            json.dumps(
                {
                    "byte_hash": hashlib.sha256(b"corrupt").hexdigest(),
                    "logical_hash": revision,
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(transactions.TransactionError, "logical hash"):
            store.load_revision(revision)

        second = b"second\n"
        second_hash = documents.logical_hash(second)
        outside = root.parent / "outside"
        outside.mkdir()
        (store.root / "revisions" / second_hash).symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(transactions.TransactionError, "without links"):
            store.remember_revision(second_hash, second)
        self.assertEqual([], list(outside.iterdir()))

        linked_data = b"linked\n"
        linked_hash = documents.logical_hash(linked_data)
        store.remember_revision(linked_hash, linked_data)
        linked_descriptor = store.root / "revisions" / linked_hash / "descriptor.json"
        linked_descriptor.unlink()
        linked_descriptor.symlink_to(root.parent / "outside-descriptor.json")
        with self.assertRaisesRegex(transactions.TransactionError, "without links"):
            store.load_revision(linked_hash)

    def test_revision_descriptor_corruption_and_digest_traversal_are_rejected(self):
        _root, _model, store = self.make_project()
        data = b"base\n"
        revision = documents.logical_hash(data)
        store.remember_revision(revision, data)
        descriptor = store.root / "revisions" / revision / "descriptor.json"
        descriptor.write_text('{"byte_hash":"bad"}\n', encoding="utf-8")
        with self.assertRaisesRegex(transactions.TransactionError, "invalid descriptor"):
            store.load_revision(revision)
        for unsafe in ("../escape", "/absolute", "A" * 64):
            with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                store.load_revision(unsafe)


if __name__ == "__main__":
    unittest.main()
