import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from .helpers import app
from cwcli.project import discover_project
from cwcli.transactions import Change, TransactionEngine, TransactionPlan, TransactionConflict


class TranslationSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'

    def run_cli(self, args, cwd=None):
        out, err = io.StringIO(), io.StringIO()
        code = app.run(args + ['--format', 'json'], cwd=cwd or self.root.parent, stdout=out, stderr=err)
        self.assertEqual('', err.getvalue())
        return code, json.loads(out.getvalue())

    def test_standalone_preview_then_apply(self):
        args = ['init', str(self.root), '--title', 'Series', '--language', 'ru', '--kind', 'translation', '--work-kind', 'series']
        code, _ = self.run_cli(args)
        self.assertEqual(0, code)
        self.assertFalse(self.root.exists())
        code, result = self.run_cli(args + ['--apply'])
        self.assertEqual(0, code, result)
        self.assertFalse((self.root / 'story').exists())
        self.assertTrue((self.root / 'sources/_index.md').is_file())
        self.assertEqual('translation', discover_project(self.root).manifest.metadata['project-kind'])

    def test_enable_preserves_manuscript_and_is_undoable(self):
        self.assertEqual(0, self.run_cli(['init', str(self.root), '--title', 'A', '--language', 'ja', '--template', 'full', '--apply'])[0])
        story = self.root / 'story/chapters/one.md'
        story.write_text('my prose')
        before = (self.root / 'project.md').read_bytes()
        code, result = self.run_cli(['translation', 'enable', '--work-kind', 'series', '--apply'], self.root)
        self.assertEqual(0, code, result)
        self.assertEqual('my prose', story.read_text())
        code, result = self.run_cli(['undo', result['transaction_id'], '--apply'], self.root)
        self.assertEqual(0, code, result)
        self.assertEqual(before, (self.root / 'project.md').read_bytes())

    def test_read_guard_rejects_source_changed_after_preview(self):
        self.run_cli(['init', str(self.root), '--title', 'A', '--language', 'ja', '--apply'])
        source = self.root / 'source.bin'
        source.write_bytes(b'\xfforiginal')
        engine = TransactionEngine(discover_project(self.root))
        plan = TransactionPlan(('test',), (Change('result.txt', None, b'result'),),
                               {'read-guards': {'source.bin': hashlib.sha256(source.read_bytes()).hexdigest()}})
        engine.preview(plan)
        source.write_bytes(b'changed')
        with self.assertRaises(TransactionConflict):
            engine.apply(plan)
        self.assertFalse((self.root / 'result.txt').exists())
