import tempfile
import unittest
from pathlib import Path

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import documents, drafts, rebase, project, scaffold, transactions


class ThreeWayRebaseTests(unittest.TestCase):
    def test_disjoint_edits_merge_in_base_coordinates(self):
        result = rebase.three_way_rebase(
            "one\ntwo\nthree\n", "one\nTWO\nthree\n", "one\ntwo\nTHREE\n"
        )
        self.assertEqual((), result.conflicts)
        self.assertEqual("one\nTWO\nTHREE\n", result.text)

    def test_same_span_and_same_boundary_insertions_conflict(self):
        span = rebase.three_way_rebase(
            "one\ntwo\n", "one\nDRAFT\n", "one\nAUTHOR\n"
        )
        insertion = rebase.three_way_rebase(
            "one\ntwo\n", "one\ndraft\ntwo\n", "one\nauthor\ntwo\n"
        )
        for result in (span, insertion):
            self.assertIsNone(result.text)
            self.assertEqual(1, len(result.conflicts))
            self.assertTrue(result.conflicts[0].draft)
            self.assertTrue(result.conflicts[0].current)

    def test_identical_edits_and_both_fast_paths_are_clean(self):
        identical = rebase.three_way_rebase(
            "one\ntwo\n", "ONE\ntwo\n", "ONE\ntwo\n"
        )
        self.assertEqual("ONE\ntwo\n", identical.text)
        self.assertEqual((), identical.conflicts)

        self.assertEqual(
            "one\nDRAFT\n",
            rebase.three_way_rebase(
                "one\ntwo\n", "one\nDRAFT\n", "one\ntwo\n"
            ).text,
        )
        self.assertEqual(
            "one\nCURRENT\n",
            rebase.three_way_rebase(
                "one\ntwo\n", "one\ntwo\n", "one\nCURRENT\n"
            ).text,
        )

    def test_scans_all_conflicts_and_preserves_russian_text(self):
        result = rebase.three_way_rebase(
            "Раз\nДва\nТри\nЧетыре\n",
            "РАЗ\nДва\nТРИ\nЧетыре\n",
            "Первый\nДва\nТретий\nЧетыре\n",
        )
        self.assertIsNone(result.text)
        self.assertEqual(2, len(result.conflicts))
        self.assertEqual(("Раз\n",), result.conflicts[0].base)
        self.assertEqual(("Три\n",), result.conflicts[1].base)

    def test_logical_newline_normalization_uses_draft_style(self):
        result = rebase.three_way_rebase(
            "one\r\ntwo\r\nthree\r\n",
            "one\r\nTWO\r\nthree\r\n",
            "one\ntwo\nTHREE\n",
        )
        self.assertEqual((), result.conflicts)
        self.assertEqual("one\r\nTWO\r\nTHREE\r\n", result.text)


