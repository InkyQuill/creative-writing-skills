import os
import tempfile
import unittest
from pathlib import Path

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import project


def write_manifest(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "project.md").write_text("---\ntitle: Test project\n---\n", encoding="utf-8")


def make_project(root: Path) -> project.Project:
    write_manifest(root)
    return project.discover_project(root)


class ProjectDiscoveryTests(unittest.TestCase):
    def test_nearest_project_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root)
            child = root / "nested"
            write_manifest(child)

            self.assertEqual(project.discover_project(child / "story").root, child.resolve())

    def test_write_refuses_parent_and_nested_project(self):
        with tempfile.TemporaryDirectory() as directory:
            outer = make_project(Path(directory) / "outer")
            make_project(outer.root / "story" / "nested")

            with self.assertRaisesRegex(project.ProjectPathError, "nested project"):
                outer.resolve("story/nested/project.md", for_write=True)
            with self.assertRaisesRegex(project.ProjectPathError, "outside project"):
                outer.resolve("../escape.md", for_write=True)

    def test_write_refuses_protected_absolute_and_windows_reserved_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            story_project = make_project(Path(directory) / "story-project")

            with self.assertRaisesRegex(project.ProjectPathError, "protected"):
                story_project.resolve(".creative-writing/transactions/entry.json", for_write=True)
            with self.assertRaisesRegex(project.ProjectPathError, "absolute"):
                story_project.resolve("/tmp/escape.md", for_write=True)
            with self.assertRaisesRegex(project.ProjectPathError, "absolute"):
                story_project.resolve("C:/escape.md", for_write=True)
            with self.assertRaisesRegex(project.ProjectPathError, "Windows reserved"):
                story_project.resolve("story/CON.md", for_write=True)

    def test_write_refuses_case_colliding_target(self):
        with tempfile.TemporaryDirectory() as directory:
            story_project = make_project(Path(directory) / "story-project")
            existing = story_project.root / "story" / "Chapter.md"
            existing.parent.mkdir()
            existing.write_text("Chapter\n", encoding="utf-8")

            with self.assertRaisesRegex(project.ProjectPathError, "case-colliding"):
                story_project.resolve("story/chapter.md", for_write=True)

    def test_managed_root_that_is_a_nested_project_is_omitted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for root_name in ("story", "work", "kb"):
                with self.subTest(root_name=root_name):
                    story_project = make_project(root / root_name)
                    nested_root = story_project.root / root_name
                    write_manifest(nested_root)
                    (nested_root / "nested.md").write_text("Nested\n", encoding="utf-8")

                    self.assertEqual([], list(story_project.iter_managed_markdown()))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable on this platform")
    def test_managed_iteration_and_writes_do_not_follow_symlinks_or_nested_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story_project = make_project(root / "story-project")
            chapter = story_project.root / "story" / "chapters" / "chapter.md"
            chapter.parent.mkdir(parents=True)
            chapter.write_text("Chapter\n", encoding="utf-8")
            notes = story_project.root / "work" / "notes.MD"
            notes.parent.mkdir()
            notes.write_text("Notes\n", encoding="utf-8")
            nested = story_project.root / "story" / "nested"
            write_manifest(nested)
            (nested / "hidden.md").write_text("Hidden\n", encoding="utf-8")
            external = root / "external.md"
            external.write_text("External\n", encoding="utf-8")
            linked = story_project.root / "story" / "external.md"
            linked.symlink_to(external)
            external_directory = root / "external-directory"
            external_directory.mkdir()
            linked_directory = story_project.root / "story" / "external-directory"
            linked_directory.symlink_to(external_directory, target_is_directory=True)

            self.assertEqual(
                ["story/chapters/chapter.md", "work/notes.MD"],
                [story_project.relative_id(path) for path in story_project.iter_managed_markdown()],
            )
            self.assertEqual(story_project.resolve("story/external.md"), linked)
            with self.assertRaisesRegex(project.ProjectPathError, "symlink"):
                story_project.resolve("story/external.md", for_write=True)
            with self.assertRaisesRegex(project.ProjectPathError, "symlink"):
                story_project.resolve("story/external-directory/new.md", for_write=True)


if __name__ == "__main__":
    unittest.main()
