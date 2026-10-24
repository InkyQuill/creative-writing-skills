import tempfile
import unittest
from pathlib import Path
from tests.cw_cli import helpers  # noqa: F401
from cwcli.project import open_workspace


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.project = open_workspace(self.root)

    def resolve(self, source):
        from cwcli.provenance import resolve_source
        return resolve_source(self.project, source)

    def test_identical_sources_resolve_in_every_layout(self):
        for name in ('chapter.md', 'chapters/one.md', 'drafts/one.md', 'story/side-stories/one.md', 'kb/world/one.md', 'notes/image.png'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'Text' if name.endswith('.md') else b'\x89PNG\xff')
            result = self.resolve(name)
            self.assertEqual('resolved', result.resolution, name)
            self.assertEqual('unknown', result.authority, name)

    def test_descriptions_are_unverified_not_missing_files(self):
        for source in ('The author confirmed the city name today', 'Author: the city is called Dawn', 'note:Conversation about chapter 3'):
            result = self.resolve(source)
            self.assertEqual('description', result.kind)
            self.assertEqual('unverified', result.resolution)
            self.assertEqual('unknown', result.authority)
        self.assertEqual('missing', self.resolve('missing.md').resolution)
        self.assertEqual('missing', self.resolve('file:missing').resolution)

    def test_url_is_not_claimed_to_be_verified(self):
        self.assertEqual('unverified', self.resolve('https://example.com/%FF').resolution)
        self.assertEqual('malformed', self.resolve('https://').resolution)

    def test_explicit_status_is_separate_from_resolution(self):
        for status, expected in [('archived', 'archived'), ('accepted', 'accepted'), ('working', 'provisional')]:
            (self.root / 'note.md').write_text(f'---\nstatus: {status}\n---\n')
            result = self.resolve('note.md')
            self.assertEqual('resolved', result.resolution)
            self.assertEqual(expected, result.authority)

    def test_opaque_metadata_does_not_break_reference_resolution(self):
        (self.root / 'note.md').write_text('---\ntags: [a]\n---\nText')
        result = self.resolve('note.md')
        self.assertEqual('resolved', result.resolution)
        self.assertEqual('unknown', result.authority)

    def test_unsafe_paths_and_receipts_are_not_resolved(self):
        (self.root / 'nested').mkdir()
        (self.root / 'nested/.cws-layout.json').write_text('{}')
        (self.root / 'nested/a.md').write_text('text')
        (self.root / 'linked.md').symlink_to(self.root / 'nested/a.md')
        for path in ('../escape.md', '%2e%2e/escape.md', 'linked.md', 'nested/a.md', '.creative-writing/context.sqlite3', 'bad%00.md'):
            self.assertEqual('unsafe', self.resolve(path).resolution, path)
        self.assertNotEqual('resolved', self.resolve('decision:missing').resolution)
        self.assertFalse((self.root / '.creative-writing').exists())
