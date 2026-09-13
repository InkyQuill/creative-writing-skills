"""External task inputs stay distinct from live verification and local guards."""
import unittest
import copy
import io
import json
from dataclasses import asdict, replace
from unittest.mock import patch
from .translation_helpers import TranslationFixture, md
from cwcli.translation.external_memory import ExternalMemoryRef, assess_external_memory
from cwcli.translation.context import build_packet
from cwcli.translation.catalog import load_catalog
from cwcli.translation.directions import plan_direction
from cwcli.translation.drafts import plan_translation_draft, plan_translation_status, plan_translation_accept, translation_status
from cwcli.transactions import TransactionEngine, TransactionConflict, TransactionPlan, Change, _jsonable


REF = ExternalMemoryRef('hieronymus', 'instance-a/series-a', 'authority', 'series-a', '10')


class ExternalMemoryReferenceTests(unittest.TestCase):
    def test_freshness_requires_complete_matching_observations(self):
        self.assertEqual('unknown', assess_external_memory((REF,), None))
        self.assertEqual('current', assess_external_memory((REF,), (REF,)))
        self.assertEqual('needs-review', assess_external_memory((REF,), (replace(REF, revision='11'),)))
        self.assertEqual('current', assess_external_memory((), None))
        self.assertEqual('needs-review', assess_external_memory((REF,), ()))
        self.assertEqual('needs-review', assess_external_memory((REF,), (replace(REF, namespace='instance-b/series-a'),)))

    def test_all_fields_are_nonempty_strings(self):
        for field in asdict(REF):
            for bad in ('', '  ', None, 1, [], {}):
                with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                    replace(REF, **{field: bad})

    def test_conflicting_duplicates_are_invalid_before_comparison(self):
        conflict = replace(REF, revision='11')
        for captured, observed in (((REF, conflict), None), ((REF,), (REF, conflict)), ((), (REF, conflict))):
            with self.subTest(captured=captured, observed=observed), self.assertRaises(ValueError):
                assess_external_memory(captured, observed)
        self.assertEqual('current', assess_external_memory((REF, REF), (REF,)))

    def test_reference_values_must_be_validated_objects(self):
        with self.assertRaises(ValueError):
            assess_external_memory((asdict(REF),), None)


