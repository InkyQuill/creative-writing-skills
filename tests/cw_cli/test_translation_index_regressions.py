from .translation_helpers import TranslationFixture, md
from cwcli.indexes import plan_reindex
from cwcli.transactions import Change


class TranslationIndexRegressions(TranslationFixture):
    def test_new_project_indexes_are_already_current(self):
        self.assertEqual((), plan_reindex(self.project).changes)

    def test_generated_overlay_is_not_indexed_as_authored_content(self):
        self.edition()
        overlay = [Change('sources/_index.md', None, md({'generated': True}))]
        changes = plan_reindex(self.project, overlay=overlay).changes
        source_index = next(c for c in changes if c.path == 'sources/_index.md')
        self.assertNotIn(b'`sources/_index.md`', source_index.after)
        self.assertIn(b'`sources/ja/edition.md`', source_index.after)

    def test_index_selection_accepts_generator_and_rejects_duplicates(self):
        self.edition()
        plan = plan_reindex(self.project, index_ids=iter(['sources/_index.md']))
        self.assertEqual(['sources/_index.md'], [c.path for c in plan.changes])
        with self.assertRaises(ValueError):
            plan_reindex(self.project, index_ids=['sources/_index.md', 'sources/_index.md'])

    def test_skip_unparseable_disk_record_keeps_valid_records(self):
        self.edition()
        bad = self.root / 'kb/entities/bad.md'
        bad.write_bytes(b'\xff')
        with self.assertRaises(ValueError):
            plan_reindex(self.project)
        plan = plan_reindex(self.project, skip_unparseable=True)
        self.apply(plan)
        self.assertIn('sources/ja/edition.md', (self.root / 'sources/_index.md').read_text())
        self.assertNotIn('bad.md', (self.root / 'kb/entities/_index.md').read_text())

    def test_skip_unparseable_overlay_removes_old_entry(self):
        self.edition()
        path = 'sources/ja/edition.md'
        overlay = [Change(path, (self.root / path).read_bytes(), b'\xff')]
        plan = plan_reindex(self.project, overlay=overlay, skip_unparseable=True)
        self.apply(plan)
        self.assertNotIn(path, (self.root / 'sources/_index.md').read_text())

    def test_authoring_overlay_generator_updates_legacy_index(self):
        from cwcli.scaffold import apply_init
        from cwcli.project import discover_project
        from cwcli.translation.commands import plan_enable
        from cwcli.transactions import TransactionEngine
        root = self.root.parent / 'author'
        apply_init(root, 'Author', 'ja')
        project = discover_project(root)
        TransactionEngine(project).apply(plan_enable(project, 'series'))
        project = discover_project(root)
        overlay = (c for c in [Change('story/chapters/one.md', None, md({'number': 1, 'title': 'Arrival', 'status': 'draft'}))])
        plan = plan_reindex(project, overlay=overlay)
        index = next(c for c in plan.changes if c.path == 'story/chapters/_index.md')
        self.assertIn(b'Arrival', index.after)
        (root / 'story/chapters/one.md').write_bytes(md({'number': 1, 'title': 'Arrival', 'status': 'draft'}))
        TransactionEngine(project).apply(plan)
        self.assertEqual((), plan_reindex(project, index_ids=iter(['story/chapters/_index.md'])).changes)
