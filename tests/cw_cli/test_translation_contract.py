import tempfile
import unittest
from pathlib import Path
from . import helpers
from cwcli.documents import parse_document
from cwcli.project import discover_project
from cwcli.schema import validate_metadata, allowed_document_kind


class TranslationContractTests(unittest.TestCase):
    def test_v2_manifest_and_paths_are_supported_without_weakening_v1(self):
        doc = parse_document(b'---\nschema-version: 2\ntitle: Series\nlanguage: ru\nstatus: planning\nproject-kind: translation\nwork-kind: series\ntranslation-enabled: true\n---\n')
        self.assertEqual([], validate_metadata('project.md', doc))
        self.assertEqual('source-unit', allowed_document_kind('sources/ja/volumes/v001/text/a.md', schema_version=2))
        self.assertIsNone(allowed_document_kind('sources/ja/text/a.md'))

    def test_settings_keep_legacy_default_and_reject_invalid_v2(self):
        from cwcli.translation.contract import project_settings
        self.assertEqual(('authoring', 'book', False), project_settings({'schema-version': 1}))
        for metadata in ({'schema-version': True}, {'schema-version': 3},
                         {'schema-version': 2, 'project-kind': 'translation', 'work-kind': 'bad', 'translation-enabled': True}):
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                project_settings(metadata)

    def test_discovery_skips_opaque_originals_and_nested_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'project.md').write_text('---\nschema-version: 2\nproject-kind: translation\nwork-kind: book\ntranslation-enabled: true\n---\n')
            for path in ('sources/ja/originals/raw.md', 'sources/ja/text/a.md', 'translations/ru/nested/project.md', 'translations/ru/nested/a.md'):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('text')
            project = discover_project(root)
            self.assertEqual(['sources/ja/text/a.md'], [project.relative_id(p) for p in project.iter_managed_markdown()])

    def test_catalog_rejects_duplicate_unit_identity_and_reference_escape(self):
        from cwcli.translation.catalog import load_catalog, read_source
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'project.md').write_text('---\nschema-version: 2\nproject-kind: translation\nwork-kind: book\ntranslation-enabled: true\n---\n')
            text = root / 'sources/ja/text'
            text.mkdir(parents=True)
            for name in ('a', 'b'):
                (text / (name + '.md')).write_text('---\nunit-id: same\n---\n')
            project = discover_project(root)
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                load_catalog(project)
            with self.assertRaises(ValueError):
                read_source(project, '../outside.md')
