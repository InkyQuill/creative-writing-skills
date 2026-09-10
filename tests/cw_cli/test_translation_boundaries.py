import io
import json
from pathlib import Path
from .translation_helpers import TranslationFixture, md
from .helpers import app
from cwcli.translation.sources import plan_source
from cwcli.translation.directions import plan_direction
from cwcli.translation.context import build_packet
from cwcli.translation.catalog import load_catalog


class TranslationBoundaryTests(TranslationFixture):
    def setUp(self):
        super().setUp(); self.edition(); self.apply(plan_direction(self.project, md({'direction-id': 'ru', 'language': 'ru', 'primary-edition': 'ja', 'coverage': ['v001']})))

    def test_neighbors_follow_import_order_not_alphabetic_unit_ids(self):
        self.unit('z-first', text='First'); self.unit('a-second', text='Second'); self.unit('m-third', text='Third')
        packet = build_packet(self.project, 'ru', ('ja:z-first',), {})
        self.assertEqual(['Second'], [x['text'] for x in packet['neighbor-text']])

    def test_unrelated_malformed_source_does_not_block_readable_volume(self):
        self.unit()
        path = self.root / 'sources/ja/volumes/v099/text/broken.md'; path.parent.mkdir(parents=True); path.write_text('---\nbroken: [not supported]\n---\n')
        packet = build_packet(self.project, 'ru', ('ja:u001',), {})
        self.assertEqual('Original prose.', packet['primary-text'][0]['text'])
        with self.assertRaises(ValueError):
            load_catalog(self.project)

    def test_invalid_json_shape_reports_cli_error_instead_of_traceback(self):
        path = self.root.parent / 'bad.json'; path.write_text('[]')
        out, err = io.StringIO(), io.StringIO()
        status = app.run(['translation', 'source', '--request', str(path), '--format', 'json'], cwd=self.root, stdout=out, stderr=err)
        self.assertEqual(2, status)
        self.assertEqual('error', json.loads(out.getvalue())['status'])

    def test_duplicate_order_is_rejected(self):
        self.unit()
        original = self.root.parent / 'another.bin'; original.write_bytes(b'original')
        text = self.root.parent / 'another.md'; text.write_text('second')
        with self.assertRaises(ValueError):
            plan_source(self.project, {'action':'unit','edition':'ja','unit':'another','volume':'v001','order':1,'original-file':str(original),'text-file':str(text)})
