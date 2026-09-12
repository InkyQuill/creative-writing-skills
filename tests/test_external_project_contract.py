import json
from pathlib import Path

from tests.cw_cli import helpers  # noqa: F401
from tests.cw_cli.translation_helpers import TranslationFixture
from cwcli.project import discover_project
from cwcli.schema import allowed_document_kind, validate_metadata
from cwcli.translation.catalog import load_catalog
from cwcli.translation.contract import project_settings, translation_kind
from cwcli.translation.directions import effective_direction, resolve_unit


CONTRACT_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "plugins/creative-writing-skills/skills/project-maintenance/resources/compatibility/cws-project-v1.json"
)

KIND_TO_PUBLIC_ROLE = {
    "manifest": "manifest",
    "chapter": "accepted_prose",
    "side-story": "accepted_prose",
    "work-artifact": "work",
    "kb-content": "knowledge",
    "continuity-record": "knowledge",
    "continuity-scene": "knowledge",
    "vocabulary": "knowledge",
    "generated-index": "derived",
    "edition": "source_edition",
    "source-unit": "source_unit",
    "direction": "translation_direction",
    "direction-settings": "direction_settings",
    "translation-memory": "translation_memory",
    "alignment": "alignment",
    "entity": "entity",
    "translation-drafts": "draft",
    "translation-reviews": "review",
    "translation-accepted": "accepted_prose",
}

PRODUCER_FAILURE_TO_CONTRACT = {"CW-SCHEMA-001": "unsupported_schema"}


