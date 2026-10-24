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

    def test_tagged_knowledge_accepts_draft_path_and_author_citation(self):
        self.write('.cws-layout.json', json.dumps({'version': 2, 'bindings': [{'path': 'notes.md', 'kind': 'file', 'tags': ['kb']}]}))
        self.write('notes.md', '---\nsources:\n  - drafts/chapter.md\n  - "note:Author confirmed the name"\n---\nNotes\n')
        self.write('drafts/chapter.md', '# Draft\n')
        before = self.snapshot()
        code, result = self.run_cli('check', 'kb', '.', '--strict')
        self.assertEqual(0, code, result)
        self.assertFalse(any(f['code'] == 'CW-KB-030' for f in result['findings']))
        self.assertTrue(any('unverified' in f['message'] for f in result['findings']))
        self.assertEqual(before, self.snapshot())

    def test_flat_managed_draft_accept_and_undo_without_layout_file(self):
        self.write('one.md', 'Base\n')
        before = self.snapshot()
        code, preview = self.run_cli('draft', 'create', 'one.md', '--draft-path', 'revision.md')
        self.assertEqual(0, code, preview)
        self.assertEqual(before, self.snapshot())
        code, created = self.run_cli('draft', 'create', 'one.md', '--draft-path', 'revision.md', '--apply')
        self.assertEqual(0, code, created)
        self.run_cli('draft', 'rebase', 'revision.md')
        self.run_cli('draft', 'set-status', 'revision.md', 'ready', '--apply')
        self.run_cli('draft', 'accept', 'revision.md', '--archive-path', 'old-revision.md')
        code, accepted = self.run_cli('draft', 'accept', 'revision.md', '--archive-path', 'old-revision.md', '--apply')
        self.assertEqual(0, code, accepted)
        self.assertFalse((self.root / 'revision.md').exists())
        self.assertTrue((self.root / 'old-revision.md').exists())
        self.run_cli('undo', accepted['transaction_id'], '--apply')
        self.assertEqual(b'Base\n', (self.root / 'one.md').read_bytes())
        self.assertTrue((self.root / 'revision.md').exists())
        self.assertFalse((self.root / 'old-revision.md').exists())
        self.assertFalse((self.root / '.cws-layout.json').exists())
        for directory in ('kb', 'story', 'work'):
            self.assertFalse((self.root / directory).exists())

    def test_opaque_metadata_body_edit_preserves_header_and_undo(self):
        from cwcli.edits import plan_edits
        from cwcli.project import open_workspace
        from cwcli.transactions import TransactionEngine
        raw = b'\xef\xbb\xbf---\r\ntags: [a, b]\r\n---\r\nBefore.\r\n'
        (self.root / 'one.md').write_bytes(raw)
        project = open_workspace(self.root)
        plan = plan_edits(project, [{'op': 'replace', 'path': 'one.md', 'old': 'Before.', 'new': 'After.'}])
        self.assertEqual(raw.replace(b'Before.', b'After.'), plan.changes[0].after)
        engine = TransactionEngine(project)
        record = engine.apply(plan)
        self.run_cli('undo', record.id, '--apply')
        self.assertEqual(raw, (self.root / 'one.md').read_bytes())

    def test_reindex_preserves_authored_index_and_requires_explicit_output(self):
        self.write('_index.md', '# My own contents\n')
        self.write('one.md', '# One\n')
        before = self.snapshot()
        self.run_cli('reindex')
        self.assertEqual(before, self.snapshot())
        code, result = self.run_cli('reindex', '--index', 'contents.md', '--apply')
        self.assertEqual(0, code, result)
        self.assertIn('one.md', (self.root / 'contents.md').read_text())
        self.assertEqual(b'# My own contents\n', (self.root / '_index.md').read_bytes())

    def test_kb_tag_does_not_prohibit_provisional_ai_material(self):
        self.write('.cws-layout.json', json.dumps({'version': 2, 'bindings': [{'path': '.', 'kind': 'directory', 'tags': ['world', 'kb']}]}))
        self.write('idea.md', '<AI>A proposed city.</AI>\n')
        code, result = self.run_cli('check', 'prose', '.', '--strict')
        self.assertEqual(0, code, result)
        self.assertFalse(any('not allowed' in f['message'] for f in result['findings']))

    def test_tagged_nested_chapters_contribute_context_neighbors(self):
        self.write('.cws-layout.json', json.dumps({'version': 2, 'bindings': [{'path': 'text', 'kind': 'directory', 'tags': ['chapters']}]}))
        self.write('text/vol1/a.md', '---\nnumber: 1\n---\nA\n')
        self.write('text/vol2/b.md', '---\nnumber: 2\n---\nB\n')
        _, result = self.run_cli('context', 'chapter', 'text/vol2/b.md')
        self.assertIn('text/vol1/a.md', json.dumps(result))

    def test_opaque_context_reads_body_without_rewriting_metadata(self):
        self.write('one.md', '---\ntags: [a, b]\n---\nVisible.\n<hidden>Secret.</hidden>\n')
        before = self.snapshot()
        code, result = self.run_cli('context', 'chapter', 'one.md', '--as', 'reader')
        self.assertEqual(0, code, result)
        self.assertEqual(before, self.snapshot())

    def test_malformed_tag_config_returns_json_error_without_traceback(self):
        self.write('.cws-layout.json', '{broken')
        self.write('one.md', 'Text')
        out, err = io.StringIO(), io.StringIO()
        code = app.run(['check', 'all', '.', '--format', 'json'], cwd=self.root, stdout=out, stderr=err)
        self.assertEqual(2, code)
        self.assertTrue(json.loads(out.getvalue())['execution_errors'])
        self.assertEqual('', err.getvalue())

    def test_explicit_link_target_cannot_enter_tag_marked_nested_project(self):
        self.write('one.md', '[Other](nested/other.md)\n')
        self.write('nested/.cws-layout.json', '{"version":2,"bindings":[]}')
        self.write('nested/other.md', 'Text')
        _, result = self.run_cli('check', 'links', 'one.md')
        self.assertTrue(result['findings'])
