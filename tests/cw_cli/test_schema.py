import tempfile
import unittest
from pathlib import Path

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import documents, scaffold, schema


def document(metadata: dict[str, str | int | bool | list[str]]) -> documents.Document:
    return documents.Document(metadata=metadata, body="", newline="\n", bom=False)


def materialize_scaffold(root: Path, title: str = "Second Light", language: str = "ru") -> None:
    for relative_id, content in scaffold.render_scaffold(title, language).items():
        path = root / relative_id
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


class ScaffoldTests(unittest.TestCase):
    def test_scaffold_contains_every_canonical_file(self):
        rendered = scaffold.render_scaffold("Second Light", "ru")

        self.assertEqual(set(rendered), set(schema.SCAFFOLD_FILES))
        self.assertEqual(list(rendered), sorted(rendered))
        manifest = documents.parse_document(rendered["project.md"])
        self.assertEqual(manifest.metadata["schema-version"], 1)
        self.assertEqual(manifest.metadata["title"], "Second Light")
        self.assertEqual(manifest.metadata["language"], "ru")
        self.assertEqual(manifest.metadata["status"], "planning")
        self.assertIn("kb/samples/_index.md", rendered)
        self.assertNotIn("AGENTS.md", rendered)

        expected_continuity = {
            "kb/continuity/_index.md",
            "kb/continuity/timeline.md",
            "kb/continuity/state.md",
            "kb/continuity/promises.md",
            "kb/continuity/questions.md",
            "kb/continuity/scenes/_index.md",
        }
        self.assertTrue(expected_continuity.issubset(rendered))
        expected_indexes = {
            "story/_index.md",
            "story/chapters/_index.md",
            "work/_index.md",
            "work/drafts/_index.md",
            "work/plans/_index.md",
            "work/reviews/_index.md",
            "work/brainstorm/_index.md",
            "work/archive/_index.md",
            "kb/_index.md",
            "kb/characters/_index.md",
            "kb/world/_index.md",
            "kb/canon/_index.md",
            "kb/continuity/_index.md",
            "kb/continuity/scenes/_index.md",
            "kb/styles/_index.md",
            "kb/samples/_index.md",
            "kb/issues/_index.md",
        }
        self.assertEqual(expected_indexes, {path for path in rendered if path.endswith("/_index.md")})
        self.assertIn("Project instructions", manifest.body)
        self.assertIn("story/chapters/", manifest.body)
        self.assertNotIn("AGENTS.md", manifest.body)
        self.assertNotIn("CLAUDE.md", manifest.body)

    def test_renderer_uses_lf_trailing_newlines_and_generated_index_shape(self):
        rendered = scaffold.render_scaffold("Second Light", "ru")

        for relative_id, content in rendered.items():
            with self.subTest(relative_id=relative_id):
                self.assertTrue(content.endswith(b"\n"))
                self.assertNotIn(b"\r", content)
        for relative_id in (path for path in rendered if path.endswith("/_index.md")):
            with self.subTest(relative_id=relative_id):
                parsed = documents.parse_document(rendered[relative_id])
                self.assertEqual({"generated": True}, parsed.metadata)
                self.assertRegex(parsed.body, r"^# .+\n\n<!-- generated registry -->\n$")

    def test_renderer_can_materialize_the_minimal_project_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            materialize_scaffold(root)

            self.assertEqual(
                list(schema.SCAFFOLD_FILES),
                sorted(path.relative_to(root).as_posix() for path in root.rglob("*.md")),
            )


class MetadataValidationTests(unittest.TestCase):
    def test_valid_manifest_and_document_metadata_produce_no_findings(self):
        findings = schema.validate_metadata(
            "project.md",
            document(
                {
                    "schema-version": 1,
                    "title": "Second Light",
                    "language": "ru",
                    "status": "drafting",
                }
            ),
        )

        self.assertEqual([], findings)
        self.assertEqual(
            [],
            schema.validate_metadata(
                "story/chapters/chapter-01.md",
                document({"number": 1, "title": "Arrival", "status": "accepted"}),
            ),
        )
        self.assertEqual(
            [],
            schema.validate_metadata(
                "kb/world/harbor.md",
                document({"class": "location", "sources": ["story/chapters/chapter-01.md"]}),
            ),
        )

    def test_invalid_manifest_reports_each_required_schema_v1_field(self):
        findings = schema.validate_metadata(
            "project.md",
            document({"schema-version": 2, "title": "", "language": 1, "status": "paused"}),
        )

        self.assertEqual(
            [
                ("invalid-schema-version", "schema-version must be 1"),
                ("invalid-title", "title must be a non-empty string"),
                ("invalid-language", "language must be a non-empty string"),
                ("invalid-project-status", "status must be one of: archived, complete, drafting, planning, revising"),
            ],
            [(finding.code, finding.message) for finding in findings],
        )

    def test_document_metadata_rejects_repeated_identity_and_invalid_type_specific_fields(self):
        findings = schema.validate_metadata(
            "story/chapters/chapter-01.md",
            document({"id": "chapter-01", "type": "chapter", "number": "one", "title": "", "status": "draft"}),
        )

        self.assertEqual(
            [
                "repeated-document-id",
                "repeated-document-type",
                "invalid-chapter-number",
                "invalid-title",
                "invalid-chapter-status",
            ],
            [finding.code for finding in findings],
        )
        findings = schema.validate_metadata("kb/world/harbor.md", document({"class": "city", "sources": "chapter"}))
        self.assertEqual(["invalid-world-class", "invalid-sources"], [finding.code for finding in findings])


if __name__ == "__main__":
    unittest.main()
