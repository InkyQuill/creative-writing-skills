import io
import json
import tempfile
import unittest
from pathlib import Path

from tests.cw_cli import helpers  # noqa: F401
from cwcli import app
from cwcli.layout import LayoutAmbiguity, resolve_role
from cwcli.project import discover_project
from cwcli import drafts, documents, transactions


class LayoutDiscoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "project.md").write_text(
            "---\nschema-version: 1\ntitle: Story\nlanguage: ru\nstatus: drafting\n---\n",
            encoding="utf-8",
        )

    def layout(self):
        output, errors = io.StringIO(), io.StringIO()
        status = app.run(["layout", "--format", "json"], cwd=self.root, stdout=output, stderr=errors)
        self.assertEqual(0, status, errors.getvalue())
        return json.loads(output.getvalue())

    def test_flat_chapters_are_detected_without_creating_canonical_tree(self):
        (self.root / "chapters").mkdir()
        (self.root / "chapters/first.md").write_text("# First\n", encoding="utf-8")
        before = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))

        result = self.layout()

        self.assertEqual(["chapters"], result["roles"]["chapters"]["candidates"])
        self.assertEqual("chapters", result["roles"]["chapters"]["selected"])
        self.assertEqual(before, sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*")))

    def test_two_populated_chapter_locations_are_reported_as_ambiguous(self):
        for directory in ("chapters", "story/chapters"):
            target = self.root / directory
            target.mkdir(parents=True)
            (target / "one.md").write_text("# One\n", encoding="utf-8")

        result = self.layout()

        self.assertEqual(["chapters", "story/chapters"], result["roles"]["chapters"]["candidates"])
        self.assertIsNone(result["roles"]["chapters"]["selected"])
        self.assertIn("chapters", result["ambiguous_roles"])

    def test_linked_or_nested_project_folders_are_not_scanned(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "one.md").write_text("# One\n", encoding="utf-8")
        (self.root / "chapters").symlink_to(outside, target_is_directory=True)
        nested = self.root / "story/chapters"
        nested.mkdir(parents=True)
        (nested / "project.md").write_text("# Nested\n", encoding="utf-8")
        (nested / "two.md").write_text("# Two\n", encoding="utf-8")

        result = self.layout()

        self.assertEqual([], result["roles"]["chapters"]["candidates"])

    def test_explicit_role_path_wins_without_moving_content(self):
        (self.root / "project.md").write_text(
            "---\nschema-version: 1\ntitle: Story\nlanguage: ru\nstatus: drafting\nrole-chapters: manuscript/book-one\n---\n",
            encoding="utf-8",
        )
        self.assertEqual("manuscript/book-one", resolve_role(discover_project(self.root), "chapters"))
        self.assertFalse((self.root / "manuscript").exists())

    def test_ambiguous_populated_role_needs_explicit_choice(self):
        for directory in ("chapters", "story/chapters"):
            target = self.root / directory
            target.mkdir(parents=True)
            (target / "one.md").write_text("# One\n", encoding="utf-8")
        with self.assertRaises(LayoutAmbiguity):
            resolve_role(discover_project(self.root), "chapters")

    def test_prose_check_reads_flat_chapters(self):
        target = self.root / "chapters"
        target.mkdir()
        (target / "one.md").write_text("Он шёл в школу.\n", encoding="utf-8")
        output, errors = io.StringIO(), io.StringIO()

        status = app.run(["check", "prose", ".", "--format", "json"], cwd=self.root, stdout=output, stderr=errors)

        self.assertEqual(0, status, errors.getvalue())
        matches = [item for item in json.loads(output.getvalue())["findings"] if item["path"] == "chapters/one.md"]
        self.assertIn("CW-PROSE-103", [item["code"] for item in matches])

    def test_flat_chapters_do_not_trigger_parallel_tree_warnings(self):
        target = self.root / "chapters"
        target.mkdir()
        (target / "one.md").write_text(
            "---\ntype: chapter\nnumber: 1\nstatus: accepted\n---\n# One\n",
            encoding="utf-8",
        )
        output, errors = io.StringIO(), io.StringIO()
        status = app.run(["check", "structure", ".", "--format", "json"], cwd=self.root, stdout=output, stderr=errors)
        self.assertEqual(0, status, errors.getvalue())
        findings = json.loads(output.getvalue())["findings"]
        self.assertNotIn("story/chapters", [item["path"] for item in findings])
        self.assertNotIn("chapters/one.md", [item["path"] for item in findings if item["code"] == "CW-STRUCT-060"])

    def test_reindex_in_flat_project_does_not_create_canonical_folders(self):
        target = self.root / "chapters"
        target.mkdir()
        (target / "one.md").write_text("# One\n", encoding="utf-8")
        output, errors = io.StringIO(), io.StringIO()

        status = app.run(["reindex", "--format", "json"], cwd=self.root, stdout=output, stderr=errors)

        self.assertEqual(0, status, errors.getvalue())
        changes = json.loads(output.getvalue()).get("changes", [])
        self.assertFalse(any("story/chapters" in json.dumps(change) for change in changes))
        self.assertFalse((self.root / "story").exists())

    def test_draft_can_target_detected_flat_chapter_path(self):
        (self.root / "chapters").mkdir()
        (self.root / "chapters/existing.md").write_text("# Existing\n", encoding="utf-8")
        output, errors = io.StringIO(), io.StringIO()

        status = app.run(
            ["draft", "create", "chapters/next.md", "--format", "json"],
            cwd=self.root, stdout=output, stderr=errors,
        )

        self.assertEqual(0, status, errors.getvalue())
        self.assertIn("work/drafts/next.md", json.dumps(json.loads(output.getvalue())))
        self.assertFalse((self.root / "story").exists())

    def test_draft_uses_explicit_draft_folder_without_default_work_tree(self):
        (self.root / "project.md").write_text(
            "---\nschema-version: 1\ntitle: Story\nlanguage: ru\nstatus: drafting\nrole-chapters: chapters\nrole-drafts: notes/drafts\n---\n",
            encoding="utf-8",
        )
        output, errors = io.StringIO(), io.StringIO()
        status = app.run(
            ["draft", "create", "chapters/next.md", "--format", "json"],
            cwd=self.root, stdout=output, stderr=errors,
        )
        self.assertEqual(0, status, errors.getvalue())
        self.assertIn("notes/drafts/next.md", json.dumps(json.loads(output.getvalue())))
        self.assertFalse((self.root / "work").exists())

        applied_out, errors = io.StringIO(), io.StringIO()
        self.assertEqual(0, app.run(
            ["draft", "create", "chapters/next.md", "--apply", "--format", "json"],
            cwd=self.root, stdout=applied_out, stderr=errors,
        ), errors.getvalue() + applied_out.getvalue())
        check_out, errors = io.StringIO(), io.StringIO()
        self.assertEqual(0, app.run(
            ["check", "drafts", ".", "--format", "json"],
            cwd=self.root, stdout=check_out, stderr=errors,
        ), errors.getvalue())
        findings = json.loads(check_out.getvalue())["findings"]
        self.assertTrue(any(item["path"] == "notes/drafts/next.md" for item in findings))
        self.assertNotIn("CW-DRAFT-020", [item["code"] for item in findings])

    def test_accept_from_flat_layout_does_not_plan_parallel_indexes(self):
        (self.root / "project.md").write_text(
            "---\nschema-version: 1\ntitle: Story\nlanguage: ru\nstatus: drafting\nrole-chapters: chapters\nrole-drafts: notes/drafts\nrole-archive: notes/archive\n---\n",
            encoding="utf-8",
        )
        (self.root / "chapters").mkdir()
        draft_folder = self.root / "notes/drafts"
        draft_folder.mkdir(parents=True)
        (draft_folder / "next.md").write_bytes(documents.render_document(documents.Document(
            metadata={"target": "chapters/next.md", "status": "ready", "number": 1},
            body="Новая глава.\n", newline="\n", bom=False,
        )))
        model = discover_project(self.root)
        store = transactions.TransactionStore(model)

        plan = drafts.plan_accept_draft(model, "notes/drafts/next.md", store, "tx-flat")

        changed = {change.path for change in plan.changes}
        self.assertIn("chapters/next.md", changed)
        self.assertIn("notes/archive/next--tx-flat.md", changed)
        self.assertFalse(any(path.startswith("story/") for path in changed))
        engine = transactions.TransactionEngine(model)
        record = engine.apply(plan, transaction_id="tx-flat")
        self.assertEqual("committed", record.state)
        self.assertTrue((self.root / "chapters/next.md").exists())
        self.assertTrue((self.root / "notes/archive/next--tx-flat.md").exists())
        inverse = engine.inverse("tx-flat")
        engine.apply(inverse)
        self.assertFalse((self.root / "chapters/next.md").exists())
        self.assertTrue((self.root / "notes/drafts/next.md").exists())


if __name__ == "__main__":
    unittest.main()
