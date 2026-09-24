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
from cwcli import context


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

    def write_layout(self, roles):
        (self.root / ".cws-layout.json").write_text(
            json.dumps({"version": 1, "roles": roles}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

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
        self.write_layout({"chapters": "manuscript/book-one"})
        self.assertEqual("manuscript/book-one", resolve_role(discover_project(self.root), "chapters"))
        self.assertFalse((self.root / "manuscript").exists())

    def test_get_folder_returns_saved_relative_path_without_creating_it(self):
        self.write_layout({"characters": "notes/people"})
        output, errors = io.StringIO(), io.StringIO()
        status = app.run(["get-folder", "characters"], cwd=self.root, stdout=output, stderr=errors)
        self.assertEqual(0, status, errors.getvalue())
        self.assertEqual("notes/people\n", output.getvalue())
        self.assertFalse((self.root / "notes").exists())

    def test_get_folder_json_uses_detected_legacy_folder(self):
        (self.root / "characters").mkdir()
        (self.root / "characters/mara.md").write_text("# Mara\n")
        output, errors = io.StringIO(), io.StringIO()
        status = app.run(["get-folder", "characters", "--format", "json"], cwd=self.root, stdout=output, stderr=errors)
        self.assertEqual(0, status, errors.getvalue())
        self.assertEqual({"role": "characters", "path": "characters"}, json.loads(output.getvalue()))

    def test_get_folder_rejects_unsafe_saved_path(self):
        self.write_layout({"characters": "../outside"})
        output, errors = io.StringIO(), io.StringIO()
        status = app.run(["get-folder", "characters", "--format", "json"], cwd=self.root, stdout=output, stderr=errors)
        self.assertEqual(2, status)
        self.assertIn("project-relative", json.loads(output.getvalue())["message"])

    def test_get_folder_reports_ambiguous_role_without_guessing(self):
        for relative in ("chapters", "story/chapters"):
            directory = self.root / relative
            directory.mkdir(parents=True)
            (directory / "one.md").write_text("# One\n")
        output, errors = io.StringIO(), io.StringIO()
        status = app.run(["get-folder", "chapters", "--format", "json"], cwd=self.root, stdout=output, stderr=errors)
        self.assertEqual(2, status)
        self.assertIn("multiple populated folders", json.loads(output.getvalue())["message"])

    def test_typography_fix_accepts_selected_manuscript_folder(self):
        self.write_layout({"chapters": "manuscript"})
        (self.root / "manuscript").mkdir()
        (self.root / "manuscript/one.md").write_text("И в школе.\n", encoding="utf-8")
        output, errors = io.StringIO(), io.StringIO()
        status = app.run(
            ["fix-prose-typography", "manuscript/one.md", "--format", "json"],
            cwd=self.root, stdout=output, stderr=errors,
        )
        self.assertEqual(0, status, errors.getvalue() + output.getvalue())
        self.assertIn("manuscript/one.md", output.getvalue())

    def test_layout_choice_is_previewed_then_saved_separately(self):
        output, errors = io.StringIO(), io.StringIO()
        args = ["layout", "--set", "chapters=manuscript/book-one", "--format", "json"]
        self.assertEqual(0, app.run(args, cwd=self.root, stdout=output, stderr=errors))
        self.assertFalse((self.root / ".cws-layout.json").exists())
        self.assertEqual(0, app.run(args + ["--apply"], cwd=self.root, stdout=io.StringIO(), stderr=errors), errors.getvalue())
        self.assertEqual("manuscript/book-one", resolve_role(discover_project(self.root), "chapters"))
        self.assertNotIn("role-chapters", (self.root / "project.md").read_text())

    def test_capture_saves_only_unambiguous_existing_folders(self):
        (self.root / "chapters").mkdir()
        (self.root / "chapters/one.md").write_text("# One\n")
        for relative in ("work/drafts", "drafts"):
            directory = self.root / relative
            directory.mkdir(parents=True)
            (directory / "one.md").write_text("# One\n")
        output, errors = io.StringIO(), io.StringIO()
        self.assertEqual(0, app.run(["layout", "--capture", "--apply"], cwd=self.root, stdout=output, stderr=errors), errors.getvalue())
        roles = json.loads((self.root / ".cws-layout.json").read_text())["roles"]
        self.assertEqual({"chapters": "chapters"}, roles)

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

    def test_reindex_updates_existing_index_in_selected_folder(self):
        self.write_layout({"chapters": "manuscript"})
        directory = self.root / "manuscript"
        directory.mkdir()
        (directory / "one.md").write_text("---\nnumber: 1\nstatus: accepted\n---\n# One\n")
        (directory / "_index.md").write_text("---\ngenerated: true\n---\n# Old\n")
        output, errors = io.StringIO(), io.StringIO()
        status = app.run(["reindex", "--apply", "--format", "json"], cwd=self.root, stdout=output, stderr=errors)
        self.assertEqual(0, status, errors.getvalue() + output.getvalue())
        self.assertIn("manuscript/one.md", (directory / "_index.md").read_text())
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
        self.write_layout({"chapters": "chapters", "drafts": "notes/drafts"})
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
        self.write_layout({"chapters": "chapters", "drafts": "notes/drafts", "archive": "notes/archive"})
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

    def test_accept_updates_existing_index_in_selected_chapters_folder(self):
        self.write_layout({"chapters": "manuscript", "drafts": "working", "archive": "old"})
        (self.root / "manuscript").mkdir()
        (self.root / "working").mkdir()
        (self.root / "manuscript/_index.md").write_text("---\ngenerated: true\n---\n# Chapters\n")
        (self.root / "working/new.md").write_bytes(documents.render_document(documents.Document(
            metadata={"target": "manuscript/new.md", "status": "ready", "number": 1},
            body="Новая глава.\n", newline="\n", bom=False,
        )))
        model = discover_project(self.root)
        engine = transactions.TransactionEngine(model)
        plan = drafts.plan_accept_draft(model, "working/new.md", engine.store, "tx-index")
        self.assertIn("manuscript/_index.md", {change.path for change in plan.changes})
        engine.apply(plan, transaction_id="tx-index")
        self.assertIn("manuscript/new.md", (self.root / "manuscript/_index.md").read_text())

    def test_context_reads_neighboring_flat_chapters(self):
        (self.root / "chapters").mkdir()
        for number in (1, 2):
            (self.root / f"chapters/{number}.md").write_text(
                f"---\nnumber: {number}\n---\nChapter {number}.\n", encoding="utf-8",
            )

        packet = context.plan_context(discover_project(self.root), "chapter", "chapters/2.md", "trusted")

        self.assertIn("chapters/2.md", packet.required)
        self.assertIn("chapters/1.md", (*packet.required, *packet.suggested))

    def test_context_uses_selected_plans_and_characters_folders(self):
        self.write_layout({"chapters": "manuscript", "plans": "notes/outlines", "characters": "notes/people"})
        for directory in ("manuscript", "notes/outlines", "notes/people"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / "manuscript/one.md").write_text("---\nnumber: 1\n---\n# One\n")
        (self.root / "notes/outlines/one.md").write_text(
            "---\nstatus: active\nrelated: manuscript/one.md\n---\n# Plan\n"
        )
        (self.root / "notes/people/mara.md").write_text("---\ntitle: Mara\n---\n# Mara\n")
        packet = context.plan_context(discover_project(self.root), "chapter", "manuscript/one.md", "character:mara")
        self.assertIn("notes/outlines/one.md", packet.suggested)
        self.assertNotIn("character:mara", packet.unresolved)

    def test_snapshot_status_accepts_selected_chapter_folder(self):
        self.write_layout({"chapters": "manuscript"})
        (self.root / "manuscript").mkdir()
        (self.root / "manuscript/one.md").write_text("---\nnumber: 1\n---\n# One\n")
        output, errors = io.StringIO(), io.StringIO()
        status = app.run(
            ["context", "chapter", "manuscript/one.md", "--as", "reader", "--snapshot", "--format", "json"],
            cwd=self.root, stdout=output, stderr=errors,
        )
        self.assertEqual(0, status, errors.getvalue() + output.getvalue())
        findings = context.snapshot_status(discover_project(self.root))
        self.assertEqual([], findings)

    def test_init_defaults_to_compact_tree_with_optional_full_template(self):
        for template, expected_index in (("compact", False), ("full", True)):
            with self.subTest(template=template):
                root = self.root / template
                output, errors = io.StringIO(), io.StringIO()
                argv = ["init", str(root), "--title", "New", "--language", "ru", "--apply", "--format", "json"]
                if template == "full":
                    argv.extend(("--template", "full"))
                status = app.run(argv, cwd=self.root, stdout=output, stderr=errors)
                self.assertEqual(0, status, errors.getvalue() + output.getvalue())
                self.assertTrue((root / "project.md").is_file())
                if template == "compact":
                    self.assertTrue((root / ".cws-layout.json").is_file())
                    self.assertFalse((root / "story/chapters").exists())
                else:
                    self.assertTrue((root / "story/chapters").is_dir())
                self.assertEqual(expected_index, (root / "story/chapters/_index.md").exists())
                self.assertEqual(expected_index, (root / "kb/issues").exists())


if __name__ == "__main__":
    unittest.main()
