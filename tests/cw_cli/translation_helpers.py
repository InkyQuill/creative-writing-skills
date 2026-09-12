import tempfile
import unittest
from pathlib import Path
from . import helpers
from cwcli.scaffold import apply_init
from cwcli.project import discover_project
from cwcli.documents import Document, render_document
from cwcli.transactions import TransactionEngine


def md(metadata, body='Evidence and instructions.\n'):
    return render_document(Document(metadata, body, '\n', False))


class TranslationFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'
        apply_init(self.root, 'Series', 'ru', kind='translation', work_kind='series')
        self.project = discover_project(self.root)

    def apply(self, plan):
        return TransactionEngine(self.project).apply(plan, transaction_id=plan.metadata.get('transaction-id'))

    def edition(self, name='ja', language='ja', coverage=None):
        from cwcli.translation.sources import plan_source
        self.apply(plan_source(self.project, {'action': 'edition', 'content': md({'edition-id': name, 'language': language, 'edition-role': 'original' if name == 'ja' else 'translation', 'revision-label': 'first', 'coverage': coverage or ['v001']}).decode()}))

    def unit(self, unit='u001', edition='ja', text='Original prose.', volume='v001'):
        from cwcli.translation.sources import plan_source
        source = Path(self.temp.name) / (edition + '-' + unit + '.bin')
        source.write_bytes(b'\xffopaque')
        extracted = Path(self.temp.name) / 'extracted.md'
        extracted.write_text(text)
        return self.apply(plan_source(self.project, {'action': 'unit', 'edition': edition, 'unit': unit, 'volume': volume, 'original-file': str(source), 'text-file': str(extracted)}))