class ExternalProjectContractTests(TranslationFixture):
    def setUp(self):
        super().setUp()
        self.fixture = json.loads(CONTRACT_FIXTURE.read_text(encoding="utf-8"))

    def materialize(self, case):
        case_root = Path(self.temp.name) / "contract" / case["name"]
        for relative, content in case["files"].items():
            target = case_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return case_root

    def test_portable_cases_match_cws_discovery_schema_and_document_roles(self):
        self.assertEqual(1, self.fixture["contract_version"])
        self.assertEqual([1, 2], self.fixture["project_schemas"])

        for case in self.fixture["cases"]:
            with self.subTest(case=case["name"]):
                case_root = self.materialize(case)
                expect = case["expect"]
                expected_root = case_root / expect.get("root", ".")
                start = expected_root / "story"
                project = discover_project(start if start.exists() else expected_root)

                if "technical_failure" in expect:
                    findings = validate_metadata("project.md", project.manifest)
                    producer_code = expect["producer_code"]
                    self.assertIn(producer_code, [finding.code for finding in findings])
                    self.assertEqual(
                        expect["technical_failure"],
                        PRODUCER_FAILURE_TO_CONTRACT[producer_code],
                    )
                    with self.assertRaisesRegex(ValueError, "unsupported project schema"):
                        project_settings(project.manifest.metadata)
                    continue

                self.assertEqual(expected_root.resolve(), project.root)
                self.assertEqual(
                    expect["schema_version"],
                    project.manifest.metadata["schema-version"],
                )
                self.assertFalse(
                    [
                        finding
                        for finding in validate_metadata("project.md", project.manifest)
                        if finding.severity == "error"
                    ]
                )
                for relative, expected_role in expect["roles"].items():
                    with self.subTest(case=case["name"], path=relative):
                        self.assertTrue((project.root / relative).exists())
                        actual_role = self.public_role(relative, expect["schema_version"])
                        self.assertEqual(expected_role, actual_role)

    def test_schema_v2_cases_match_translation_settings_and_catalog_semantics(self):
        cases = {case["name"]: case for case in self.fixture["cases"]}

        book = discover_project(self.materialize(cases["translation-book"]))
        self.assertEqual(
            ("translation", "book", True), project_settings(book.manifest.metadata)
        )
        book_catalog = load_catalog(book)
        self.assertEqual("source-unit", translation_kind("sources/ja/text/u001.md"))
        self.assertEqual(
            "ja:u001",
            book_catalog["translations/ru-main/drafts/u001.md"].metadata[
                "source-units"
            ][0],
        )
        self.assertEqual(
            [],
            effective_direction(book, "ru-main", None, catalog=book_catalog)[
                "auxiliary-editions"
            ],
        )
        self.assertEqual(
            "ru",
            effective_direction(book, "ru-literary", None, catalog=book_catalog)[
                "language"
            ],
        )

        series = discover_project(self.materialize(cases["translation-series"]))
        self.assertEqual(
            ("translation", "series", True), project_settings(series.manifest.metadata)
        )
        series_catalog = load_catalog(series)
        self.assertEqual(
            "direction-settings",
            translation_kind("translations/ru-main/volumes/v002/settings.md"),
        )
        self.assertEqual(
            ["en"],
            effective_direction(series, "ru-main", "v001", catalog=series_catalog)[
                "auxiliary-editions"
            ],
        )
        self.assertEqual(
            [],
            effective_direction(series, "ru-main", "v002", catalog=series_catalog)[
                "auxiliary-editions"
            ],
        )
        self.assertEqual(
            "ru",
            effective_direction(
                series, "ru-literary", "v002", catalog=series_catalog
            )["language"],
        )

    def test_actionable_direction_cases_follow_producer_effective_settings(self):
        for case in self.fixture["cases"]:
            selections = case["expect"].get("selections", [])
            if not selections:
                continue
            project = discover_project(self.materialize(case))
            catalog = load_catalog(project)
            for selection in selections:
                with self.subTest(case=case["name"], selection=selection):
                    if selection.get("diagnostic") == "uncovered_edition":
                        with self.assertRaisesRegex(ValueError, "does not cover"):
                            effective_direction(
                                project, selection["direction_id"], "v002", catalog=catalog
                            )
                        continue
                    if selection["status"] not in ("ready", "unbound"):
                        continue
                    direction = selection.get(
                        "selected_direction", selection["direction_id"]
                    )
                    volumes = (
                        [selection["volume_id"]]
                        if selection["volume_id"]
                        else catalog[f"translations/{direction}/translation.md"].metadata[
                            "coverage"
                        ]
                    )
                    for volume in volumes:
                        settings = effective_direction(
                            project, direction, volume, catalog=catalog
                        )
                        self.assertEqual(selection["target_language"], settings["language"])
                        self.assertEqual(
                            selection["primary_edition"], settings["primary-edition"]
                        )
                        self.assertEqual(
                            selection["auxiliary_editions"], settings["auxiliary-editions"]
                        )
                        edition = catalog[f"sources/{settings['primary-edition']}/edition.md"]
                        self.assertEqual(
                            selection["source_language"], edition.metadata["language"]
                        )
                    for reference in selection.get("source_units", []):
                        path, doc = resolve_unit(project, reference, catalog=catalog)
                        self.assertEqual(selection["cwd"], path)
                        self.assertEqual(selection["volume_id"], doc.metadata["volume-id"])
                        self.assertRegex(doc.metadata["original-sha256"], r"^[0-9a-f]{64}$")

    def test_schema_v2_authoring_keeps_authoring_document_roles(self):
        cases = {case["name"]: case for case in self.fixture["cases"]}
        case = cases["authoring-v2-retained-structure"]
        project = discover_project(self.materialize(case))

        self.assertEqual(
            ("authoring", "book", True), project_settings(project.manifest.metadata)
        )
        expected = {
            "story/chapters/01.md": "accepted_prose",
            "story/side-stories/after-01.md": "accepted_prose",
            "work/drafts/revision.md": "work",
            "kb/vocab.md": "knowledge",
            "kb/continuity/state.md": "knowledge",
            "kb/continuity/scenes/arrival.md": "knowledge",
            "kb/canon/premise.md": "knowledge",
            "story/chapters/_index.md": "derived",
        }
        self.assertEqual(
            expected,
            {
                relative: self.public_role(relative, 2)
                for relative in expected
            },
        )

    @staticmethod
    def public_role(relative, schema_version):
        if relative == "AGENTS.md":
            return "instructions"
        if relative.startswith(".creative-writing/"):
            return "private_state"
        kind = allowed_document_kind(relative, schema_version=schema_version)
        if kind is None:
            return "opaque"
        return KIND_TO_PUBLIC_ROLE[kind]


if __name__ == "__main__":
    import unittest

    unittest.main()
