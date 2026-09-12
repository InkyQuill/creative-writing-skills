from .translation_helpers import TranslationFixture, md
from cwcli.translation.directions import plan_direction, effective_direction, plan_alignment


class TranslationDirectionTests(TranslationFixture):
    def test_volume_override_and_two_russian_versions(self):
        self.edition(coverage=['v001', 'v023'])
        self.edition('en', 'en')
        for name in ('ru-main', 'ru-other'):
            self.apply(plan_direction(self.project, md({'direction-id': name, 'language': 'ru', 'primary-edition': 'ja', 'auxiliary-editions': ['en'], 'coverage': ['v001', 'v023']})))
        with self.assertRaisesRegex(ValueError, 'cover'):
            effective_direction(self.project, 'ru-main', 'v023')
        self.apply(plan_direction(self.project, md({'direction-id': 'ru-main', 'volume-id': 'v023', 'auxiliary-editions': []})))
        self.assertEqual([], effective_direction(self.project, 'ru-main', 'v023')['auxiliary-editions'])
        with self.assertRaises(ValueError):
            effective_direction(self.project, 'ru-other', 'v023')

    def test_split_alignment_uses_ids_and_rejects_missing_units(self):
        self.edition()
        self.edition('en', 'en')
        self.unit()
        self.unit('a', 'en')
        self.unit('b', 'en')
        self.apply(plan_alignment(self.project, md({'alignment-id': 'split', 'source-units': ['ja:u001'], 'reference-units': ['en:a', 'en:b'], 'status': 'accepted', 'relation': 'split'})))
        with self.assertRaises(ValueError):
            plan_alignment(self.project, md({'alignment-id': 'bad', 'source-units': ['ja:missing'], 'reference-units': ['en:a'], 'status': 'accepted', 'relation': 'equivalent'}))
        self.assertTrue((self.root / 'kb/source-comparisons/split.md').is_file())
