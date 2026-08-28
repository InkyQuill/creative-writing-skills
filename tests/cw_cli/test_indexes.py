import io
import json
import tempfile
import unittest
from pathlib import Path

from .helpers import app
from cwcli import indexes, project, scaffold


def make_project(root: Path) -> project.Project:
    for relative_id, data in scaffold.render_scaffold("Index Test", "en").items():
        target = root / relative_id
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (root / ".creative-writing/context").mkdir(parents=True)
    (root / ".creative-writing/transactions").mkdir(parents=True)
    return project.discover_project(root)


class IndexTests(unittest.TestCase):
    def test_new_scaffold_is_already_a_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            story = make_project(Path(directory))

            plan = indexes.plan_reindex(story)

            self.assertEqual((), plan.changes)
            self.assertEqual(("reindex",), plan.command)

    def test_indexes_are_sorted_and_include_type_specific_frontmatter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = make_project(root)
            (root / "story/chapters/zeta.md").write_text(
                "---\nnumber: 2\ntitle: Zeta\n---\n# Zeta\n", encoding="utf-8"
            )
            (root / "story/chapters/alpha.md").write_text(
                "---\nnumber: 1\ntitle: Alpha\n---\n# Alpha\n", encoding="utf-8"
            )

            plan = indexes.plan_reindex(story)
            chapter_index = next(
                change.after for change in plan.changes if change.path == "story/chapters/_index.md"
            )

            assert chapter_index is not None
            rendered = chapter_index.decode("utf-8")
            self.assertLess(rendered.index("alpha.md"), rendered.index("zeta.md"))
            self.assertIn('number=1; title="Alpha"', rendered)

    def test_archived_and_unmanaged_documents_are_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = make_project(root)
            (root / "work/drafts/active.md").write_text(
                "---\nstatus: working\ntitle: Active\n---\n", encoding="utf-8"
            )
            (root / "work/drafts/hidden.md").write_text(
                "---\nstatus: archived\ntitle: Hidden\n---\n", encoding="utf-8"
            )
            (root / "work/archive/old.md").write_text("---\ntitle: Old\n---\n", encoding="utf-8")
            (root / "work/unmanaged.md").write_text("---\ntitle: Unmanaged\n---\n", encoding="utf-8")

            plan = indexes.plan_reindex(story)
            work_index = next(change.after for change in plan.changes if change.path == "work/_index.md")

            assert work_index is not None
            rendered = work_index.decode("utf-8")
            self.assertIn("work/drafts/active.md", rendered)
            self.assertNotIn("hidden.md", rendered)
            self.assertNotIn("old.md", rendered)
            self.assertNotIn("unmanaged.md", rendered)

    def test_reindex_cli_previews_then_applies_transaction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            (root / "kb/characters/aria.md").write_text(
                "---\ntitle: Aria\nclass: person\n---\n", encoding="utf-8"
            )
            before = (root / "kb/characters/_index.md").read_bytes()

            preview = io.StringIO()
            status = app.run(
                ["reindex", "--format", "json"], cwd=root, stdout=preview, stderr=io.StringIO()
            )
            self.assertEqual(0, status)
            self.assertEqual("preview", json.loads(preview.getvalue())["status"])
            self.assertEqual(before, (root / "kb/characters/_index.md").read_bytes())

            applied = io.StringIO()
            status = app.run(
                ["reindex", "--apply", "--format", "json"],
                cwd=root,
                stdout=applied,
                stderr=io.StringIO(),
            )
            self.assertEqual(0, status)
            self.assertEqual("committed", json.loads(applied.getvalue())["status"])
            self.assertIn("kb/characters/aria.md", (root / "kb/characters/_index.md").read_text())

    def test_reindex_preserves_existing_crlf_convention(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = make_project(root)
            index_path = root / "story/chapters/_index.md"
            index_path.write_bytes(index_path.read_bytes().replace(b"\n", b"\r\n"))
            (root / "story/chapters/one.md").write_text(
                "---\nnumber: 1\ntitle: One\n---\n", encoding="utf-8"
            )

            change = next(
                change
                for change in indexes.plan_reindex(story).changes
                if change.path == "story/chapters/_index.md"
            )

            assert change.after is not None
            self.assertIn(b"story/chapters/one.md", change.after)
            self.assertNotIn(b"\n", change.after.replace(b"\r\n", b""))

    def test_reindex_can_repair_malformed_index_without_losing_its_newlines(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = make_project(root)
            index_path = root / "story/chapters/_index.md"
            index_path.write_bytes(b"---\r\ngenerated: [unsupported]\r\n---\r\nstale\r\n")

            change = next(
                change
                for change in indexes.plan_reindex(story).changes
                if change.path == "story/chapters/_index.md"
            )

            assert change.after is not None
            self.assertIn(b"generated: true\r\n", change.after)
            self.assertNotIn(b"\n", change.after.replace(b"\r\n", b""))


if __name__ == "__main__":
    unittest.main()
