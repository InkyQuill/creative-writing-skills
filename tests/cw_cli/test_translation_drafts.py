import copy
from .translation_helpers import TranslationFixture, md
from cwcli.translation.directions import plan_direction
from cwcli.translation.context import build_packet
from cwcli.translation.drafts import plan_translation_draft, plan_translation_accept, plan_translation_status, translation_status
from cwcli.translation.memory import plan_memory
from cwcli.transactions import TransactionEngine


class TranslationDraftTests(TranslationFixture):
    def setUp(self):
        super().setUp()
        self.edition()
        self.unit()
        self.apply(plan_direction(self.project, md({'direction-id': 'ru', 'language': 'ru', 'primary-edition': 'ja', 'coverage': ['v001']})))
        self.path = 'translations/ru/volumes/v001/drafts/first.md'
        self.target = self.root / 'translations/ru/volumes/v001/accepted/first.md'

    def draft(self, text='Перевод.'):
        packet = build_packet(self.project, 'ru', ('ja:u001',), {})
        self.apply(plan_translation_draft(self.project, 'ru', 'first', packet, text.encode()))

    def test_accept_requires_review_and_staleness_preserves_accepted_text(self):
        self.draft()
        with self.assertRaises(ValueError):
            plan_translation_accept(self.project, self.path)
        self.apply(plan_translation_status(self.project, self.path, 'reviewed'))
        record = self.apply(plan_translation_accept(self.project, self.path))
        self.assertIn('Перевод.', self.target.read_text())
        original = self.target.read_bytes()
        self.apply(plan_memory(self.project, 'ru', 'voices', md({'record-id': 'new', 'subject': 'narrator', 'status': 'accepted', 'evidence': ['user: calm']})))
        state = translation_status(self.project, self.path)
        self.assertEqual('accepted', state['status'])
        self.assertEqual('needs-review', state['freshness'])
        self.assertEqual(original, self.target.read_bytes())
        engine = TransactionEngine(self.project)
        engine.apply(engine.inverse(record.id))
        self.assertFalse(self.target.exists())

    def test_modified_packet_is_rejected_and_hidden_text_cannot_be_accepted(self):
        packet = build_packet(self.project, 'ru', ('ja:u001',), {})
        forged = copy.deepcopy(packet)
        forged['primary-text'][0]['text'] = 'different'
        with self.assertRaises(ValueError):
            plan_translation_draft(self.project, 'ru', 'bad', forged, b'text')
        self.draft('<hidden>secret</hidden>')
        self.apply(plan_translation_status(self.project, self.path, 'reviewed'))
        with self.assertRaises(ValueError):
            plan_translation_accept(self.project, self.path)
        self.assertFalse(self.target.exists())

    def test_revision_requires_unchanged_accepted_base(self):
        self.draft()
        self.apply(plan_translation_status(self.project, self.path, 'reviewed'))
        self.apply(plan_translation_accept(self.project, self.path))
        self.draft('Новая версия.')
        self.apply(plan_translation_status(self.project, self.path, 'reviewed'))
        self.target.write_text('User correction')
        with self.assertRaises(ValueError):
            plan_translation_accept(self.project, self.path)
        self.assertEqual('User correction', self.target.read_text())
