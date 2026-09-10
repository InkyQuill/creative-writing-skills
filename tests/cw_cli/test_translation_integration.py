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
        super().setUp(); self.edition(); self.unit(text='<AI>source</AI>')
        self.apply(plan_direction(self.project, md({'direction-id': 'en', 'language': 'en', 'primary-edition': 'ja', 'coverage': ['v001']})))

    def run_cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        status = app.run(args + ['--format', 'json'], cwd=self.root, stdout=out, stderr=err)
        self.assertEqual('', err.getvalue())
        return status, json.loads(out.getvalue())

    def test_cli_context_draft_review_accept_and_correct_prose_language(self):
        status, packet = self.run_cli(['translation', 'context', '--direction', 'en', '--units', 'ja:u001'])
        self.assertEqual(0, status)
        packet_file = self.root.parent / 'packet.json'; packet_file.write_text(json.dumps(packet))
        text_file = self.root.parent / 'draft.md'; text_file.write_text('She offered him tea.')
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