class DraftRebasePlanTests(unittest.TestCase):
    def make_project(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name) / "story-project"
        for relative, data in scaffold.render_scaffold("Rebase Test", "ru").items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        model = project.discover_project(root)
        return root, model, transactions.TransactionStore(model)

    def make_draft(self, base: bytes, draft_body: str):
        root, model, store = self.make_project()
        target = root / "story/chapters/ch-001.md"
        target.write_bytes(base)
        creation = drafts.plan_create_draft(
            model, "story/chapters/ch-001.md", None, store
        )
        draft_path = root / creation.changes[0].path
        created = documents.parse_document(creation.changes[0].after)
        metadata = dict(created.metadata)
        draft_path.write_bytes(
            documents.render_document(
                documents.Document(
                    metadata=metadata,
                    body=draft_body,
                    newline=created.newline,
                    bom=created.bom,
                )
            )
        )
        return root, model, store, target, draft_path

    def test_clean_plan_changes_only_draft_and_is_transaction_ready(self):
        base = b"---\nnumber: 1\ntitle: Harbor\n---\none\ntwo\nthree\n"
        root, model, store, target, draft_path = self.make_draft(
            base, "one\nTWO\nthree\n"
        )
        target.write_bytes(
            b"---\nnumber: 1\ntitle: Harbor revised\n---\none\ntwo\nTHREE\n"
        )
        before_draft = draft_path.read_bytes()

        plan = drafts.plan_rebase_draft(model, "work/drafts/ch-001.md", store)

        self.assertEqual(("draft", "rebase", "work/drafts/ch-001.md"), plan.command)
        self.assertEqual(1, len(plan.changes))
        self.assertEqual("work/drafts/ch-001.md", plan.changes[0].path)
        self.assertEqual(before_draft, plan.changes[0].before)
        rebased = documents.parse_document(plan.changes[0].after)
        current_revision = documents.logical_hash(target.read_bytes())
        self.assertEqual(current_revision, rebased.metadata["base-revision"])
        self.assertEqual("working", rebased.metadata["status"])
        self.assertEqual("Harbor", rebased.metadata["title"])
        self.assertEqual("one\nTWO\nTHREE\n", rebased.body)
        self.assertEqual(target.read_bytes(), store.load_revision(current_revision))
        self.assertEqual(before_draft, draft_path.read_bytes())

        engine = transactions.TransactionEngine(model)
        engine.preview(plan)
        record = engine.apply(plan, transaction_id="draft-rebase")
        self.assertEqual("committed", record.state)
        self.assertEqual(plan.changes[0].after, draft_path.read_bytes())

    def test_current_equal_base_returns_noop_without_rewriting_draft(self):
        base = b"---\r\nnumber: 1\r\ntitle: Harbor\r\n---\r\none\r\ntwo\r\n"
        _root, model, store, _target, draft_path = self.make_draft(
            base, "one\r\nTWO\r\n"
        )
        before = draft_path.read_bytes()
        plan = drafts.plan_rebase_draft(model, "work/drafts/ch-001.md", store)
        self.assertEqual((), plan.changes)
        self.assertEqual(before, draft_path.read_bytes())

    def test_draft_equal_base_adopts_current_body_and_preserves_draft_newlines(self):
        base = b"---\r\nnumber: 1\r\ntitle: Harbor\r\n---\r\none\r\ntwo\r\n"
        _root, model, store, target, _draft_path = self.make_draft(
            base, "one\r\ntwo\r\n"
        )
        target.write_bytes(
            b"---\ntitle: Changed\nnumber: 1\n---\none\nCURRENT\n"
        )
        plan = drafts.plan_rebase_draft(model, "work/drafts/ch-001.md", store)
        rebased = documents.parse_document(plan.changes[0].after)
        self.assertEqual("one\r\nCURRENT\r\n", rebased.body)
        self.assertEqual("Harbor", rebased.metadata["title"])

    def test_bare_cr_frontmatter_and_body_support_disjoint_rebase(self):
        base = b"---\rnumber: 1\rtitle: Harbor\r---\rone\rtwo\rthree\r"
        _root, model, store, target, _draft_path = self.make_draft(
            base, "one\rTWO\rthree\r"
        )
        target.write_bytes(
            b"---\rnumber: 1\rtitle: Changed\r---\rone\rtwo\rTHREE\r"
        )

        plan = drafts.plan_rebase_draft(model, "work/drafts/ch-001.md", store)

        rebased = documents.parse_document(plan.changes[0].after)
        self.assertEqual("\r", rebased.newline)
        self.assertEqual("one\rTWO\rTHREE\r", rebased.body)
        self.assertEqual("working", rebased.metadata["status"])

    def test_rebase_replaces_only_quoted_tab_spaced_revision_scalar(self):
        base = b"---\nnumber: 1\ntitle: Harbor\n---\none\ntwo\nthree\n"
        _root, model, store, target, draft_path = self.make_draft(
            base, "one\nTWO\nthree\n"
        )
        old_revision = documents.logical_hash(base)
        raw_field = b'base-revision:\t  "' + old_revision.encode("ascii") + b'"\t'
        draft_source = draft_path.read_bytes().replace(
            b"base-revision: " + old_revision.encode("ascii"), raw_field
        )
        draft_path.write_bytes(draft_source)
        target.write_bytes(
            b"---\nnumber: 1\ntitle: Changed\n---\none\ntwo\nTHREE\n"
        )
        new_revision = documents.logical_hash(target.read_bytes())

        plan = drafts.plan_rebase_draft(model, "work/drafts/ch-001.md", store)

        expected_field = (
            b'base-revision:\t  "' + new_revision.encode("ascii") + b'"\t'
        )
        after = plan.changes[0].after
        self.assertIn(expected_field + b"\n", after)
        self.assertEqual(
            draft_source.replace(raw_field, expected_field).replace(
                b"one\nTWO\nthree\n", b"one\nTWO\nTHREE\n"
            ),
            after,
        )

    def test_raw_revision_replacement_preserves_comment_suffix_and_line_ending(self):
        old_revision = b"1" * 64
        new_revision = "2" * 64
        prefix = b"---\rbase-revision:  '" + old_revision + b"' \t# retained\r---\r"

        rendered = drafts._replace_base_revision_value(prefix, new_revision)

        self.assertEqual(
            b"---\rbase-revision:  '" + new_revision.encode("ascii") + b"' \t# retained\r---\r",
            rendered,
        )

    def test_conflict_reports_fragments_and_writes_nothing(self):
        base = b"---\nnumber: 1\n---\none\ntwo\n"
        root, model, store, target, draft_path = self.make_draft(
            base, "one\nDRAFT\n"
        )
        target.write_bytes(b"---\nnumber: 1\n---\none\nAUTHOR\n")
        before = {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }
        before_draft = draft_path.read_bytes()

        with self.assertRaises(drafts.DraftConflict) as raised:
            drafts.plan_rebase_draft(model, "work/drafts/ch-001.md", store)

        self.assertEqual(("two\n",), raised.exception.conflicts[0].base)
        self.assertEqual(("DRAFT\n",), raised.exception.conflicts[0].draft)
        self.assertEqual(("AUTHOR\n",), raised.exception.conflicts[0].current)
        after = {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(before, after)
        self.assertEqual(before_draft, draft_path.read_bytes())

    def test_missing_and_corrupt_base_are_actionable_and_non_mutating(self):
        base = b"---\nnumber: 1\n---\none\n"
        root, model, store, target, draft_path = self.make_draft(base, "ONE\n")
        target.write_bytes(b"---\nnumber: 1\n---\nCURRENT\n")
        revision = documents.parse_document(draft_path.read_bytes()).metadata[
            "base-revision"
        ]
        revision_root = store.root / "revisions" / revision

        for corruption in ("missing", "corrupt"):
            with self.subTest(corruption=corruption):
                if corruption == "missing":
                    descriptor = revision_root / "descriptor.json"
                    held = descriptor.read_bytes()
                    descriptor.unlink()
                else:
                    descriptor = revision_root / "descriptor.json"
                    descriptor.write_text("{}\n", encoding="utf-8")
                before_draft = draft_path.read_bytes()
                before_target = target.read_bytes()
                with self.assertRaisesRegex(drafts.DraftError, "recoverable rebase inputs"):
                    drafts.plan_rebase_draft(model, "work/drafts/ch-001.md", store)
                self.assertEqual(before_draft, draft_path.read_bytes())
                self.assertEqual(before_target, target.read_bytes())
                descriptor.write_bytes(held)


if __name__ == "__main__":
    unittest.main()
