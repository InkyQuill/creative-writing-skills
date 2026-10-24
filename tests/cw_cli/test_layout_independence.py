import io
import json
import tempfile
import unittest
from pathlib import Path
from tests.cw_cli import helpers  # noqa: F401
from cwcli import app


class LayoutIndependenceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        code = app.run([*args, '--format', 'json'], cwd=self.root, stdout=out, stderr=err)
        self.assertNotEqual(2, code, out.getvalue() + err.getvalue())
        return code, json.loads(out.getvalue())

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_flat_unconfigured_check_all_never_scaffolds(self):
        self.write('chapter.md', '# Chapter\nHello.\n')
        before = self.snapshot()
        code, result = self.run_cli('check', 'all', '.', '--strict')
        self.assertEqual(0, code, result)
        self.assertEqual([], result['execution_errors'])
        self.assertEqual(before, self.snapshot())
        self.assertEqual({'chapter.md'}, {p.name for p in self.root.iterdir()})
        self.assertTrue(any('chapter.md' in c['paths'] for c in result['coverage']))

    def test_named_file_check_finds_links_without_checking_siblings(self):
        self.write('one.md', '[lost](missing.md)\n')
        self.write('two.md', '[other](also-missing.md)\n')
        _, result = self.run_cli('check', 'links', 'one.md')
        self.assertEqual({'one.md'}, {f['path'] for f in result['findings']})
        self.assertTrue(any(f['code'] == 'CW-LINK-010' for f in result['findings']))
        self.assertEqual(['one.md'], result['coverage'][0]['paths'])

    def test_ordinary_tagged_drafts_do_not_need_lifecycle_metadata(self):
        self.write('.cws-layout.json', json.dumps({'version': 2, 'bindings': [{'path': '.', 'kind': 'directory', 'tags': ['drafts']}]}))
        self.write('one.md', '# Working text\n')
        code, result = self.run_cli('check', 'all', '.', '--strict')
        self.assertEqual(0, code, result)
        self.assertFalse(any(f['code'].startswith('CW-DRAFT') for f in result['findings']))

    def test_opaque_metadata_does_not_demand_repair(self):
        self.write('one.md', '---\ntags: [a, b]\n---\nHello.\n')
        code, result = self.run_cli('check', 'all', '.', '--strict')
        self.assertEqual(0, code, result)
        self.assertTrue(any('metadata' in (c['skipped_reason'] or '') for c in result['coverage']))

    def test_explicit_prose_check_runs_generic_rules(self):
        self.write('one.md', '<AI>unclosed\n')
        _, result = self.run_cli('check', 'prose', 'one.md')
        self.assertTrue(result['findings'])
        self.assertEqual({'one.md'}, {f['path'] for f in result['findings']})

    def test_flat_context_reads_explicit_link_without_scaffold_dependencies(self):
        self.write('one.md', '# One\n[World](world.md)\n')
        self.write('world.md', '# World\n')
        _, result = self.run_cli('context', 'chapter', 'one.md')
        rendered = json.dumps(result)
        self.assertIn('world.md', rendered)
        self.assertNotIn('kb/continuity', rendered)
        self.assertEqual({'one.md', 'world.md'}, {p.name for p in self.root.iterdir()})

    def test_recursive_tagged_continuity_checks_explicit_anchor_conflict(self):
        self.write('.cws-layout.json', json.dumps({'version': 2, 'bindings': [{'path': 'notes', 'kind': 'directory', 'tags': ['continuity']}]}))
        self.write('notes/volumes/events.md', '| When | Event | Threads | Anchor | Chapter |\n| --- | --- | --- | --- | --- |\n| Day 1 | A | arc | same | 1 |\n| Day 2 | B | arc | same | 2 |\n')
        _, result = self.run_cli('check', 'continuity', '.')
        self.assertTrue(any('anchor' in f['message'] and f['path'] == 'notes/volumes/events.md' for f in result['findings']))
        self.assertFalse(any('kb/' in str(f) for f in result['findings']))
