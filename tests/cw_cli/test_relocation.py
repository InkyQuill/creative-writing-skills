import io
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from tests.cw_cli import helpers  # noqa: F401
from cwcli import app
from cwcli.project import discover_project
from cwcli.relocation import plan_relocation, _rewrite_paths
from cwcli.transactions import TransactionEngine, TransactionConflict, TransactionError


class RelocationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.write("project.md", b"---\nschema-version: 1\ntitle: Story\nlanguage: ru\nstatus: drafting\n---\n")
        self.write("work/drafts/one.md", b'---\ntitle: Draft\nstatus: working\ntarget: story/chapters/one.md\n---\n![Mara](../../kb/characters/mara.png)\n')
        self.write("kb/characters/mara.md", b'---\ntitle: Mara\nstatus: active\n---\n[Draft](../../work/drafts/one.md#scene)\n')
        self.write("kb/characters/mara.png", b'\x89PNG\x00\xff')
        self.write("work/drafts/one.md.review.json", b'{"hash":"original","selection":"do not change"}\r\n')
        self.write("work/drafts/_index.md", b'---\ngenerated: true\n---\n# Old\n')
        self.write("kb/characters/_index.md", b'---\ngenerated: true\n---\n# Old\n')
        self.write("notes.md", b'[Mara](kb/characters/mara.md)\n[ref]: work/drafts/one.md#scene\n')
        self.write("author.binder.json", b'{"path":"work/drafts/one.md"}\n')

    def write(self, path, data):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def plan(self):
        return plan_relocation(discover_project(self.root), {"drafts": "drafts", "characters": "characters"})

    def test_preview_apply_and_exact_undo(self):
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        dirs = {p.relative_to(self.root).as_posix() for p in self.root.rglob('*') if p.is_dir()}
        engine = TransactionEngine(discover_project(self.root))
        plan = self.plan()
        engine.preview(plan)
        self.assertFalse((self.root / '.creative-writing').exists())
        record = engine.apply(plan)
        self.assertFalse((self.root / 'work/drafts').exists())
        self.assertEqual(before['kb/characters/mara.png'], (self.root / 'characters/mara.png').read_bytes())
        self.assertEqual(before['work/drafts/one.md.review.json'], (self.root / 'drafts/one.md.review.json').read_bytes())
        self.assertIn(b'../characters/mara.png', (self.root / 'drafts/one.md').read_bytes())
        self.assertIn(b'status: working', (self.root / 'drafts/one.md').read_bytes())
        self.assertIn(b'../drafts/one.md#scene', (self.root / 'characters/mara.md').read_bytes())
        self.assertIn(b'characters/mara.md', (self.root / 'notes.md').read_bytes())
        self.assertIn(b'drafts/one.md#scene', (self.root / 'notes.md').read_bytes())
        self.assertIn(b'drafts/one.md', (self.root / 'author.binder.json').read_bytes())
        self.assertIn(b'`drafts/one.md`', (self.root / 'drafts/_index.md').read_bytes())
        output, errors = io.StringIO(), io.StringIO()
        status = app.run(['undo', record.id, '--apply', '--format', 'json'], cwd=self.root, stdout=output, stderr=errors)
        self.assertEqual(0, status, errors.getvalue() + output.getvalue())
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '.creative-writing' not in p.parts}
        self.assertEqual(before, after)
        self.assertEqual(dirs, {p.relative_to(self.root).as_posix() for p in self.root.rglob('*') if p.is_dir() and '.creative-writing' not in p.parts})

    def test_conflict_does_not_move_content(self):
        plan = self.plan()
        self.write('work/drafts/one.md', b'Author edit\n')
        with self.assertRaises(TransactionConflict):
            TransactionEngine(discover_project(self.root)).apply(plan)
        self.assertFalse((self.root / 'drafts').exists())

    def test_rejects_collisions_overlap_symlinks_and_nested_projects(self):
        for path, selections in [('drafts/existing.md', {'drafts': 'drafts'}), ('work/drafts/nested/project.md', {'drafts': 'drafts'})]:
            with self.subTest(path=path):
                self.write(path, b'# Existing\n')
                with self.assertRaises(ValueError):
                    plan_relocation(discover_project(self.root), selections)
                (self.root / path).unlink()
                (self.root / path).parent.rmdir()
        with self.assertRaises(ValueError):
            plan_relocation(discover_project(self.root), {'drafts': 'work/drafts/sub'})
        (self.root / 'work/drafts/link').symlink_to(self.root / 'notes.md')
        with self.assertRaises(ValueError):
            self.plan()

    def test_cli_requires_selections_and_supports_preview(self):
        for argv, expected in [(['layout', '--relocate'], 2), (['layout', '--relocate', '--set', 'drafts=drafts'], 0)]:
            output, errors = io.StringIO(), io.StringIO()
            status = app.run([*argv, '--format', 'json'], cwd=self.root, stdout=output, stderr=errors)
            self.assertEqual(expected, status, output.getvalue())
        self.assertFalse((self.root / 'drafts').exists())

    def test_install_failure_rolls_back_assets_and_directories(self):
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        engine = TransactionEngine(discover_project(self.root))
        original = engine._install_change
        calls = 0
        def fail_after_install(transaction_id, change):
            nonlocal calls
            calls += 1
            original(transaction_id, change)
            if calls == 4:
                raise OSError("simulated failure after installation")
        with mock.patch.object(engine, '_install_change', side_effect=fail_after_install):
            with self.assertRaises(TransactionError):
                engine.apply(self.plan())
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '.creative-writing' not in p.parts}
        self.assertEqual(before, after)
        self.assertFalse((self.root / 'drafts').exists())
        self.assertFalse((self.root / 'characters').exists())

    def test_chapter_move_updates_draft_target_without_accepting_draft(self):
        self.write('story/chapters/one.md', b'---\ntitle: One\nnumber: 1\nstatus: accepted\n---\n# One\n')
        plan = plan_relocation(discover_project(self.root), {'chapters': 'chapters'})
        TransactionEngine(discover_project(self.root)).apply(plan)
        self.assertIn(b'target: chapters/one.md', (self.root / 'work/drafts/one.md').read_bytes())
        self.assertIn(b'status: working', (self.root / 'work/drafts/one.md').read_bytes())

    def test_external_links_and_encoded_local_paths(self):
        self.write('kb/characters/mara image.png', b'opaque')
        self.write('notes.md', b'[Local](kb/characters/mara%20image.png#detail)\n[Web](https://example.com/kb/characters/mara.md)\n')
        TransactionEngine(discover_project(self.root)).apply(self.plan())
        self.assertEqual(b'[Local](characters/mara%20image.png#detail)\n[Web](https://example.com/kb/characters/mara.md)\n', (self.root / 'notes.md').read_bytes())

    def test_single_segment_folder_words_in_prose_remain_exact(self):
        prose = b'The characters meet. "characters" and `characters` are words.\r\n'
        self.assertEqual(prose, _rewrite_paths(prose, {'characters': 'people'}))
        self.write('characters/mara.md', b'---\ntitle: Mara\nstatus: active\n---\n' + prose)
        self.write('notes.md', prose + b'[Mara](characters/mara.md)\n[Folder](characters)\n`characters/mara.md`\n')
        self.write('.cws-layout.json', b'{"version":1,"roles":{"characters":"characters"}}\n')
        plan = plan_relocation(discover_project(self.root), {'characters': 'people'})
        TransactionEngine(discover_project(self.root)).apply(plan)
        self.assertTrue((self.root / 'people/mara.md').read_bytes().endswith(prose))
        self.assertEqual(prose + b'[Mara](people/mara.md)\n[Folder](people)\n`people/mara.md`\n', (self.root / 'notes.md').read_bytes())

    def test_multi_segment_folder_tokens_keep_end_delimiters(self):
        before = b'`work/drafts` "work/drafts" <work/drafts> (work/drafts)\nwork/drafts'
        self.assertEqual(b'`drafts` "drafts" <drafts> (drafts)\ndrafts',
                         _rewrite_paths(before, {'work/drafts': 'drafts'}))
