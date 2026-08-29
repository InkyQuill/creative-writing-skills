import tempfile
import unittest
from pathlib import Path

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import documents, drafts, indexes, project, scaffold, transactions


class DraftLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "story-project"
        for relative, data in scaffold.render_scaffold("Lifecycle Test", "ru").items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.model = project.discover_project(self.root)
        self.store = transactions.TransactionStore(self.model)

    def make_draft(
        self,
        *,
        target_exists: bool = True,
        status: str = "ready",
        body: str = "Draft body\n",
        target: str = "story/chapters/ch-004.md",
        bom: bool = False,
        newline: str = "\n",
    ) -> tuple[Path, Path | None]:
        target_path = self.root / target
        if target_exists:
            target_source = documents.render_document(
                documents.Document(
                    metadata={"number": 4, "title": "Harbor", "status": "old"},
                    body=f"Old{newline}",
                    newline=newline,
                    bom=bom,
                )
            )
            target_path.write_bytes(target_source)
        creation = drafts.plan_create_draft(self.model, target, None, self.store)
        draft_path = self.root / creation.changes[0].path
        created = documents.parse_document(creation.changes[0].after)
        metadata = dict(created.metadata)
        metadata["status"] = status
        draft_path.write_bytes(
            documents.render_document(
                documents.Document(
                    metadata=metadata,
                    body=body,
                    newline=newline,
                    bom=bom,
                )
            )
        )
        return draft_path, target_path if target_exists else None

    def managed_files(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for root_name in ("story", "work", "kb")
            for path in (self.root / root_name).rglob("*")
            if path.is_file()
        }

    def test_accept_is_read_only_and_plans_story_archive_and_indexes_not_kb(self):
        body = "<AI>Первая <AI>вложенная</AI></AI>\r\nВторая <AI>строка</AI>\r\n"
        draft_path, target_path = self.make_draft(
            body=body, bom=True, newline="\r\n"
        )
        assert target_path is not None
        kb_note = self.root / "kb/canon/fact.md"
        kb_note.write_bytes(b"---\ntitle: Fact\n---\nCanon\n")
        for change in indexes.plan_reindex(self.model).changes:
            if change.path.startswith("work/") and change.after is not None:
                (self.root / change.path).write_bytes(change.after)
        before = self.managed_files()

        plan = drafts.plan_accept_draft(
            self.model, "work/drafts/ch-004.md", self.store, "tx-accept"
        )

        self.assertEqual(before, self.managed_files())
        changed = {change.path for change in plan.changes}
        self.assertIn("story/chapters/ch-004.md", changed)
        self.assertIn("work/archive/ch-004--tx-accept.md", changed)
        self.assertIn("work/drafts/ch-004.md", changed)
        self.assertIn("story/chapters/_index.md", changed)
        self.assertIn("work/archive/_index.md", changed)
        self.assertFalse(any(path.startswith("kb/") for path in changed))

        target_change = next(
            change for change in plan.changes if change.path == "story/chapters/ch-004.md"
        )
        accepted = documents.parse_document(target_change.after)
        self.assertTrue(accepted.bom)
        self.assertEqual("\r\n", accepted.newline)
        self.assertEqual("Первая вложенная\r\nВторая строка\r\n", accepted.body)
        for key in (
            "target",
            "base-revision",
            "status",
            "accepted-transaction",
            "abandoned-transaction",
        ):
            self.assertNotIn(key, accepted.metadata)
        self.assertEqual(4, accepted.metadata["number"])
        self.assertEqual("Harbor", accepted.metadata["title"])

        archive_change = next(
            change
            for change in plan.changes
            if change.path == "work/archive/ch-004--tx-accept.md"
        )
        archived = documents.parse_document(archive_change.after)
        self.assertEqual("accepted", archived.metadata["status"])
        self.assertEqual("tx-accept", archived.metadata["accepted-transaction"])
        self.assertEqual(body, archived.body)
        archive_index = next(
            change.after
            for change in plan.changes
            if change.path == "work/archive/_index.md"
        )
        self.assertIn(b"work/archive/ch-004--tx-accept.md", archive_index)
        drafts_index = next(
            change.after
            for change in plan.changes
            if change.path == "work/drafts/_index.md"
        )
        self.assertNotIn(b"work/drafts/ch-004.md", drafts_index)
        self.assertEqual(b"---\ntitle: Fact\n---\nCanon\n", kb_note.read_bytes())
        self.assertEqual(before["work/drafts/ch-004.md"], draft_path.read_bytes())

    def test_accept_apply_and_undo_restore_exact_managed_bytes(self):
        self.make_draft(body="<AI>Accepted</AI>\n")
        before = self.managed_files()
        engine = transactions.TransactionEngine(self.model)
        plan = drafts.plan_accept_draft(
            self.model, "work/drafts/ch-004.md", self.store, "tx-roundtrip"
        )

        engine.preview(plan)
        record = engine.apply(plan, transaction_id="tx-roundtrip")
        self.assertEqual("committed", record.state)
        self.assertFalse((self.root / "work/drafts/ch-004.md").exists())
        self.assertTrue((self.root / "work/archive/ch-004--tx-roundtrip.md").exists())
        self.assertEqual(
            "Accepted\n",
            documents.parse_document(
                (self.root / "story/chapters/ch-004.md").read_bytes()
            ).body,
        )

        inverse = engine.inverse("tx-roundtrip")
        engine.apply(inverse, transaction_id="tx-roundtrip-undo")
        self.assertEqual(before, self.managed_files())

    def test_accept_creates_a_still_absent_new_target(self):
        self.make_draft(
            target_exists=False,
            target="story/chapters/ch-005.md",
            body="<AI>New chapter</AI>\n",
        )

        plan = drafts.plan_accept_draft(
            self.model, "work/drafts/ch-005.md", self.store, "tx-new-target"
        )

        target_change = next(
            change
            for change in plan.changes
            if change.path == "story/chapters/ch-005.md"
        )
        self.assertIsNone(target_change.before)
        self.assertEqual(
            "New chapter\n", documents.parse_document(target_change.after).body
        )
        transactions.TransactionEngine(self.model).apply(
            plan, transaction_id="tx-new-target"
        )
        self.assertEqual(target_change.after, (self.root / target_change.path).read_bytes())

    def test_existing_target_format_wins_when_logical_bytes_are_equal(self):
        self.make_draft(body="Draft line one\nDraft line two\n")
        target = self.root / "story/chapters/ch-004.md"
        exact_current = target.read_bytes().replace(b"\n", b"\r\n")
        exact_current = b"\xef\xbb\xbf" + exact_current
        self.assertEqual(
            documents.logical_hash(target.read_bytes()),
            documents.logical_hash(exact_current),
        )
        target.write_bytes(exact_current)

        plan = drafts.plan_accept_draft(
            self.model, "work/drafts/ch-004.md", self.store, "tx-format"
        )

        target_change = next(
            change
            for change in plan.changes
            if change.path == "story/chapters/ch-004.md"
        )
        self.assertEqual(exact_current, target_change.before)
        self.assertTrue(target_change.after.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\n", target_change.after.replace(b"\r\n", b""))
        accepted = documents.parse_document(target_change.after)
        self.assertEqual("\r\n", accepted.newline)
        self.assertTrue(accepted.bom)
        self.assertEqual("Draft line one\r\nDraft line two\r\n", accepted.body)

    def test_lifecycle_selected_indexes_ignore_malformed_unrelated_roots(self):
        self.make_draft()
        malformed_kb = self.root / "kb/canon/broken.md"
        malformed_kb.write_bytes(b"---\ntitle: [unsupported]\n---\n")

        accepted = drafts.plan_accept_draft(
            self.model, "work/drafts/ch-004.md", self.store, "tx-scoped-accept"
        )
        self.assertTrue(accepted.changes)
        with self.assertRaises(documents.DocumentError):
            indexes.plan_reindex(self.model)

        malformed_kb.unlink()
        malformed_story = self.root / "story/chapters/broken.md"
        malformed_story.write_bytes(b"---\ntitle: [unsupported]\n---\n")

        abandoned = drafts.plan_abandon_draft(
            self.model, "work/drafts/ch-004.md", "tx-scoped-abandon"
        )
        self.assertTrue(abandoned.changes)
        self.assertFalse(
            any(change.path.startswith("story/") for change in abandoned.changes)
        )
        with self.assertRaises(documents.DocumentError):
            indexes.plan_reindex(self.model)

    def test_accept_rejects_status_stale_missing_base_and_new_target_collision(self):
        draft_path, target_path = self.make_draft(status="review")
        with self.assertRaisesRegex(drafts.DraftError, "status ready"):
            drafts.plan_accept_draft(
                self.model, "work/drafts/ch-004.md", self.store, "tx-status"
            )

        document = documents.parse_document(draft_path.read_bytes())
        metadata = dict(document.metadata)
        metadata["status"] = "ready"
        draft_path.write_bytes(
            documents.render_document(
                documents.Document(metadata, document.body, document.newline, document.bom)
            )
        )
        assert target_path is not None
        target_path.write_bytes(target_path.read_bytes() + b"manual\n")
        with self.assertRaisesRegex(drafts.DraftError, "stale"):
            drafts.plan_accept_draft(
                self.model, "work/drafts/ch-004.md", self.store, "tx-stale"
            )

        draft_path.unlink()
        new_draft, _ = self.make_draft(
            target_exists=False, target="story/chapters/ch-005.md"
        )
        new_target = self.root / "story/chapters/ch-005.md"
        new_target.write_text("appeared\n", encoding="utf-8")
        with self.assertRaisesRegex(drafts.DraftError, "appeared"):
            drafts.plan_accept_draft(
                self.model, "work/drafts/ch-005.md", self.store, "tx-new"
            )
        self.assertTrue(new_draft.exists())

    def test_accept_rejects_unrecoverable_base(self):
        draft_path, _ = self.make_draft()
        revision = documents.parse_document(draft_path.read_bytes()).metadata[
            "base-revision"
        ]
        (self.store.root / "revisions" / revision / "descriptor.json").unlink()

        with self.assertRaisesRegex(drafts.DraftError, "unrecoverable"):
            drafts.plan_accept_draft(
                self.model, "work/drafts/ch-004.md", self.store, "tx-base"
            )

    def test_accept_rejects_hidden_and_malformed_or_unbalanced_ai_tags(self):
        draft_path, _ = self.make_draft()
        cases = (
            ("<hidden>secret</hidden>\n", "hidden"),
            ("secret</hidden>\n", "hidden"),
            ("<hidden secret\n", "hidden"),
            ("<AI>open\n", "unbalanced"),
            ("close</AI>\n", "unbalanced"),
            ("<AI source>bad</AI>\n", "malformed"),
        )
        for body, message in cases:
            with self.subTest(body=body):
                document = documents.parse_document(draft_path.read_bytes())
                draft_path.write_bytes(
                    documents.render_document(
                        documents.Document(
                            dict(document.metadata),
                            body,
                            document.newline,
                            document.bom,
                        )
                    )
                )
                with self.assertRaisesRegex(drafts.DraftError, message):
                    drafts.plan_accept_draft(
                        self.model,
                        "work/drafts/ch-004.md",
                        self.store,
                        "tx-tags",
                    )

    def test_accept_rejects_hidden_material_in_frontmatter(self):
        draft_path, _ = self.make_draft()
        hidden_values = (
            "<hidden>secret</hidden>",
            "<hidden>unclosed",
            "orphan</hidden>",
            "<hidden malformed",
        )
        for value in hidden_values:
            with self.subTest(value=value):
                document = documents.parse_document(draft_path.read_bytes())
                metadata = dict(document.metadata)
                metadata["note"] = value
                draft_path.write_bytes(
                    documents.render_document(
                        documents.Document(
                            metadata,
                            document.body,
                            document.newline,
                            document.bom,
                        )
                    )
                )
                with self.assertRaisesRegex(drafts.DraftError, "hidden"):
                    drafts.plan_accept_draft(
                        self.model,
                        "work/drafts/ch-004.md",
                        self.store,
                        "tx-hidden-metadata",
                    )

    def test_accept_strips_balanced_ai_from_metadata_and_rejects_malformed_metadata(self):
        draft_path, _ = self.make_draft(body="<AI>Body</AI>\n")
        document = documents.parse_document(draft_path.read_bytes())
        metadata = dict(document.metadata)
        metadata["title"] = "<AI>Accepted title</AI>"
        metadata["aliases"] = ["Plain", "<AI>Suggested</AI>"]
        draft_path.write_bytes(
            documents.render_document(
                documents.Document(metadata, document.body, document.newline, document.bom)
            )
        )
        plan = drafts.plan_accept_draft(
            self.model, "work/drafts/ch-004.md", self.store, "tx-ai-metadata"
        )
        accepted_change = next(
            change for change in plan.changes if change.path == "story/chapters/ch-004.md"
        )
        accepted = documents.parse_document(accepted_change.after)
        self.assertEqual("Accepted title", accepted.metadata["title"])
        self.assertEqual(["Plain", "Suggested"], accepted.metadata["aliases"])
        self.assertNotIn(b"<AI", accepted_change.after)

        metadata["title"] = "<AI>broken"
        draft_path.write_bytes(
            documents.render_document(
                documents.Document(metadata, document.body, document.newline, document.bom)
            )
        )
        with self.assertRaisesRegex(drafts.DraftError, "unbalanced"):
            drafts.plan_accept_draft(
                self.model, "work/drafts/ch-004.md", self.store, "tx-bad-ai-metadata"
            )

    def test_archive_ids_are_safe_and_collisions_refuse_overwrite(self):
        self.make_draft()
        for transaction_id in ("", "../escape", "tx.dot", "транзакция", "space id"):
            with self.subTest(transaction_id=transaction_id):
                with self.assertRaisesRegex(drafts.DraftError, "safe ASCII"):
                    drafts.plan_accept_draft(
                        self.model,
                        "work/drafts/ch-004.md",
                        self.store,
                        transaction_id,
                    )

        archive = self.root / "work/archive/ch-004--tx-collision.md"
        archive.write_bytes(b"author archive\n")
        with self.assertRaisesRegex(drafts.DraftError, "already exists"):
            drafts.plan_accept_draft(
                self.model,
                "work/drafts/ch-004.md",
                self.store,
                "tx-collision",
            )
        self.assertEqual(b"author archive\n", archive.read_bytes())

    def test_abandon_archives_updates_work_indexes_and_round_trips_without_story_change(self):
        self.make_draft(status="working", body="<hidden>kept in abandoned work</hidden>\n")
        before = self.managed_files()
        story_before = {
            path: data for path, data in before.items() if path.startswith("story/")
        }

        plan = drafts.plan_abandon_draft(
            self.model, "work/drafts/ch-004.md", "tx-abandon"
        )

        self.assertFalse(any(change.path.startswith("story/") for change in plan.changes))
        self.assertFalse(any(change.path.startswith("kb/") for change in plan.changes))
        archive_change = next(
            change
            for change in plan.changes
            if change.path == "work/archive/ch-004--tx-abandon.md"
        )
        archived = documents.parse_document(archive_change.after)
        self.assertEqual("abandoned", archived.metadata["status"])
        self.assertEqual("tx-abandon", archived.metadata["abandoned-transaction"])
        self.assertNotIn("accepted-transaction", archived.metadata)

        engine = transactions.TransactionEngine(self.model)
        engine.apply(plan, transaction_id="tx-abandon")
        after_story = {
            path: data
            for path, data in self.managed_files().items()
            if path.startswith("story/")
        }
        self.assertEqual(story_before, after_story)
        engine.apply(engine.inverse("tx-abandon"), transaction_id="tx-abandon-undo")
        self.assertEqual(before, self.managed_files())

    def test_abandon_repairs_parseable_inactive_invalid_and_duplicate_drafts(self):
        draft_path, _ = self.make_draft(status="working")
        valid = documents.parse_document(draft_path.read_bytes())
        duplicate = self.root / "work/drafts/duplicate.md"
        duplicate.write_bytes(
            documents.render_document(
                documents.Document(
                    {**valid.metadata, "status": "abandoned"},
                    "Inactive duplicate\n",
                    "\n",
                    False,
                )
            )
        )
        invalid = self.root / "work/drafts/invalid.md"
        invalid.write_bytes(
            b"---\ntarget: ../outside.md\nbase-revision: broken\nstatus: accepted\n---\nKept\n"
        )
        for relative in ("work/drafts/duplicate.md", "work/drafts/invalid.md"):
            with self.subTest(relative=relative):
                plan = drafts.plan_abandon_draft(self.model, relative, "tx-repair")
                self.assertFalse(any(change.path.startswith("story/") for change in plan.changes))
                archive = next(
                    change.after
                    for change in plan.changes
                    if change.path.startswith("work/archive/")
                )
                self.assertEqual(
                    "abandoned", documents.parse_document(archive).metadata["status"]
                )


if __name__ == "__main__":
    unittest.main()
