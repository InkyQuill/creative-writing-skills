"""Behavioral regressions for the second translation review."""
import io
import json
import multiprocessing
from unittest.mock import patch
from .translation_helpers import TranslationFixture, md
from cwcli.app import run
from cwcli.translation.context import build_packet
from cwcli.translation.directions import plan_direction
from cwcli.translation.sources import plan_source
from cwcli.translation.memory import select_memory
from cwcli.translation.drafts import plan_translation_draft, plan_translation_status, plan_translation_accept
from cwcli.transactions import Change, TransactionPlan, TransactionEngine, TransactionConflict, _jsonable
from cwcli.project import discover_project


def accept_in_process(root, payload, paused, release, started, result, transaction_id=None):
    command, changes, metadata = payload
    plan = TransactionPlan(tuple(command), tuple(Change(*change) for change in changes), metadata)
    engine = TransactionEngine(discover_project(root))
    install = engine._install_change
    if paused is not None:
        def held_install(identifier, change):
            paused.set()
            if not release.wait(10):
                raise RuntimeError('test release timeout')
            return install(identifier, change)
        engine._install_change = held_install
    started.set()
    try:
        engine.apply(plan, transaction_id=transaction_id)
        result.put('committed')
    except TransactionConflict:
        result.put('conflict')
    except Exception as error:
        result.put(type(error).__name__ + ': ' + str(error))


def recover_in_process(root, started, result):
    engine = TransactionEngine(discover_project(root))
    started.set()
    try:
        result.put(engine.recover('active-transaction').state)
    except Exception as error:
        result.put(str(error))


