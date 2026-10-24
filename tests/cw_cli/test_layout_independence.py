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
        checked, result = self.run_cli('check', 'drafts', '.', '--strict')
        self.assertEqual(0, checked, result)
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

    def test_manifest_in_flat_project_does_not_require_legacy_scaffold(self):
        self.write('project.md', '---\nschema-version: 1\ntitle: Flat\nlanguage: en\n---\n')
        self.write('chapter.md', '[missing](absent.md)\n')
        _, result = self.run_cli('check', 'all', '.', '--strict')
        self.assertTrue(any(f['code'] == 'CW-LINK-010' for f in result['findings']))
        self.assertFalse(any(f['code'] == 'CW-STRUCT-010' for f in result['findings']))
        self.assertFalse((self.root / 'kb').exists())

    def test_context_resolves_file_citations_and_ignores_descriptions(self):
        self.write('chapter.md', '---\nsources:\n  - file:world.md\n  - note:Author conversation\n---\nText\n')
        self.write('world.md', 'World\n')
        _, result = self.run_cli('context', 'chapter', 'chapter.md')
        rendered = json.dumps(result)
        self.assertIn('world.md', rendered)
        self.assertNotIn('unsupported', rendered)
        self.assertNotIn('invalid explicit reference', rendered)

    def test_archived_continuity_is_not_automatically_current_context(self):
        self.write('.cws-layout.json', json.dumps({'version': 2, 'bindings': [{'path': 'old.md', 'kind': 'file', 'tags': ['continuity', 'archive']}]}))
        self.write('chapter.md', 'Text\n')
        self.write('old.md', 'Old state\n')
        _, result = self.run_cli('context', 'chapter', 'chapter.md')
        self.assertNotIn('old.md', json.dumps(result))

    def test_explicit_historical_reference_can_select_archive(self):
        self.write('.cws-layout.json', json.dumps({'version': 2, 'bindings': [{'path': 'old.md', 'kind': 'file', 'tags': ['continuity', 'archive']}]}))
        self.write('chapter.md', '---\nsources:\n  - file:old.md\n---\nText\n')
        self.write('old.md', 'Old state\n')
        _, result = self.run_cli('context', 'chapter', 'chapter.md')
        self.assertIn('old.md', result['required'])

    def test_abandoned_flat_archive_is_not_an_active_draft(self):
        self.write('one.md', 'Base\n')
        self.run_cli('draft', 'create', 'one.md', '--draft-path', 'revision.md', '--apply')
        self.run_cli('draft', 'abandon', 'revision.md', '--archive-path', 'old.md', '--apply')
        code, result = self.run_cli('check', 'drafts', '.', '--strict')
        self.assertEqual(0, code, result)

    def test_reindex_does_not_claim_generated_author_notes(self):
        self.write('notes.md', '---\ngenerated: true\n---\nAuthor-owned generated notes.\n')
        before = (self.root / 'notes.md').read_bytes()
        self.run_cli('reindex', '--apply')
        self.assertEqual(before, (self.root / 'notes.md').read_bytes())
        self.run_cli('reindex', '--index', 'contents.md', '--apply')
        self.write('new.md', 'New\n')
        self.run_cli('reindex', '--apply')
        self.assertIn('new.md', (self.root / 'contents.md').read_text())

    def test_root_citations_are_malformed_without_crashing_context(self):
        from cwcli.provenance import resolve_source
        from cwcli.project import open_workspace
        self.write('chapter.md', '---\nrelated: ./\n---\nText\n')
        project = open_workspace(self.root)
        for value in ('./', 'file:.', 'file:./'):
            self.assertEqual('malformed', resolve_source(project, value).resolution)
        code, result = self.run_cli('context', 'chapter', 'chapter.md')
        self.assertEqual(0, code, result)

    def test_manifest_is_not_prose_or_an_index_entry(self):
        self.write('project.md', '---\nschema-version: 1\nlanguage: en\n---\n')
        self.write('chapter.md', 'Hello world.\n')
        _, result = self.run_cli('check', 'prose', '.')
        self.assertFalse(any(f['path'] == 'project.md' for f in result['findings']))
        self.run_cli('reindex', '--index', 'contents.md', '--apply')
        self.assertNotIn('project.md', (self.root / 'contents.md').read_text())

    def test_omitted_scope_checks_project_but_explicit_dot_checks_subdirectory(self):
        self.write('project.md', '---\nschema-version: 1\nlanguage: en\n---\n')
        self.write('one.md', '[broken](missing.md)\n')
        self.write('nested/two.md', 'Fine\n')
        for scope, expected in (([], True), (['.'], False)):
            out = io.StringIO()
            app.run(['check', 'links', *scope, '--format', 'json'], cwd=self.root / 'nested', stdout=out, stderr=io.StringIO())
            self.assertEqual(expected, any(f['path'] == 'one.md' for f in json.loads(out.getvalue())['findings']))

    def test_selected_managed_file_does_not_claim_orphan_status(self):
        self.write('project.md', '---\nschema-version: 1\n---\n')
        self.write('story/chapters/one.md', 'One\n')
        self.write('story/chapters/two.md', '[One](one.md)\n')
        _, result = self.run_cli('check', 'links', 'story/chapters/one.md')
        self.assertFalse(any(f['code'] == 'CW-LINK-030' for f in result['findings']))

    def test_unreadable_structure_file_does_not_stop_remaining_files(self):
        from unittest.mock import patch
        from cwcli.project import open_workspace
        from cwcli.checks.structure import check_structure
        self.write('one.md', 'One\n')
        self.write('two.md', '---\nunclosed')
        original = Path.read_bytes
        def read(path):
            if path.name == 'one.md':
                raise PermissionError('unreadable')
            return original(path)
        with patch.object(Path, 'read_bytes', read):
            project = open_workspace(self.root)
            findings = check_structure(project)
            from cwcli.checks import run_checks
            report = run_checks(project, ['structure'])
        self.assertEqual([], report.execution_errors)
        self.assertEqual({'one.md', 'two.md'}, {f.path for f in findings})

    def test_layout_cache_is_local_and_refreshes_after_configuration_changes(self):
        from unittest.mock import patch
        from cwcli.catalog import read_layout
        from cwcli.project import open_workspace
        from cwcli import catalog
        self.write('.cws-layout.json', '{"version":2,"bindings":[]}')
        project = open_workspace(self.root)
        with patch.object(catalog, '_read_layout', wraps=catalog._read_layout) as read:
            first = read_layout(project)
            self.assertIs(first, read_layout(project))
            self.assertEqual(1, read.call_count)
            self.assertIsNot(first, read_layout(open_workspace(self.root)))
            self.assertEqual(2, read.call_count)
            self.write('.cws-layout.json', '{"version":2,"bindings":[{"path":".","kind":"directory","tags":["kb"]}]}')
            self.assertEqual({'kb'}, read_layout(project).bindings[0].tags)
            self.assertEqual(3, read.call_count)
