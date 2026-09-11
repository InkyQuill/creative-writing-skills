import io
import json
from .translation_helpers import TranslationFixture, md
from .helpers import app
from cwcli.translation.directions import plan_direction
from cwcli.translation.context import build_packet
from cwcli.translation.drafts import plan_translation_draft
from cwcli.translation.memory import plan_memory
from cwcli.transactions import TransactionConflict
from cwcli.edits import plan_edits
from cwcli.checks.prose import check_prose


class TranslationIntegrationTests(TranslationFixture):
    def setUp(self):
        super().setUp()
        self.edition()
        self.unit(text='<AI>source</AI>')
        self.apply(plan_direction(self.project, md({'direction-id': 'en', 'language': 'en', 'primary-edition': 'ja', 'coverage': ['v001']})))

    def run_cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        status = app.run(args + ['--format', 'json'], cwd=self.root, stdout=out, stderr=err)
        self.assertEqual('', err.getvalue())
        return status, json.loads(out.getvalue())

    def test_cli_context_draft_review_accept_and_correct_prose_language(self):
        status, packet = self.run_cli(['translation', 'context', '--direction', 'en', '--units', 'ja:u001'])
        self.assertEqual(0, status)
        packet_file = self.root.parent / 'packet.json'
        packet_file.write_text(json.dumps(packet))
        text_file = self.root.parent / 'draft.md'
        text_file.write_text('She offered him tea.')
        status, result = self.run_cli(['translation', 'draft', '--direction', 'en', '--draft-id', 'first', '--packet', str(packet_file), '--file', str(text_file), '--apply'])
        self.assertEqual(0, status, result)
        path = 'translations/en/volumes/v001/drafts/first.md'
        self.assertEqual(0, self.run_cli(['translation', 'set-status', path, 'reviewed', '--apply'])[0])
        self.assertEqual(0, self.run_cli(['translation', 'accept', path, '--apply'])[0])
        metrics = [f for f in check_prose(self.project) if f.code == 'CW-PROSE-090' and f.path.endswith('accepted/first.md')]
        self.assertEqual(1, len(metrics))
        self.assertEqual('en', metrics[0].details['language'])
        self.assertFalse(any(f.path.startswith('sources/') for f in check_prose(self.project)))

    def test_new_memory_after_draft_plan_invalidates_apply(self):
        packet = build_packet(self.project, 'en', ('ja:u001',), {})
        plan = plan_translation_draft(self.project, 'en', 'first', packet, b'Translation')
        self.apply(plan_memory(self.project, 'en', 'voices', md({'record-id': 'new', 'subject': 'narrator', 'status': 'accepted', 'evidence': ['user: calm']})))
        with self.assertRaises(TransactionConflict):
            self.apply(plan)
        self.assertFalse((self.root / 'translations/en/volumes/v001/drafts/first.md').exists())

    def test_generic_edit_cannot_forge_domain_identity(self):
        with self.assertRaises(ValueError):
            plan_edits(self.project, [{'op': 'frontmatter-set', 'path': 'sources/ja/volumes/v001/text/u001.md', 'key': 'unit-id', 'value': 'other'}])


class TranslationSeriesScenarioTests(TranslationFixture):
    def test_32_originals_22_references_support_independent_continuations(self):
        self.edition(coverage=[f'v{i:03}' for i in range(1, 33)])
        self.edition('en-official', 'en', coverage=[f'v{i:03}' for i in range(1, 23)])
        self.unit('next', volume='v023', text='未訳の巻')
        for name, language in [('en-continuation', 'en'), ('ru-main', 'ru')]:
            self.apply(plan_direction(self.project, md({'direction-id': name, 'language': language, 'primary-edition': 'ja', 'coverage': [f'v{i:03}' for i in range(23, 33)]})))
        before = build_packet(self.project, 'en-continuation', ('ja:next',), {})
        self.apply(plan_memory(self.project, 'ru-main', 'voices', md({'record-id': 'narrator', 'subject': 'narrator', 'status': 'accepted', 'evidence': ['user: Russian narrator choice']})))
        self.assertEqual(before, build_packet(self.project, 'en-continuation', ('ja:next',), {}))
        self.assertEqual(1, len(build_packet(self.project, 'ru-main', ('ja:next',), {})['rules']))

    def test_standalone_book_import_omits_volume_layer(self):
        from cwcli.scaffold import apply_init
        from cwcli.project import discover_project
        from cwcli.translation.sources import plan_source
        from cwcli.transactions import TransactionEngine
        book = self.root.parent / 'book'
        apply_init(book, 'Book', 'ru', kind='translation', work_kind='book')
        project = discover_project(book)
        engine = TransactionEngine(project)
        engine.apply(plan_source(project, {'action': 'edition', 'content': md({'edition-id': 'source', 'language': 'ja', 'edition-role': 'original', 'revision-label': 'first'}).decode()}))
        original = self.root.parent / 'original.txt'
        original.write_text('原文')
        engine.apply(plan_source(project, {'action': 'unit', 'edition': 'source', 'unit': 'one', 'original-file': str(original), 'text-file': str(original)}))
        engine.apply(plan_direction(project, md({'direction-id': 'ru', 'language': 'ru', 'primary-edition': 'source'})))
        packet = build_packet(project, 'ru', ('source:one',), {})
        self.assertEqual('sources/source/text/one.md', packet['primary-text'][0]['path'])
        self.assertFalse((book / 'sources/source/volumes').exists())
