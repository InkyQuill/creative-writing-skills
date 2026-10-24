import tempfile
import unittest
from pathlib import Path
from tests.cw_cli import helpers  # noqa: F401
from cwcli import project, documents


class WorkspaceScopeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_manifestless_root_is_usable_without_writes(self):
        (self.root / 'chapter.md').write_text('# One\n')
        workspace = project.open_workspace(self.root)
        self.assertEqual({}, workspace.metadata)
        self.assertIsNone(workspace.manifest)
        self.assertEqual(['chapter.md'], [workspace.relative_id(p) for p in workspace.iter_managed_markdown()])
        self.assertEqual(['chapter.md'], sorted(p.name for p in self.root.iterdir()))

    def test_tag_marker_selects_nearest_workspace(self):
        (self.root / '.cws-layout.json').write_text('{"version":2,"bindings":[]}')
        child = self.root / 'nested'
        child.mkdir()
        workspace = project.open_workspace(child)
        self.assertEqual(self.root, workspace.root)

    def test_explicit_root_overrides_ancestor_marker(self):
        (self.root / 'project.md').write_text('---\nschema-version: 1\n---\n')
        child = self.root / 'book'
        child.mkdir()
        self.assertEqual(child, project.open_workspace(child, root=child).root)

    def test_inventory_excludes_hidden_symlink_and_nested_projects(self):
        for folder in ('visible', '.private', 'other'):
            (self.root / folder).mkdir()
            (self.root / folder / 'one.md').write_text('text')
        (self.root / 'other/.cws-layout.json').write_text('{"version":2,"bindings":[]}')
        (self.root / 'linked').symlink_to(self.root / 'visible', target_is_directory=True)
        workspace = project.open_workspace(self.root)
        self.assertEqual(['visible/one.md'], [workspace.relative_id(p) for p in workspace.iter_managed_markdown()])

    def test_explicit_file_scope_does_not_read_siblings(self):
        from cwcli.catalog import iter_documents
        for name in ('one.md', 'two.md', '.private.md'):
            (self.root / name).write_text('text')
        workspace = project.open_workspace(self.root)
        self.assertEqual(['one.md'], [p.name for p in iter_documents(workspace, target='one.md')])
        self.assertEqual(['.private.md'], [p.name for p in iter_documents(workspace, target='.private.md')])

    def test_opaque_metadata_preserves_body_and_bytes(self):
        raw = b'\xef\xbb\xbf---\r\ntags: [a, b]\r\n---\r\nHello.\r\n'
        result = documents.read_document(raw)
        self.assertEqual(raw, result.raw)
        self.assertEqual('Hello.\r\n', result.body)
        self.assertIsNone(result.document)
        self.assertIsNotNone(result.metadata_error)

    def test_unknown_body_boundary_and_invalid_utf8_are_honest(self):
        for raw in (b'---\ntags: [a]\ntext', b'\xff'):
            result = documents.read_document(raw)
            self.assertEqual(raw, result.raw)
            self.assertIsNone(result.body)
            self.assertIsNotNone(result.metadata_error)
