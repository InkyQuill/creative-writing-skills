import io
import json
import tempfile
import unittest
from pathlib import Path

from tests.cw_cli import helpers  # noqa: F401
from cwcli import app
from cwcli.documents import parse_document
from cwcli.project import Project


class CatalogTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.project = Project(self.root, parse_document(b'---\nschema-version: 1\ntitle: Story\nlanguage: en\n---\n'))
        (self.root / 'project.md').write_bytes(b'---\nschema-version: 1\ntitle: Story\nlanguage: en\n---\n')

    def config(self, bindings, destinations=None):
        data = {'version': 2, 'bindings': bindings, 'destinations': destinations or {}}
        (self.root / '.cws-layout.json').write_text(json.dumps(data))

    def tags(self, path):
        from cwcli.catalog import effective_tags, read_layout
        return effective_tags(read_layout(self.project), path)

    def test_root_tag_inherits_into_nested_files(self):
        self.config([{'path': '.', 'kind': 'directory', 'tags': ['drafts']}])
        self.assertEqual({'drafts'}, self.tags('volumes/一/chapter.md'))

    def test_file_override_removes_inherited_draft_tag(self):
        self.config([
            {'path': '.', 'kind': 'directory', 'tags': ['drafts']},
            {'path': 'world.md', 'kind': 'file', 'tags': ['kb', 'world'], 'remove': ['drafts']},
        ])
        self.assertEqual({'kb', 'world'}, self.tags('world.md'))
        self.assertEqual({'drafts'}, self.tags('chapter.md'))

    def test_multiple_folders_and_tags_are_valid(self):
        self.config([{'path': p, 'kind': 'directory', 'tags': ['kb', 'world']} for p in ('notes', 'research')])
        self.assertEqual({'kb', 'world'}, self.tags('notes/places/city.md'))
        self.assertEqual({'kb', 'world'}, self.tags('research/a.md'))

    def test_custom_tag_round_trips(self):
        self.config([{'path': '.', 'kind': 'directory', 'tags': ['my-purpose']}])
        from cwcli.catalog import read_layout, render_config
        before = (self.root / '.cws-layout.json').read_bytes()
        encoded = json.loads(render_config(read_layout(self.project)))
        self.assertEqual(['my-purpose'], encoded['bindings'][0]['tags'])
        self.assertEqual(before, (self.root / '.cws-layout.json').read_bytes())

    def test_v1_read_preserves_bytes_and_role_results(self):
        from cwcli.catalog import read_layout, effective_tags
        original = b'{"version":1,"roles":{"chapters":"text"}}\n'
        (self.root / '.cws-layout.json').write_bytes(original)
        self.assertEqual({'chapters'}, effective_tags(read_layout(self.project), 'text/one.md'))
        self.assertEqual(original, (self.root / '.cws-layout.json').read_bytes())

    def test_invalid_bindings_rejected(self):
        from cwcli.catalog import read_layout
        for bindings in (
            [{'path': '../outside', 'kind': 'directory', 'tags': ['kb']}],
            [{'path': '.', 'kind': 'directory', 'tags': ['kb'], 'remove': ['kb']}],
            [{'path': '.', 'kind': 'directory', 'tags': ['kb']}] * 2,
        ):
            with self.subTest(bindings=bindings):
                self.config(bindings)
                with self.assertRaises(ValueError):
                    read_layout(self.project)

    def test_destinations_are_explicit_or_unambiguous(self):
        from cwcli.catalog import resolve_destination
        self.config([{'path': p, 'kind': 'directory', 'tags': ['reviews']} for p in ('a', 'b')])
        with self.assertRaises(ValueError):
            resolve_destination(self.project, 'reviews')
        self.config([], {'reviews': '.'})
        self.assertEqual('.', resolve_destination(self.project, 'reviews'))

    def test_tag_preview_apply_and_undo(self):
        def run(args):
            out, err = io.StringIO(), io.StringIO()
            status = app.run(args + ['--format', 'json'], cwd=self.root, stdout=out, stderr=err)
            self.assertEqual(0, status, out.getvalue() + err.getvalue())
            return json.loads(out.getvalue())
        run(['layout', 'tag', '.', '--kind', 'directory', '--add', 'drafts'])
        self.assertFalse((self.root / '.cws-layout.json').exists())
        result = run(['layout', 'tag', '.', '--kind', 'directory', '--add', 'drafts', '--apply'])
        self.assertEqual({'drafts'}, self.tags('a.md'))
        run(['undo', result['transaction_id'], '--apply'])
        self.assertFalse((self.root / '.cws-layout.json').exists())
        self.assertFalse((self.root / 'story').exists())

    def test_upgrade_materializes_existing_roles_without_duplicate_bindings(self):
        (self.root / '.cws-layout.json').write_text(json.dumps({'version': 1, 'roles': {'world': 'notes', 'characters': 'notes'}}))
        for folder in ('notes', 'chapters'):
            (self.root / folder).mkdir()
            (self.root / folder / 'one.md').write_text('Text')
        out = io.StringIO()
        status = app.run(['layout', 'tag', 'extras', '--kind', 'directory', '--add', 'reviews', '--apply', '--format', 'json'], cwd=self.root, stdout=out, stderr=io.StringIO())
        self.assertEqual(0, status, out.getvalue())
        self.assertEqual({'world', 'characters'}, self.tags('notes/one.md'))
        self.assertEqual({'chapters'}, self.tags('chapters/one.md'))

    def test_removed_tag_is_not_a_destination(self):
        from cwcli.catalog import read_layout, tagged_directories
        self.config([
            {'path': '.', 'kind': 'directory', 'tags': ['reviews']},
            {'path': 'notes', 'kind': 'directory', 'tags': ['kb']},
        ])
        self.assertEqual(('.',), tagged_directories(read_layout(self.project), 'reviews'))
