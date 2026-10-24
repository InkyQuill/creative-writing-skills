"""Optional layout must not relax managed translation integrity."""
import io
import json
from dataclasses import replace
from .translation_helpers import TranslationFixture, md
from cwcli import app
from cwcli.drafts import plan_create_draft, DraftError
from cwcli.indexes import plan_reindex
from cwcli.transactions import TransactionStore
from cwcli.translation.directions import plan_direction
from cwcli.translation.context import build_packet
from cwcli.translation.drafts import plan_translation_draft, translation_status


class LayoutTranslationBoundaryTests(TranslationFixture):
    def setUp(self):
        super().setUp()
        self.edition()
        self.unit()
        (self.root / '.cws-layout.json').write_text('{"version":2,"bindings":[]}')

    def test_originals_stay_opaque_and_cannot_be_draft_inputs_or_outputs(self):
        original = 'sources/ja/volumes/v001/originals/extra.md'
        path = self.root / original
        raw = md({'generated': True}, 'Imported source text.\n')
        path.write_bytes(raw)
        (self.root / 'chapter.md').write_text('Story\n')
        with self.assertRaisesRegex(DraftError, 'immutable'):
            plan_create_draft(self.project, original, draft_path='revision.md', store=TransactionStore(self.project))
        with self.assertRaisesRegex(DraftError, 'immutable'):
            plan_create_draft(self.project, 'chapter.md', draft_path=original, store=TransactionStore(self.project))
        self.assertNotIn(original, {self.project.relative_id(p) for p in self.project.iter_managed_markdown()})
        self.assertFalse(list(replace(self.project, selection=original).iter_managed_markdown()))
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        plan = plan_reindex(self.project)
        self.assertNotIn(original, {c.path for c in plan.changes})
        self.assertFalse(any(b'# Contents' in c.after for c in plan.changes if c.after))
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_scoped_translation_check_keeps_dependency_catalog(self):
        self.apply(plan_direction(self.project, md({'direction-id': 'ru', 'language': 'ru', 'primary-edition': 'ja', 'coverage': ['v001']})))
        packet = build_packet(self.project, 'ru', ('ja:u001',), {})
        self.apply(plan_translation_draft(self.project, 'ru', 'first', packet, b'Translation.'))
        path = 'translations/ru/volumes/v001/drafts/first.md'
        self.assertEqual('current', translation_status(self.project, path)['freshness'])
        out, err = io.StringIO(), io.StringIO()
        code = app.run(['check', 'translation', path, '--strict', '--format', 'json'], cwd=self.root, stdout=out, stderr=err)
        self.assertEqual(0, code, out.getvalue() + err.getvalue())
        self.assertEqual([], json.loads(out.getvalue())['findings'])
