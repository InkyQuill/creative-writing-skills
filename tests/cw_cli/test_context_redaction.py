import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import app, context, project, scaffold


class ContextSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "project"
        for relative, data in scaffold.render_scaffold("Context", "en").items():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (self.root / ".creative-writing/context").mkdir(parents=True)
        (self.root / ".creative-writing/transactions").mkdir(parents=True)
        self.write("kb/characters/mara.md", "---\ntitle: Mara\n---\nMara.\n")
        self.write("kb/characters/ivo.md", "---\ntitle: Ivo\n---\nIvo.\n")
        self.write(
            "story/chapters/ch-004.md",
            "---\nnumber: 4\n---\nVisible prose.\n<hidden>author-only\nsecret</hidden>\n",
        )
        self.write(
            "kb/continuity/state.md",
            "---\ntitle: State\n---\n# State\n\n"
            "| character | fact |\n|---|---|\n"
            "| mara | knows the gate |\n| ivo | knows the crown |\n",
        )
        self.project = project.discover_project(self.root)

    def write(self, relative: str, text: str) -> Path:
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def plan(self, role: str = "reader") -> context.ContextPlan:
        return context.plan_context(
            self.project, "chapter", "story/chapters/ch-004.md", role
        )

    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        status = app.run(argv, cwd=self.root, stdout=stdout, stderr=stderr)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_reader_removes_only_balanced_hidden_and_preserves_visible_material(self):
        result = context.render_snapshot(self.project, self.plan())
        chapter = result.files["story/chapters/ch-004.md"].decode("utf-8")

        self.assertIn("Visible prose.", chapter)
        self.assertNotIn("author-only", chapter)
        self.assertNotIn("<hidden>", chapter)
        self.assertTrue(result.boundary_warning)
        self.assertEqual([], list((self.root / ".creative-writing/transactions").iterdir()))

    def test_character_filters_recognized_tables_only_and_normalizes_id(self):
        result = context.render_snapshot(self.project, self.plan("character:MARA"))
        state = result.files["kb/continuity/state.md"].decode("utf-8")

        self.assertIn("# State", state)
        self.assertIn("| character | fact |", state)
        self.assertIn("| mara | knows the gate |", state)
        self.assertNotIn("| ivo | knows the crown |", state)

    def test_unrecognized_table_is_preserved_and_does_not_infer_knowledge(self):
        self.write(
            "kb/world/place.md",
            "---\n---\n| person | fact |\n|---|---|\n| ivo | visible |\n",
        )
        plan = context.plan_context(self.project, "kb", "kb/world/place.md", "character:mara")
        result = context.render_snapshot(self.project, plan)
        self.assertIn("| ivo | visible |", result.files["kb/world/place.md"].decode())

    def test_broken_nested_and_crossed_source_tags_fail_before_writing(self):
        for body in (
            "<hidden>broken\n",
            "<hidden>outer <hidden>inner</hidden></hidden>\n",
            "<hidden><AI>x</hidden></AI>\n",
        ):
            with self.subTest(body=body):
                self.write("story/chapters/ch-004.md", f"---\nnumber: 4\n---\n{body}")
                before = tuple((self.root / ".creative-writing/context").iterdir())
                with self.assertRaises(context.ContextSnapshotError):
                    context.render_snapshot(self.project, self.plan())
                self.assertEqual(before, tuple((self.root / ".creative-writing/context").iterdir()))

    def test_malformed_table_and_trusted_role_are_refused(self):
        self.write(
            "story/chapters/ch-004.md",
            "---\nnumber: 4\n---\n| character | fact |\n|---|---|\n| mara | broken | extra |\n",
        )
        with self.assertRaises(context.ContextSnapshotError):
            context.render_snapshot(self.project, self.plan("character:mara"))
        with self.assertRaisesRegex(context.ContextSnapshotError, "trusted"):
            context.render_snapshot(self.project, self.plan("trusted"))

    def test_manifest_id_order_and_hashes_are_stable_and_sources_are_immutable(self):
        source_before = {
            path: (self.root / path).read_bytes()
            for path in self.plan().required + self.plan().suggested
        }
        first = context.render_snapshot(self.project, self.plan())
        second = context.render_snapshot(self.project, self.plan())

        self.assertEqual(first.snapshot_id, second.snapshot_id)
        self.assertEqual(first.manifest, second.manifest)
        self.assertEqual(source_before, {path: (self.root / path).read_bytes() for path in source_before})
        self.assertEqual(list(source_before), [item["path"] for item in first.manifest["sources"]])
        for item in first.manifest["sources"]:
            raw = source_before[item["path"]]
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item["exact_hash"])
            self.assertEqual(
                hashlib.sha256(first.files[item["path"]]).hexdigest(),
                item["snapshot_exact_hash"],
            )

    def test_status_reports_stale_corrupt_missing_and_symlink_without_check_all(self):
        result = context.render_snapshot(self.project, self.plan())
        self.write("story/chapters/ch-004.md", "---\nnumber: 4\n---\nChanged.\n")
        findings = context.snapshot_status(self.project)
        self.assertIn("CW-CONTEXT-STALE", {item.code for item in findings})

        manifest = self.root / result.directory / "manifest.json"
        manifest.write_text("{broken", encoding="utf-8")
        self.assertIn("CW-CONTEXT-CORRUPT", {item.code for item in context.snapshot_status(self.project)})

        status, output, error = self.run_cli(["check", "all", "--format", "json"])
        self.assertIn(status, {0, 1})
        self.assertEqual("", error)
        self.assertNotIn("context", json.loads(output)["checks"])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_status_does_not_follow_symlink_snapshot_or_source(self):
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        (outside / "manifest.json").write_text("{}", encoding="utf-8")
        (self.root / ".creative-writing/context/link").symlink_to(outside, target_is_directory=True)
        self.assertIn("CW-CONTEXT-UNSAFE", {item.code for item in context.snapshot_status(self.project)})

    def test_atomic_install_failure_leaves_no_partial_or_temporary_snapshot(self):
        with mock.patch("cwcli.context.os.rename", side_effect=OSError("injected")):
            with self.assertRaisesRegex(OSError, "injected"):
                context.render_snapshot(self.project, self.plan())
        self.assertEqual([], list((self.root / ".creative-writing/context").iterdir()))

    def test_cli_snapshot_and_cleanup_preview_apply_are_derived_only(self):
        status, output, error = self.run_cli(
            ["context", "chapter", "story/chapters/ch-004.md", "--as", "reader", "--snapshot", "--format", "json"]
        )
        self.assertEqual((0, ""), (status, error))
        payload = json.loads(output)
        self.assertEqual("created", payload["snapshot"]["status"])
        snapshot_dir = self.root / payload["snapshot"]["directory"]
        self.assertTrue(snapshot_dir.is_dir())
        self.assertEqual([], list((self.root / ".creative-writing/transactions").iterdir()))

        status, output, error = self.run_cli(["clean-context", "--format", "json"])
        self.assertEqual((0, ""), (status, error))
        preview = json.loads(output)
        self.assertEqual("preview", preview["status"])
        self.assertTrue(snapshot_dir.exists())

        status, output, error = self.run_cli(["clean-context", "--apply", "--format", "json"])
        self.assertEqual((0, ""), (status, error))
        self.assertEqual("applied", json.loads(output)["status"])
        self.assertFalse(snapshot_dir.exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_cleanup_refuses_symlink_and_unknown_entries_without_removing_anything(self):
        result = context.render_snapshot(self.project, self.plan())
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        (outside / "keep").write_text("keep", encoding="utf-8")
        (self.root / ".creative-writing/context/escape").symlink_to(outside, target_is_directory=True)

        status, _output, error = self.run_cli(["clean-context", "--apply"])
        self.assertEqual(2, status)
        self.assertIn("unsafe", error)
        self.assertTrue((self.root / result.directory).exists())
        self.assertEqual("keep", (outside / "keep").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
