import io
import json
import tempfile
import unittest
from pathlib import Path

from tests.cw_cli import helpers  # noqa: F401
from cwcli import app


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


if __name__ == "__main__":
    unittest.main()