class SecondTranslationReviewTests(TranslationFixture):
    def setUp(self):
        super().setUp()
        self.edition()
        self.apply(plan_direction(self.project, md({'direction-id': 'ru', 'language': 'ru', 'primary-edition': 'ja', 'coverage': ['v001']})))

    def test_migration_does_not_follow_manifest_symlink(self):
        outside = self.root.parent / 'outside.md'
        outside.write_bytes(md({'schema-version': 2}))
        (self.root / 'project.md').unlink()
        (self.root / 'project.md').symlink_to(outside)
        out, err = io.StringIO(), io.StringIO()
        code = run(['migrate', '--plan', '--format', 'json'], cwd=self.root, stdout=out, stderr=err)
        self.assertNotEqual(0, code)
        self.assertIn('without links', json.loads(out.getvalue())['message'])

    def test_multiple_neighbors_retain_source_reading_order(self):
        self.unit('z-first', text='First')
        self.unit('middle', text='Middle')
        self.unit('a-last', text='Last')
        packet = build_packet(self.project, 'ru', ('ja:middle',), {})
        self.assertEqual(['First', 'Last'], [r['text'] for r in packet['neighbor-text']])

    def test_manuscript_source_rejects_indexes_nested_and_non_markdown_files(self):
        for relative in ('story/chapters/_index.md', 'story/side-stories/_index.md', 'story/chapters/nested/one.md', 'story/chapters/one.txt'):
            with self.subTest(relative=relative):
                path = self.root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('Manuscript')
                with self.assertRaises(ValueError):
                    plan_source(self.project, {'action': 'manuscript-unit', 'edition': 'ja', 'unit': 'source', 'volume': 'v001', 'manuscript-path': relative})

    def test_direct_markdown_manuscript_source_remains_supported(self):
        for number, folder in enumerate(('chapters', 'side-stories')):
            relative = f'story/{folder}/one.md'
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Manuscript')
            plan = plan_source(self.project, {'action': 'manuscript-unit', 'edition': 'ja', 'unit': f'source-{number}', 'volume': 'v001', 'manuscript-path': relative})
            self.apply(plan)
            self.assertEqual('Manuscript', path.read_text())

    def test_volume_override_rejects_changed_parent_settings(self):
        plan = plan_direction(self.project, md({'direction-id': 'ru', 'volume-id': 'v001', 'primary-edition': 'ja'}))
        root = self.root / 'translations/ru/translation.md'
        root.write_bytes(md({'direction-id': 'ru', 'language': 'ru', 'primary-edition': 'ja', 'coverage': ['v002']}))
        with self.assertRaises(TransactionConflict):
            self.apply(plan)
        self.assertFalse((self.root / 'translations/ru/volumes/v001/settings.md').exists())

    def test_oversized_scope_rejected_before_catalog_scan(self):
        units = tuple(f'ja:u{i}' for i in range(65))
        scope = {'scope-entities': [f'e{i}' for i in range(65)]}
        with patch('cwcli.translation.context.load_catalog', side_effect=AssertionError('catalog must not be scanned')):
            with self.assertRaisesRegex(ValueError, 'scope.*too large'):
                build_packet(self.project, 'ru', units, scope)

    def test_direct_memory_selection_rejects_oversized_product_before_scan(self):
        scope = {'scope-units': [f'ja:u{i}' for i in range(65)], 'scope-relationships': [f'r{i}' for i in range(65)]}
        with patch('cwcli.translation.memory.memory_records', side_effect=AssertionError('memory must not be scanned')):
            with self.assertRaisesRegex(ValueError, 'scope.*too large'):
                select_memory(self.project, 'ru', scope)

    def test_concurrent_acceptance_serializes_validation_and_installation(self):
        self.unit()
        (self.root / 'translations/ru/volumes/v001/accepted').mkdir(parents=True)
        plans = []
        for name in ('first', 'second'):
            packet = build_packet(self.project, 'ru', ('ja:u001',), {})
            self.apply(plan_translation_draft(self.project, 'ru', name, packet, b'Translation'))
            path = f'translations/ru/volumes/v001/drafts/{name}.md'
            self.apply(plan_translation_status(self.project, path, 'reviewed'))
            plans.append(plan_translation_accept(self.project, path))
        ctx = multiprocessing.get_context('spawn')
        payloads = [(plan.command, [(c.path, c.before, c.after) for c in plan.changes], _jsonable(plan.metadata)) for plan in plans]
        paused, release = ctx.Event(), ctx.Event()
        started = [ctx.Event(), ctx.Event()]
        results = [ctx.Queue(), ctx.Queue()]
        processes = [ctx.Process(target=accept_in_process, args=(self.root, payloads[i], paused if i == 0 else None, release, started[i], results[i])) for i in range(2)]
        try:
            processes[0].start()
            self.assertTrue(paused.wait(5))
            processes[1].start()
            self.assertTrue(started[1].wait(5))
            # First process is paused immediately before installation. Give the
            # second a chance to race; without exclusion it commits overlapping text.
            processes[1].join(1)
            release.set()
            for process in processes:
                process.join(10)
                self.assertFalse(process.is_alive())
            self.assertEqual('committed', results[0].get(timeout=2))
            self.assertEqual('conflict', results[1].get(timeout=2))
            self.assertFalse((self.root / 'translations/ru/volumes/v001/accepted/second.md').exists())
        finally:
            release.set()
            for process in processes:
                if process.is_alive():
                    process.terminate()
                if process.pid is not None:
                    process.join(5)
            for queue in results:
                queue.close()

    def test_recovery_cannot_roll_back_an_active_writer(self):
        ctx = multiprocessing.get_context('spawn')
        paused, release = ctx.Event(), ctx.Event()
        started = [ctx.Event(), ctx.Event()]
        results = [ctx.Queue(), ctx.Queue()]
        payload = (('test',), [('result.txt', None, b'written')], {})
        writer = ctx.Process(target=accept_in_process, args=(self.root, payload, paused, release, started[0], results[0], 'active-transaction'))
        recovery = ctx.Process(target=recover_in_process, args=(self.root, started[1], results[1]))
        try:
            writer.start()
            self.assertTrue(paused.wait(5))
            recovery.start()
            self.assertTrue(started[1].wait(5))
            recovery.join(1)
            release.set()
            for process in (writer, recovery):
                process.join(10)
                self.assertFalse(process.is_alive())
            self.assertEqual('committed', results[0].get(timeout=2))
            self.assertIn('in state committed', results[1].get(timeout=2))
            self.assertEqual(b'written', (self.root / 'result.txt').read_bytes())
        finally:
            release.set()
            for process in (writer, recovery):
                if process.is_alive():
                    process.terminate()
                if process.pid is not None:
                    process.join(5)
            for queue in results:
                queue.close()
