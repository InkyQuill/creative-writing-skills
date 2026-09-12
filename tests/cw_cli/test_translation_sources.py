from .translation_helpers import TranslationFixture, md
from cwcli.translation.sources import plan_source
from cwcli.translation.catalog import load_catalog
from cwcli.edits import plan_edits


class TranslationSourceTests(TranslationFixture):
    def test_import_preserves_binary_original_and_refresh_keeps_identity(self):
        self.edition()
        self.unit()
        original = self.root / 'sources/ja/volumes/v001/originals/u001.bin'
        self.assertEqual(b'\xffopaque', original.read_bytes())
        extracted = self.root.parent / 'fixed.md'
        extracted.write_text('Fixed extraction')
        self.apply(plan_source(self.project, {'action': 'refresh-unit', 'edition': 'ja', 'unit': 'u001', 'text-file': str(extracted)}))
        self.assertEqual(b'\xffopaque', original.read_bytes())
        doc = load_catalog(self.project)['sources/ja/volumes/v001/text/u001.md']
        self.assertEqual('u001', doc.metadata['unit-id'])
        self.assertEqual('Fixed extraction', doc.body)

    def test_duplicate_import_and_outside_coverage_fail_without_changes(self):
        self.edition()
        self.unit()
        with self.assertRaises(ValueError):
            self.unit()
        with self.assertRaises(ValueError):
            self.unit(unit='u002', volume='v032')
        self.assertFalse((self.root / 'sources/ja/volumes/v032').exists())

    def test_original_markdown_cannot_be_changed_by_generic_edit(self):
        self.edition()
        self.unit()
        with self.assertRaises(ValueError):
            plan_edits(self.project, [{'op': 'replace', 'path': 'sources/ja/volumes/v001/originals/u001.bin', 'old': 'opaque', 'new': 'changed'}])
