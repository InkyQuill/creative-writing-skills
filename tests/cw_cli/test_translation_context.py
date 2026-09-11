from .translation_helpers import TranslationFixture, md
from cwcli.translation.directions import plan_direction, plan_alignment
from cwcli.translation.memory import plan_memory
from cwcli.translation.context import build_packet


class TranslationContextTests(TranslationFixture):
    def setUp(self):
        super().setUp()
        self.edition()
        self.edition('en', 'en')
        self.unit(text='日本語')
        self.unit('u002', text='次')
        self.unit('en-one', 'en', text='English rendering')
        self.apply(plan_direction(self.project, md({'direction-id': 'ru', 'language': 'ru', 'primary-edition': 'ja', 'auxiliary-editions': ['en'], 'coverage': ['v001']})))
        self.apply(plan_alignment(self.project, md({'alignment-id': 'one', 'source-units': ['ja:u001'], 'reference-units': ['en:en-one'], 'status': 'accepted', 'relation': 'equivalent'})))

    def test_packet_has_fixed_sources_neighbors_and_direction_rules(self):
        packet = build_packet(self.project, 'ru', ('ja:u001',), {})
        self.assertEqual('日本語', packet['primary-text'][0]['text'])
        self.assertEqual('English rendering', packet['reference-text'][0]['text'])
        self.assertEqual('次', packet['neighbor-text'][0]['text'])
        self.assertEqual(['ja:u001'], packet['units'])
        self.assertEqual(packet, build_packet(self.project, 'ru', ('ja:u001',), {}))
        self.assertIn('sources/ja/volumes/v001/originals/u001.bin', packet['dependencies'])

    def test_new_rule_changes_inventory_and_false_scope_is_rejected(self):
        before = build_packet(self.project, 'ru', ('ja:u001',), {})
        self.apply(plan_memory(self.project, 'ru', 'voices', md({'record-id': 'voice', 'subject': 'narrator', 'status': 'accepted', 'evidence': ['user: calm narrator']})))
        after = build_packet(self.project, 'ru', ('ja:u001',), {})
        self.assertNotEqual(before['memory-catalog-digest'], after['memory-catalog-digest'])
        self.assertEqual(1, len(after['rules']))
        with self.assertRaises(ValueError):
            build_packet(self.project, 'ru', ('ja:u001',), {'scope-volumes': ['v099']})

    def test_auxiliary_cannot_be_silently_used_as_primary(self):
        with self.assertRaises(ValueError):
            build_packet(self.project, 'ru', ('en:en-one',), {})
