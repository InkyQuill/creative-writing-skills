from .translation_helpers import TranslationFixture, md
from cwcli.translation.directions import plan_direction
from cwcli.checks.translation import check_translation
from cwcli.indexes import plan_reindex
from cwcli.checks.structure import check_structure


class TranslationCheckTests(TranslationFixture):
    def test_missing_translation_is_reported_and_indexes_are_idempotent(self):
        self.edition(); self.unit()
        self.apply(plan_direction(self.project, md({'direction-id': 'ru', 'language': 'ru', 'primary-edition': 'ja', 'coverage': ['v001']})))
        findings = check_translation(self.project)
        self.assertTrue(any(f.code == 'CW-TRANS-020' for f in findings))
        self.apply(plan_reindex(self.project))
        self.assertIn('ja', (self.root / 'sources/_index.md').read_text())
        self.assertEqual((), plan_reindex(self.project).changes)
        self.assertEqual([], [f for f in check_structure(self.project) if f.severity == 'error'])
