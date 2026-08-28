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
                ("CW-SCHEMA-001", "error"),
                ("CW-SCHEMA-010", "warning"),
                ("CW-SCHEMA-011", "warning"),
                ("CW-SCHEMA-012", "warning"),
            ],
            [(finding.code, finding.severity) for finding in findings],
        )
        self.assertTrue(all(finding.next_action for finding in findings))

    def test_boolean_schema_versions_are_not_integers(self):
        for schema_version in (True, False):
            with self.subTest(schema_version=schema_version):
                findings = schema.validate_metadata(
                    "project.md",
                    document(
                        {
                            "schema-version": schema_version,
                            "title": "Second Light",
                            "language": "ru",
                            "status": "planning",
                        }
                    ),
                )

                self.assertEqual([("CW-SCHEMA-001", "error")], [(item.code, item.severity) for item in findings])
                self.assertIn("integer 1", findings[0].message)
                self.assertIsNotNone(findings[0].next_action)

    def test_structural_metadata_drift_is_warning_first_and_actionable(self):
        findings = schema.validate_metadata(
            "story/chapters/chapter-01.md",
            document({"id": "chapter-01", "type": "chapter", "number": "one", "title": "", "status": "draft"}),
        )

        self.assertEqual(
            [
                "CW-SCHEMA-020",
                "CW-SCHEMA-021",
                "CW-SCHEMA-030",
            ],
            [finding.code for finding in findings],
        )
        self.assertTrue(all(finding.severity == "warning" for finding in findings))
        self.assertTrue(all(finding.next_action for finding in findings))

        index_findings = schema.validate_metadata("work/_index.md", document({"generated": False}))
        self.assertEqual([("CW-SCHEMA-040", "warning")], [(item.code, item.severity) for item in index_findings])
        self.assertIsNotNone(index_findings[0].next_action)

    def test_schema_v1_does_not_invent_type_specific_semantic_contracts(self):
        cases = {
            "work/drafts/revision.md": {"future-field": "draft value", "status": "project-defined"},
            "work/plans/arc.md": {"columns": ["custom", "shape"]},
            "kb/world/harbor.md": {"class": "project-defined", "sources": "project-defined"},
            "kb/continuity/state.md": {"table-contract": "project-defined"},
        }

        for relative_id, metadata in cases.items():
            with self.subTest(relative_id=relative_id):
                self.assertEqual([], schema.validate_metadata(relative_id, document(metadata)))


if __name__ == "__main__":
    unittest.main()