class ExternalMemoryPacketTests(TranslationFixture):
    def setUp(self):
        super().setUp()
        self.edition()
        self.unit()
        self.apply(plan_direction(self.project, md({'direction-id': 'ru', 'language': 'ru', 'primary-edition': 'ja', 'coverage': ['v001']})))
        self.selection = {'external-memory-refs': [asdict(REF)], 'excluded-file-memory': ['translations/ru/memory/']}
        self.path = 'translations/ru/volumes/v001/drafts/first.md'
        self.target = self.root / 'translations/ru/volumes/v001/accepted/first.md'

    def packet(self, selection=None, scope=None):
        return build_packet(self.project, 'ru', ('ja:u001',), scope or {}, memory_input=self.selection if selection is None else selection)

    def reviewed(self, name='first', selection=None, scope=None):
        packet = self.packet(selection, scope)
        self.apply(plan_translation_draft(self.project, 'ru', name, packet, b'Translation.'))
        path = f'translations/ru/volumes/v001/drafts/{name}.md'
        self.apply(plan_translation_status(self.project, path, 'reviewed'))
        return path

    def write_memory(self, name, **extra):
        path = self.root / f'translations/ru/memory/voices/{name}.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(md({'record-id': name, 'subject': 'hero', 'status': 'accepted', 'evidence': ['user: voice'], **extra}))
        return path

    def test_none_retains_v1_and_empty_selection_retains_file_behavior(self):
        self.write_memory('voice')
        old = build_packet(self.project, 'ru', ('ja:u001',), {})
        self.assertEqual(old, build_packet(self.project, 'ru', ('ja:u001',), {}, memory_input=None))
        self.assertEqual(1, old['packet-version'])
        self.assertNotIn('memory-input', old)
        empty = self.packet({})
        self.assertEqual(2, empty.pop('packet-version'))
        self.assertEqual({'external-memory-refs': [], 'excluded-file-memory': [], 'external-entities': {}}, empty.pop('memory-input'))
        self.assertEqual({k: v for k, v in old.items() if k != 'packet-version'}, empty)

    def test_v1_accept_rejects_external_options_before_freshness(self):
        packet = build_packet(self.project, 'ru', ('ja:u001',), {})
        self.apply(plan_translation_draft(self.project, 'ru', 'first', packet, b'Translation.'))
        self.apply(plan_translation_status(self.project, self.path, 'reviewed'))
        for options in (
                {'external_memory_observed': []},
                {'external_memory_observed': [asdict(REF)]},
                {'external_fallback_note': ''},
                {'external_fallback_note': 'Authorized fallback'},
                {'external_memory_observed': [], 'external_fallback_note': 'Fallback'}):
            with self.subTest(options=options), patch(
                    'cwcli.translation.drafts.translation_status',
                    side_effect=AssertionError('unsupported options precede freshness')):
                with self.assertRaisesRegex(ValueError, 'require packet-version 2'):
                    plan_translation_accept(self.project, self.path, **options)
        self.assertFalse(self.target.exists())
        self.apply(plan_translation_accept(self.project, self.path))
        self.assertIn('Translation.', self.target.read_text())

    def test_selection_validation_precedes_catalog_scan(self):
        invalid = ([], {'trust': True}, {'external-memory-refs': None},
                   {'external-memory-refs': [dict(asdict(REF), revision='')]},
                   {'external-memory-refs': [{'unverified': ''}]},
                   {'external-memory-refs': [dict(asdict(REF), unverified='absent revision')]},
                   {'excluded-file-memory': 'translations/ru/memory'},
                   {'excluded-file-memory': ['sources/ja']},
                   {'excluded-file-memory': ['translations/en/memory/']},
                   {'excluded-file-memory': ['translations/ru/memory/../../translation.md']},
                   {'external-entities': []}, {'external-entities': {'hero': []}},
                   {'external-entities': {'outside': [asdict(REF)]}},
                   {'external-memory-refs': [asdict(REF)], 'external-entities': {'hero': [asdict(replace(REF, revision='11'))]}})
        with patch('cwcli.translation.context.load_catalog', side_effect=AssertionError('catalog must not be scanned')):
            for selection in invalid:
                with self.subTest(selection=selection), self.assertRaises(ValueError):
                    self.packet(selection, {'scope-entities': ['hero']})

    def test_packet_rebuild_rejects_unknown_versions_or_modified_context(self):
        from cwcli.translation.context import rebuild_packet
        packet = self.packet()
        self.assertEqual(packet, rebuild_packet(self.project, packet))
        for version in (None, 0, 3, True, '2'):
            bad = dict(packet, **{'packet-version': version})
            with self.subTest(version=version), self.assertRaises(ValueError):
                plan_translation_draft(self.project, 'ru', 'bad', bad, b'Text')
        for field in ('memory-input', 'packet-version'):
            bad = copy.deepcopy(packet)
            del bad[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                plan_translation_draft(self.project, 'ru', 'bad', bad, b'Text')
        bad = copy.deepcopy(packet)
        bad['primary-text'][0]['text'] = 'Forged'
        with self.assertRaises(ValueError):
            plan_translation_draft(self.project, 'ru', 'bad', bad, b'Text')
        bad = copy.deepcopy(packet)
        bad['memory-input']['trust'] = True
        with self.assertRaises(ValueError):
            rebuild_packet(self.project, bad)

    def test_v2_draft_apply_rechecks_source_bytes(self):
        packet = self.packet()
        self.assertEqual(2, packet['packet-version'])
        plan = plan_translation_draft(self.project, 'ru', 'first', packet, b'Translation')
        source = self.root / packet['primary-text'][0]['path']
        source.write_bytes(source.read_bytes() + b'changed')
        with self.assertRaises(TransactionConflict):
            self.apply(plan)
        self.assertFalse((self.root / self.path).exists())

    def test_v2_keeps_original_source_and_alignment_inventory_guards(self):
        packet = self.packet()
        plan = plan_translation_draft(self.project, 'ru', 'first', packet, b'Translation')
        original = next(path for path in packet['dependencies'] if '/originals/' in path)
        target = self.root / original
        before = target.read_bytes()
        target.write_bytes(b'changed original')
        with self.assertRaises(TransactionConflict):
            self.apply(plan)
        target.write_bytes(before)
        for path, content in (
                ('sources/ja/volumes/v001/text/extra.md', md({'unit-id': 'extra', 'volume-id': 'v001', 'order': 5})),
                ('kb/source-comparisons/new.md', md({'alignment-id': 'new', 'status': 'proposed'}))):
            target = self.root / path
            target.write_bytes(content)
            with self.subTest(path=path), self.assertRaises(TransactionConflict):
                self.apply(plan)
            target.unlink()

    def test_file_exclusion_does_not_hide_neighboring_files_or_unsafe_paths(self):
        excluded = self.write_memory('old')
        excluded.write_bytes(b'\xff')
        selection = {'excluded-file-memory': ['translations/ru/memory/voices/old.md']}
        before = self.packet(selection)
        self.write_memory('other')
        after = self.packet(selection)
        self.assertNotEqual(before['memory-catalog-digest'], after['memory-catalog-digest'])
        self.assertEqual('other', after['rules'][0]['record-id'])
        link = self.root / 'translations/ru/memory/linked'
        link.symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.packet({'excluded-file-memory': ['translations/ru/memory/linked/']})

    def test_excluded_malformed_memory_is_never_parsed_through_acceptance(self):
        bad = self.write_memory('old')
        bad.write_bytes(b'\xff')
        with self.assertRaises(ValueError):
            build_packet(self.project, 'ru', ('ja:u001',), {})
        self.reviewed()
        self.assertEqual('unknown', translation_status(self.project, self.path)['freshness'])
        self.apply(plan_translation_accept(self.project, self.path, external_memory_observed=[asdict(REF)]))
        self.assertIn('Translation.', self.target.read_text())

    def test_excluded_directory_covers_future_records_and_conflicting_graph(self):
        self.write_memory('a')
        self.write_memory('b')
        before = self.packet()
        self.reviewed()
        bad = self.write_memory('later', supersedes='absent')
        bad.write_bytes(b'\xff')
        self.assertEqual(before, self.packet())
        self.assertEqual('current', translation_status(self.project, self.path, external_memory_observed=[asdict(REF)])['freshness'])
        self.assertFalse(any('/memory/' in path for path in before['dependencies']))

    def test_selected_rule_cannot_promote_an_excluded_parent(self):
        self.write_memory('parent')
        self.write_memory('child', supersedes='parent')
        with self.assertRaisesRegex(ValueError, 'supersession'):
            self.packet({'excluded-file-memory': ['translations/ru/memory/voices/parent.md']})

    def test_shared_catalog_and_cache_respect_each_draft_selection(self):
        self.write_memory('a')
        self.write_memory('b')
        for name, excluded in (('a', 'b'), ('b', 'a')):
            self.reviewed(name, {'excluded-file-memory': [f'translations/ru/memory/voices/{excluded}.md']})
        catalog, cache = load_catalog(self.project), {}
        for name in ('a', 'b', 'a'):
            path = f'translations/ru/volumes/v001/drafts/{name}.md'
            self.assertEqual('current', translation_status(self.project, path, catalog=catalog, cache=cache)['freshness'])
        from cwcli.checks.translation import check_translation
        self.assertFalse(any(f.code in ('CW-TRANS-010', 'CW-TRANS-011') for f in check_translation(self.project)))

    def test_external_entities_need_no_file_mirror_and_participate_in_freshness(self):
        selection = {'external-entities': {'hero': [asdict(REF)]}}
        self.reviewed(selection=selection, scope={'scope-entities': ['hero']})
        self.assertFalse((self.root / 'kb/entities/hero.md').exists())
        self.assertEqual([], self.packet(selection, {'scope-entities': ['hero']})['entities'])
        self.assertEqual('unknown', translation_status(self.project, self.path)['freshness'])
        self.assertEqual('current', translation_status(self.project, self.path, external_memory_observed=[asdict(REF)])['freshness'])
        self.assertEqual('needs-review', translation_status(self.project, self.path, external_memory_observed=[])['freshness'])

    def test_marker_and_known_references_preserve_unknown_without_false_current(self):
        marker = {'unverified': 'Public evidence capture has no revision'}
        self.reviewed(selection={'external-memory-refs': [asdict(REF), marker], 'external-entities': {'hero': [marker]}}, scope={'scope-entities': ['hero']})
        for observed in (None, [asdict(REF)]):
            with self.subTest(observed=observed):
                self.assertEqual('unknown', translation_status(self.project, self.path, external_memory_observed=observed)['freshness'])
        self.assertEqual('needs-review', translation_status(self.project, self.path, external_memory_observed=[])['freshness'])
        self.apply(plan_translation_accept(self.project, self.path, external_memory_observed=[asdict(REF)], external_fallback_note='User permitted this task with unavailable advisory revision.'))
        self.assertEqual('unknown', translation_status(self.project, self.path, external_memory_observed=[asdict(REF)])['freshness'])
        self.assertIn('external-memory-freshness: unknown', self.target.read_text())

    def test_unverified_only_entity_stays_unknown(self):
        self.reviewed(selection={'external-entities': {'hero': [{'unverified': 'Public service identity unavailable'}]}}, scope={'scope-entities': ['hero']})
        self.assertEqual('unknown', translation_status(self.project, self.path, external_memory_observed=[])['freshness'])
        with self.assertRaisesRegex(ValueError, 'external'):
            plan_translation_accept(self.project, self.path)

    def test_observed_input_rejects_markers_extra_keys_and_conflicting_ids(self):
        self.reviewed()
        for observed in ({}, [{'unverified': 'No revision'}], [dict(asdict(REF), trust=True)], [asdict(REF), asdict(replace(REF, revision='11'))]):
            with self.subTest(observed=observed), self.assertRaises(ValueError):
                translation_status(self.project, self.path, external_memory_observed=observed)

    def test_unavailable_acceptance_needs_nonempty_note_and_records_limitation(self):
        self.reviewed()
        for note in (None, '', ' ', True):
            with self.subTest(note=note), self.assertRaises(ValueError):
                plan_translation_accept(self.project, self.path, external_fallback_note=note)
        note = 'User authorized this task while the service is unavailable.'
        plan = plan_translation_accept(self.project, self.path, external_fallback_note=note)
        self.assertEqual('unknown', plan.metadata['external-memory-freshness'])
        self.assertEqual(note, plan.metadata['external-fallback-note'])
        record = self.apply(plan)
        self.assertEqual(note, TransactionEngine(self.project).store.manifest(record.id)['metadata']['external-fallback-note'])
        self.assertEqual('unknown', translation_status(self.project, self.path)['freshness'])
        self.assertIn('external-memory-freshness: unknown', self.target.read_text())
        self.assertEqual('current', translation_status(self.project, self.path, external_memory_observed=[asdict(REF)])['freshness'])
        self.assertIn('external-memory-freshness: unknown', self.target.read_text())

    def test_fallback_never_relaxes_known_changed_or_local_source_guards(self):
        self.reviewed()
        for observed in ([], [asdict(replace(REF, revision='11'))], [asdict(replace(REF, namespace='other/series-a'))]):
            with self.subTest(observed=observed), self.assertRaises(ValueError):
                plan_translation_accept(self.project, self.path, external_memory_observed=observed, external_fallback_note='Permitted unavailable fallback')
        plan = plan_translation_accept(self.project, self.path, external_fallback_note='Permitted unavailable fallback')
        source = self.root / 'sources/ja/volumes/v001/text/u001.md'
        source.write_bytes(source.read_bytes() + b'Edit')
        with self.assertRaises(ValueError):
            plan_translation_accept(self.project, self.path, external_fallback_note='Permitted unavailable fallback')
        with self.assertRaises(TransactionConflict):
            self.apply(plan)
        self.assertFalse(self.target.exists())

    def test_fallback_preserves_review_hash_accepted_base_and_serialized_coverage(self):
        first = self.reviewed()
        second = self.reviewed('second')
        self.target.parent.mkdir(parents=True, exist_ok=True)
        plans = [plan_translation_accept(self.project, path, external_fallback_note='Permitted unavailable fallback') for path in (first, second)]
        plan = plans[1]
        serialized = json.loads(json.dumps(_jsonable(plan.metadata)))
        second_plan = TransactionPlan(plan.command, tuple(Change(c.path, c.before, c.after) for c in plan.changes), serialized)
        self.apply(plans[0])
        with self.assertRaises(TransactionConflict):
            self.apply(second_plan)
        with self.assertRaisesRegex(ValueError, 'coverage'):
            plan_translation_accept(self.project, second, external_fallback_note='Permitted unavailable fallback')
        self.reviewed()
        self.target.write_text('Author edit')
        with self.assertRaisesRegex(ValueError, 'accepted base'):
            plan_translation_accept(self.project, first, external_fallback_note='Permitted unavailable fallback')
        draft = self.root / first
        draft.write_bytes(draft.read_bytes() + b'Unreviewed edit')
        with self.assertRaisesRegex(ValueError, 'reviewed'):
            plan_translation_accept(self.project, first, external_fallback_note='Permitted unavailable fallback')

    def test_offline_check_reports_unknown_separately_from_changed_inputs(self):
        from cwcli.checks.translation import check_translation
        self.reviewed()
        findings = [f for f in check_translation(self.project) if f.path == self.path]
        self.assertTrue(any(f.code == 'CW-TRANS-012' and 'unverified' in f.message for f in findings))
        self.assertFalse(any(f.code == 'CW-TRANS-010' for f in findings))

    def test_recovery_uses_frozen_local_transaction_without_service_or_packet_rebuild(self):
        self.reviewed()
        self.target.parent.mkdir(parents=True, exist_ok=True)
        plan = plan_translation_accept(self.project, self.path, external_fallback_note='Permitted unavailable fallback')
        engine = TransactionEngine(self.project)
        engine.store.prepare(plan, transaction_id='external-recovery')
        first = plan.changes[0]
        self.target.write_bytes(first.after)
        engine.store.write_state('external-recovery', 'applying', completed=(first.path,), intents=(first.path,))
        with patch('socket.create_connection', side_effect=AssertionError('no network')), patch('cwcli.translation.context.rebuild_packet', side_effect=AssertionError('frozen recovery')):
            self.assertEqual('rolled-back', engine.recover('external-recovery').state)
        self.assertFalse(self.target.exists())
        self.assertEqual('reviewed', translation_status(self.project, self.path)['status'])

    def test_cli_selection_observations_and_utf8_fallback(self):
        from cwcli.app import run
        def cli(args):
            out, err = io.StringIO(), io.StringIO()
            code = run(['translation', *args, '--format', 'json'], cwd=self.root, stdout=out, stderr=err)
            self.assertEqual('', err.getvalue())
            return code, json.loads(out.getvalue())
        for filename, value in (('input.json', self.selection), ('observed.json', [asdict(REF)])):
            (self.root.parent / filename).write_text(json.dumps(value))
        code, packet = cli(['context', '--direction', 'ru', '--units', 'ja:u001', '--memory-input', '../input.json'])
        self.assertEqual(0, code)
        self.assertEqual(2, packet['packet-version'])
        (self.root.parent / 'packet.json').write_text(json.dumps(packet))
        (self.root.parent / 'prose.md').write_text('Translation.')
        self.assertEqual(0, cli(['draft', '--direction', 'ru', '--draft-id', 'first', '--packet', '../packet.json', '--file', '../prose.md', '--apply'])[0])
        self.assertEqual('current', cli(['status', self.path, '--external-memory-observed', '../observed.json'])[1]['freshness'])
        self.assertEqual(0, cli(['set-status', self.path, 'reviewed', '--apply'])[0])
        (self.root.parent / 'note.txt').write_text('Разрешено для этой задачи.', encoding='utf-8')
        self.assertEqual(0, cli(['accept', self.path, '--external-fallback-note', '../note.txt', '--apply'])[0])
        self.assertEqual('unknown', cli(['status', self.path])[1]['freshness'])

    def test_cli_json_files_require_objects_and_arrays_not_null(self):
        from cwcli.app import run
        self.reviewed()
        (self.root.parent / 'null.json').write_text('null')
        commands = (
            ['context', '--direction', 'ru', '--units', 'ja:u001', '--memory-input', '../null.json'],
            ['status', self.path, '--external-memory-observed', '../null.json'],
            ['accept', self.path, '--external-memory-observed', '../null.json'])
        for command in commands:
            out, err = io.StringIO(), io.StringIO()
            code = run(['translation', *command, '--format', 'json'], cwd=self.root, stdout=out, stderr=err)
            with self.subTest(command=command):
                self.assertNotEqual(0, code)
                self.assertIn('JSON', json.loads(out.getvalue())['message'])
