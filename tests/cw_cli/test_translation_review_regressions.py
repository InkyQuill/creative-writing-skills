"""Regressions for translation review: scoped rules and transactional acceptance."""
from .translation_helpers import TranslationFixture, md
from cwcli.translation.directions import plan_direction
from cwcli.translation.memory import plan_memory, select_memory
from cwcli.translation.context import build_packet
from cwcli.translation.drafts import plan_translation_draft, plan_translation_accept, plan_translation_status, translation_status
from cwcli.transactions import TransactionConflict
from cwcli.checks.translation import check_translation


class TranslationReviewRegressions(TranslationFixture):
    def setUp(self):
        super().setUp()
        self.edition()
        self.unit()
        self.unit('u002')
        self.apply(plan_direction(self.project, md({'direction-id': 'ru', 'language': 'ru', 'primary-edition': 'ja', 'coverage': ['v001']})))

    def save_rule(self, name, kind='voices', **extra):
        return self.apply(plan_memory(self.project, 'ru', kind, md({'record-id': name, 'status': 'accepted', 'subject': 'hero', 'evidence': ['user: voice'], **extra})))

    def reviewed_draft(self, name):
        packet = build_packet(self.project, 'ru', ('ja:u001',), {})
        self.apply(plan_translation_draft(self.project, 'ru', name, packet, b'Translation.'))
        path = f'translations/ru/volumes/v001/drafts/{name}.md'
        self.apply(plan_translation_status(self.project, path, 'reviewed'))
        return path

    def test_batch_keeps_general_rule_and_explains_exception_scope(self):
        self.save_rule('general')
        self.save_rule('exception', supersedes='general', **{'scope-units': ['ja:u001']})
        packet = build_packet(self.project, 'ru', ('ja:u001', 'ja:u002'), {})
        rules = {r['path']: r for r in packet['rules']}
        self.assertEqual({'translations/ru/memory/voices/general.md', 'translations/ru/memory/voices/exception.md'}, set(rules))
        self.assertEqual(['ja:u001'], rules['translations/ru/memory/voices/exception.md']['scope']['scope-units'])
        self.assertEqual('general', rules['translations/ru/memory/voices/exception.md']['supersedes'])

    def test_disjoint_rules_for_same_subject_are_valid_in_batch(self):
        self.save_rule('first', **{'scope-units': ['ja:u001']})
        self.save_rule('second', **{'scope-units': ['ja:u002']})
        self.assertEqual(2, len(select_memory(self.project, 'ru', {'scope-units': ['ja:u001', 'ja:u002']})))

    def test_style_identity_cannot_be_replaced(self):
        self.save_rule('style-old', kind='style')
        path = self.root / 'translations/ru/memory/style.md'
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            self.save_rule('style-new', kind='style')
        self.assertEqual(before, path.read_bytes())

    def test_prepared_accepts_cannot_duplicate_source_coverage(self):
        accepted = self.root / 'translations/ru/volumes/v001/accepted'
        accepted.mkdir(parents=True, exist_ok=True)
        paths = [self.reviewed_draft(name) for name in ('a', 'b')]
        plans = [plan_translation_accept(self.project, p) for p in paths]
        self.apply(plans[0])
        with self.assertRaises(TransactionConflict):
            self.apply(plans[1])
        self.assertFalse((accepted / 'b.md').exists())
        self.assertEqual('reviewed', translation_status(self.project, paths[1])['status'])

    def test_missing_draft_status_is_diagnostic_and_checker_continues(self):
        path = self.reviewed_draft('a')
        target = self.root / path
        target.write_text('\n'.join(line for line in target.read_text().split('\n') if not line.startswith('status:')))
        with self.assertRaises(ValueError):
            translation_status(self.project, path)
        findings = check_translation(self.project)
        self.assertTrue(any(f.code == 'CW-TRANS-011' and f.path == path for f in findings))
        self.assertTrue(any(f.code == 'CW-TRANS-020' for f in findings))

    def test_volume_override_outside_direction_coverage_is_rejected(self):
        with self.assertRaises(ValueError):
            plan_direction(self.project, md({'direction-id': 'ru', 'volume-id': 'v002', 'primary-edition': 'ja'}))

    def test_missing_primary_edition_is_reported_without_losing_other_findings(self):
        path = self.root / 'translations/ru/translation.md'
        path.write_bytes(md({'direction-id': 'ru', 'language': 'ru', 'coverage': ['v001']}))
        self.apply(plan_direction(self.project, md({'direction-id': 'en', 'language': 'en', 'primary-edition': 'ja', 'coverage': ['v001']})))
        findings = check_translation(self.project)
        self.assertTrue(any(f.code == 'CW-TRANS-002' for f in findings))
        self.assertTrue(any(f.code == 'CW-TRANS-020' and f.path == 'translations/en/translation.md' for f in findings))

    def test_source_fields_reject_non_text_values(self):
        from cwcli.translation.sources import plan_source
        for value in (None, 42, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                plan_source(self.project, {'action': 'edition', 'content': value})
            with self.subTest(manuscript=value), self.assertRaises(ValueError):
                plan_source(self.project, {'action': 'manuscript-unit', 'edition': 'ja', 'unit': 'new', 'volume': 'v001', 'manuscript-path': value})

    def test_migrate_malformed_manifest_returns_structured_error(self):
        import io
        import json
        from cwcli.app import run
        (self.root / 'project.md').write_bytes(b'\xff')
        out, err = io.StringIO(), io.StringIO()
        code = run(['migrate', '--plan', '--format', 'json'], cwd=self.root, stdout=out, stderr=err)
        self.assertNotEqual(0, code)
        self.assertIsInstance(json.loads(out.getvalue()), dict)

    def test_checker_scans_catalog_once_and_observes_changes_on_next_run(self):
        from unittest.mock import patch
        from cwcli.project import Project
        self.reviewed_draft('a')
        self.reviewed_draft('b')
        scans = []
        original = Project.iter_managed_markdown
        def tracked(project):
            scans.append(project.root)
            return original(project)
        with patch.object(Project, 'iter_managed_markdown', tracked):
            findings = check_translation(self.project)
        self.assertFalse(any(f.code == 'CW-TRANS-010' for f in findings))
        self.assertEqual(1, len(scans))
        self.save_rule('new')
        self.assertEqual(2, sum(f.code == 'CW-TRANS-010' for f in check_translation(self.project)))

    def test_invalid_accepted_units_do_not_abort_checker(self):
        path = self.root / 'translations/ru/volumes/v001/accepted/bad.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(md({'direction-id': 'ru', 'source-units': 42}))
        findings = check_translation(self.project)
        self.assertTrue(any(f.path.endswith('bad.md') and f.severity == 'error' for f in findings))
        self.assertTrue(any(f.code == 'CW-TRANS-020' for f in findings))

    def test_context_catalog_scans_do_not_grow_per_selected_unit(self):
        from unittest.mock import patch
        from cwcli.project import Project
        self.unit('u003')
        scans = []
        original = Project.iter_managed_markdown
        def tracked(project):
            scans.append(project.root)
            return original(project)
        with patch.object(Project, 'iter_managed_markdown', tracked):
            packet = build_packet(self.project, 'ru', ('ja:u001', 'ja:u002', 'ja:u003'), {})
        self.assertEqual(3, len(packet['primary-text']))
        self.assertLessEqual(len(scans), 2)
