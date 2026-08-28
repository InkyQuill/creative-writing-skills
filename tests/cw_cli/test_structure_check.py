import io
import json
import tempfile
import unittest
from pathlib import Path

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import app, project, scaffold, schema
from cwcli.checks import structure


def materialize_scaffold(root: Path) -> None:
    for relative_id, content in scaffold.render_scaffold("Second Light", "ru").items():
        path = root / relative_id
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def rewrite_manifest(root: Path, *, schema_version: int) -> None:
    (root / "project.md").write_text(
        f"---\nschema-version: {schema_version}\ntitle: Second Light\nlanguage: ru\nstatus: planning\n---\n",
        encoding="utf-8",
    )


class StructureCheckTests(unittest.TestCase):
    def make_project(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name) / "project"
        materialize_scaffold(root)
        return directory, root

    def findings_for(self, root: Path):
        return structure.check_structure(project.discover_project(root))

    def test_missing_index_is_warning_but_newer_schema_is_error(self):
        directory, root = self.make_project()
        with directory:
            (root / "kb/_index.md").unlink()

            findings = self.findings_for(root)
            self.assertIn(
                ("CW-STRUCT-010", "warning", "kb/_index.md"),
                {(finding.code, finding.severity, finding.path) for finding in findings},
            )

            rewrite_manifest(root, schema_version=99)
            findings = self.findings_for(root)
            self.assertEqual(
                [("CW-STRUCT-001", "error", "project.md")],
                [(finding.code, finding.severity, finding.path) for finding in findings],
            )

    def test_optional_chapter_status_does_not_produce_a_metadata_finding(self):
        directory, root = self.make_project()
        with directory:
            chapter = root / "story/chapters/chapter-01.md"
            chapter.write_text("---\nnumber: 1\ntitle: Arrival\n---\nText\n", encoding="utf-8")

            findings = self.findings_for(root)

            self.assertNotIn("invalid-chapter-status", {finding.code for finding in findings})

    def test_duplicate_chapter_numbers_are_errors(self):
        directory, root = self.make_project()
        with directory:
            for name in ("chapter-01.md", "chapter-01-revision.md"):
                (root / "story/chapters" / name).write_text(
                    "---\nnumber: 1\ntitle: Arrival\n---\nText\n", encoding="utf-8"
                )

            findings = self.findings_for(root)

            self.assertEqual(
                {"story/chapters/chapter-01.md", "story/chapters/chapter-01-revision.md"},
                {finding.path for finding in findings if finding.code == "CW-STRUCT-030"},
            )
            self.assertTrue(all(finding.severity == "error" for finding in findings if finding.code == "CW-STRUCT-030"))

    def test_malformed_frontmatter_reports_its_path_and_does_not_stop_other_checks(self):
        directory, root = self.make_project()
        with directory:
            malformed = root / "story/chapters/malformed.md"
            malformed.write_bytes(b"---\nnumber: 2\ntitle: Broken\n")
            (root / "README.md").write_text("# Outside\n", encoding="utf-8")

            findings = self.findings_for(root)

            self.assertIn(
                ("CW-STRUCT-020", "error", "story/chapters/malformed.md"),
                {(finding.code, finding.severity, finding.path) for finding in findings},
            )
            self.assertIn(
                ("CW-STRUCT-090", "info", "README.md"),
                {(finding.code, finding.severity, finding.path) for finding in findings},
            )

    def test_unmanaged_markdown_mixed_newlines_and_case_collisions_are_nonblocking_findings(self):
        directory, root = self.make_project()
        with directory:
            (root / "notes.md").write_text("# Notes\n", encoding="utf-8")
            (root / "kb/vocab.md").write_bytes(b"---\r\ntitle: Vocabulary\n---\r\n")
            for name in ("Arrival.md", "arrival.md"):
                (root / "story/chapters" / name).write_text(
                    "---\nnumber: 1\ntitle: Arrival\n---\nText\n", encoding="utf-8"
                )

            findings = self.findings_for(root)
            by_code = {(finding.code, finding.severity) for finding in findings}

            self.assertIn(("CW-STRUCT-090", "info"), by_code)
            self.assertIn(("CW-STRUCT-040", "warning"), by_code)
            self.assertIn(("CW-STRUCT-050", "warning"), by_code)

    def test_check_command_preserves_json_warning_severity_and_strict_status(self):
        directory, root = self.make_project()
        with directory:
            (root / "kb/_index.md").unlink()
            stdout = io.StringIO()

            status = app.run(
                ["check", "structure", str(root), "--strict", "--format", "json"],
                cwd=root.parent,
                stdout=stdout,
                stderr=io.StringIO(),
            )

            report = json.loads(stdout.getvalue())
            self.assertEqual(1, status)
            self.assertTrue(report["strict_failure"])
            self.assertIn(
                "warning",
                {finding["severity"] for finding in report["findings"] if finding["code"] == "CW-STRUCT-010"},
            )

    def test_init_only_previews_sorted_file_and_protected_directory_creates(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "new-project"
            stdout = io.StringIO()

            status = app.run(
                ["init", str(target), "--title", "Second Light", "--language", "ru"],
                cwd=target.parent,
                stdout=stdout,
                stderr=io.StringIO(),
            )

            operations = json.loads(stdout.getvalue())
            self.assertEqual(0, status)
            self.assertFalse(target.exists())
            self.assertEqual([operation["path"] for operation in operations], sorted(operation["path"] for operation in operations))
            self.assertEqual(
                set(schema.SCAFFOLD_FILES) | {".creative-writing/context", ".creative-writing/transactions"},
                {operation["path"] for operation in operations},
            )
            self.assertEqual(
                {"create-directory"},
                {operation["op"] for operation in operations if operation["path"].startswith(".creative-writing/")},
            )
            self.assertEqual(
                {"create"},
                {operation["op"] for operation in operations if not operation["path"].startswith(".creative-writing/")},
            )

    def test_init_apply_is_guarded_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "new-project"
            stderr = io.StringIO()

            status = app.run(
                ["init", str(target), "--title", "Second Light", "--language", "ru", "--apply"],
                cwd=target.parent,
                stdout=io.StringIO(),
                stderr=stderr,
            )

            self.assertEqual(2, status)
            self.assertEqual(
                "init --apply requires the transaction engine; run without --apply for preview\n",
                stderr.getvalue(),
            )
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
