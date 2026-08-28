import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import app, project, scaffold, schema
from cwcli.checks import structure


def materialize_scaffold(root: Path) -> None:
    for relative_id, content in scaffold.render_scaffold("Second Light", "ru").items():
        path = root / relative_id
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    for relative_id in (".creative-writing/context", ".creative-writing/transactions"):
        (root / relative_id).mkdir(parents=True, exist_ok=True)


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

    def test_expected_kinds_frontmatter_presence_and_allowed_locations_are_enforced(self):
        directory, root = self.make_project()
        with directory:
            vocab = root / "kb/vocab.md"
            vocab.unlink()
            vocab.mkdir()
            (root / "work/_index.md").write_text("# Missing frontmatter\n", encoding="utf-8")
            (root / "story/stray.md").write_text("---\ntitle: Stray\n---\n", encoding="utf-8")

            findings = self.findings_for(root)
            indexed = {(finding.code, finding.severity, finding.path): finding for finding in findings}

            self.assertIn(("CW-STRUCT-011", "error", "kb/vocab.md"), indexed)
            self.assertIn(("CW-STRUCT-021", "warning", "work/_index.md"), indexed)
            self.assertIn(("CW-STRUCT-060", "warning", "story/stray.md"), indexed)
            self.assertTrue(indexed[("CW-STRUCT-011", "error", "kb/vocab.md")].next_action)
            self.assertTrue(indexed[("CW-STRUCT-021", "warning", "work/_index.md")].next_action)
            self.assertTrue(indexed[("CW-STRUCT-060", "warning", "story/stray.md")].next_action)

    def test_schema_v1_allows_each_path_inferred_artifact_class(self):
        directory, root = self.make_project()
        with directory:
            allowed_paths = (
                "story/chapters/chapter-01.md",
                "work/drafts/revision.md",
                "work/plans/arc.md",
                "work/reviews/chapter-01.md",
                "work/brainstorm/opening.md",
                "work/archive/accepted.md",
                "kb/characters/iris.md",
                "kb/world/harbor.md",
                "kb/canon/summary.md",
                "kb/styles/voice.md",
                "kb/samples/dialogue.md",
                "kb/issues/continuity-gap.md",
                "kb/continuity/scenes/chapter-01-scene-01.md",
            )
            for relative_id in allowed_paths:
                path = root / relative_id
                path.write_text("---\ntitle: Allowed\nnumber: 1\n---\n", encoding="utf-8")

            findings = self.findings_for(root)

            self.assertEqual([], [finding.path for finding in findings if finding.code == "CW-STRUCT-060"])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable on this platform")
    def test_expected_kind_check_does_not_follow_symlink(self):
        directory, root = self.make_project()
        with directory:
            external = root.parent / "external-vocab.md"
            external.write_text("---\ntitle: External\n---\n", encoding="utf-8")
            vocab = root / "kb/vocab.md"
            vocab.unlink()
            vocab.symlink_to(external)

            findings = self.findings_for(root)

            self.assertIn(
                ("CW-STRUCT-011", "error", "kb/vocab.md"),
                {(finding.code, finding.severity, finding.path) for finding in findings},
            )

    def test_repairable_metadata_drift_is_warning_first_and_actionable(self):
        directory, root = self.make_project()
        with directory:
            rewrite_manifest(root, schema_version=1)
            (root / "project.md").write_text(
                "---\nschema-version: 1\ntitle:\nlanguage: 7\nstatus: paused\n---\n",
                encoding="utf-8",
            )
            (root / "story/chapters/chapter-01.md").write_text(
                "---\nid: repeated\ntype: repeated\nnumber: one\n---\n",
                encoding="utf-8",
            )

            findings = [finding for finding in self.findings_for(root) if finding.code.startswith("CW-SCHEMA-")]

            self.assertGreaterEqual(len(findings), 6)
            self.assertTrue(all(finding.severity == "warning" for finding in findings))
            self.assertTrue(all(finding.next_action for finding in findings))

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
            self.assertEqual({"checks", "findings", "execution_errors", "strict_failure"}, set(report))
            self.assertEqual(["structure"], report["checks"])
            self.assertEqual([], report["execution_errors"])
            self.assertTrue(report["strict_failure"])
            self.assertIn(
                "warning",
                {finding["severity"] for finding in report["findings"] if finding["code"] == "CW-STRUCT-010"},
            )

    def test_json_check_contains_malformed_manifest_as_an_execution_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            (root / "project.md").write_bytes(b"---\ntitle: Broken\n")
            stdout = io.StringIO()
            stderr = io.StringIO()
            global_stderr = io.StringIO()

            with redirect_stderr(global_stderr):
                status = app.run(
                    ["check", "structure", str(root), "--format", "json"],
                    cwd=root.parent,
                    stdout=stdout,
                    stderr=stderr,
                )

            report = json.loads(stdout.getvalue())
            self.assertEqual(2, status)
            self.assertEqual(["structure"], report["checks"])
            self.assertEqual([], report["findings"])
            self.assertEqual(False, report["strict_failure"])
            self.assertEqual("structure", report["execution_errors"][0]["check"])
            self.assertIn("line 3: unterminated frontmatter", report["execution_errors"][0]["message"])
            self.assertEqual("", stderr.getvalue())
            self.assertEqual("", global_stderr.getvalue())

    def test_json_check_contains_manifest_read_failures_as_execution_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            manifest = root / "project.md"
            manifest.write_text("---\nschema-version: 1\n---\n", encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()
            global_stderr = io.StringIO()
            original_read_bytes = Path.read_bytes

            def fail_only_for_manifest(path: Path) -> bytes:
                if path == manifest.resolve():
                    raise OSError("simulated manifest read failure")
                return original_read_bytes(path)

            with redirect_stderr(global_stderr), patch("cwcli.project.Path.read_bytes", new=fail_only_for_manifest):
                status = app.run(
                    ["check", "structure", str(root), "--format", "json"],
                    cwd=root.parent,
                    stdout=stdout,
                    stderr=stderr,
                )

            report = json.loads(stdout.getvalue())
            self.assertEqual(2, status)
            self.assertEqual(["structure"], report["checks"])
            self.assertEqual("structure", report["execution_errors"][0]["check"])
            self.assertIn("simulated manifest read failure", report["execution_errors"][0]["message"])
            self.assertEqual("", stderr.getvalue())
            self.assertEqual("", global_stderr.getvalue())

    def test_json_check_contains_discovery_failure_as_an_execution_error(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "not-a-project"
            target.mkdir()
            stdout = io.StringIO()
            stderr = io.StringIO()

            status = app.run(
                ["check", "structure", str(target), "--format", "json"],
                cwd=target.parent,
                stdout=stdout,
                stderr=stderr,
            )

            report = json.loads(stdout.getvalue())
            self.assertEqual(2, status)
            self.assertEqual(["structure"], report["checks"])
            self.assertEqual([], report["findings"])
            self.assertEqual("structure", report["execution_errors"][0]["check"])
            self.assertIn("no project.md found", report["execution_errors"][0]["message"])
            self.assertEqual("", stderr.getvalue())

    def test_text_check_uses_injected_stderr_for_execution_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "not-a-project"
            target.mkdir()
            stdout = io.StringIO()
            stderr = io.StringIO()
            global_stderr = io.StringIO()

            with redirect_stderr(global_stderr):
                status = app.run(
                    ["check", "structure", str(target)],
                    cwd=target.parent,
                    stdout=stdout,
                    stderr=stderr,
                )

            self.assertEqual(2, status)
            self.assertEqual("", stdout.getvalue())
            self.assertIn("cw: error: no project.md found", stderr.getvalue())
            self.assertEqual("", global_stderr.getvalue())

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

    def test_init_apply_bootstraps_project(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "new-project"
            stderr = io.StringIO()

            status = app.run(
                ["init", str(target), "--title", "Second Light", "--language", "ru", "--apply"],
                cwd=target.parent,
                stdout=io.StringIO(),
                stderr=stderr,
            )

            self.assertEqual(0, status)
            self.assertEqual("", stderr.getvalue())
            self.assertTrue((target / "project.md").is_file())


if __name__ == "__main__":
    unittest.main()
