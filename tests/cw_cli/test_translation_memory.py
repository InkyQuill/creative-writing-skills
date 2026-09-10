from .translation_helpers import TranslationFixture, md
from cwcli.translation.directions import plan_direction
from cwcli.translation.memory import plan_memory, select_memory


class TranslationMemoryTests(TranslationFixture):
    def setUp(self):
        super().setUp(); self.edition(coverage=['v001', 'v023'])
        for name in ('ru', 'en'):
            self.apply(plan_direction(self.project, md({'direction-id': name, 'language': name, 'primary-edition': 'ja', 'coverage': ['v001', 'v023']})))

    def save(self, name, **fields):
        data = {'record-id': name, 'status': 'accepted', 'subject': 'hero-voice', 'evidence': ['ja:u001 Chapter 1: threat']}
        data.update(fields)
        return self.apply(plan_memory(self.project, 'ru', 'voices', md(data, 'Keep formal speech even when threatening.')))

    def test_scoped_exception_preserves_general_rule_outside_volume(self):
        self.save('general')
        self.save('later', supersedes='general', **{'scope-volumes': ['v023']})
        self.assertEqual(('translations/ru/memory/voices/general.md',), select_memory(self.project, 'ru', {'scope-volumes': ['v001']}))
        self.assertEqual(('translations/ru/memory/voices/later.md',), select_memory(self.project, 'ru', {'scope-volumes': ['v023']}))
        self.assertEqual((), select_memory(self.project, 'en', {'scope-volumes': ['v023']}))

    def test_proposals_are_not_rules_and_overlapping_accepted_rules_conflict(self):
        self.save('proposed', status='proposed')
        self.assertEqual((), select_memory(self.project, 'ru', {}))
        self.save('first')
        self.save('second')
        with self.assertRaisesRegex(ValueError, 'conflict'):
            select_memory(self.project, 'ru', {})

    def test_global_replacement_keeps_history_and_cycles_are_rejected(self):
        self.save('old')
        self.save('new', supersedes='old')
        self.assertEqual(('translations/ru/memory/voices/new.md',), select_memory(self.project, 'ru', {}))
        self.assertIn('superseded', (self.root / 'translations/ru/memory/voices/old.md').read_text())
        with self.assertRaises(ValueError):
            self.save('old', supersedes='new')
