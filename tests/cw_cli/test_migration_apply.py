import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import app, migration


class MigrationApplyTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "legacy"
        (self.root / "chapters").mkdir(parents=True)
        self.legacy = self.root / "chapters/ch-001.md"
        self.legacy.write_bytes(b"---\nnumber: 1\ntitle: Legacy\n---\r\nExact legacy\r\n")
        (self.root / "notes.bin").write_bytes(b"unknown\x00bytes")

    def run_cli(self, argv: list[str]) -> tuple[int, dict[str, object], str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        status = app.run(argv, cwd=self.root, stdout=stdout, stderr=stderr)
        payload = json.loads(stdout.getvalue()) if stdout.getvalue() else {}
        return status, payload, stderr.getvalue()

    def write_plan(self, payload: dict[str, object]) -> Path:
        path = Path(self.root.parent) / "migration-plan.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def preview(self) -> tuple[Path, str]:
        status, payload, error = self.run_cli(["migrate", "--plan", "--format", "json"])
        self.assertEqual((0, ""), (status, error))
        return self.write_plan(payload), payload["plan-hash"]

    def test_apply_is_one_undoable_transaction_and_restores_exact_legacy_bytes(self):
        legacy = self.legacy.read_bytes()
        unknown = (self.root / "notes.bin").read_bytes()
        plan_path, expected = self.preview()

        status, applied, error = self.run_cli(
            [
                "migrate", "--apply", str(plan_path),
                "--expect-plan-hash", expected, "--format", "json",
            ]
        )

        self.assertEqual((0, ""), (status, error))
        self.assertEqual("committed", applied["status"])
        self.assertEqual(expected, applied["plan_hash"])
        destination = self.root / "story/chapters/ch-001.md"
        self.assertEqual(legacy, destination.read_bytes())
        self.assertFalse(self.legacy.exists())
        self.assertEqual(unknown, (self.root / "notes.bin").read_bytes())
        self.assertTrue((self.root / "work/drafts/_index.md").exists())

        status, report, _ = self.run_cli(["check", "structure", "--format", "json"])
        self.assertEqual(0, status)
        self.assertFalse(report["execution_errors"])

        transaction_id = applied["transaction_id"]
        status, undone, _ = self.run_cli(
            ["undo", transaction_id, "--format", "json", "--apply"]
        )
        self.assertEqual(0, status)
        self.assertEqual("committed", undone["status"])
        self.assertEqual(legacy, self.legacy.read_bytes())
        self.assertFalse(destination.exists())
        self.assertEqual(unknown, (self.root / "notes.bin").read_bytes())
        for relative in ("story", "work", "kb"):
            self.assertFalse((self.root / relative).exists())

    def test_tamper_hash_unresolved_and_destination_collision_are_conflicts_without_mutation(self):
        plan_path, shown_hash = self.preview()
        original = self.legacy.read_bytes()
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
        payload["operations"][0]["destination"] = "story/chapters/changed.md"
        plan_path.write_text(json.dumps(payload), encoding="utf-8")
        status, result, _ = self.run_cli(
            ["migrate", "--apply", str(plan_path), "--expect-plan-hash", shown_hash, "--format", "json"]
        )
        self.assertEqual(1, status)

        self.assertEqual("conflict", result["status"])
        self.assertEqual(original, self.legacy.read_bytes())

        plan_path, shown_hash = self.preview()
        (self.root / "story/chapters").mkdir(parents=True)
        collision = self.root / "story/chapters/ch-001.md"
        collision.write_bytes(b"do not overwrite")
        status, _, _ = self.run_cli(
            ["migrate", "--apply", str(plan_path), "--expect-plan-hash", shown_hash, "--format", "json"]
        )
        self.assertEqual(1, status)
        self.assertEqual(b"do not overwrite", collision.read_bytes())
        self.assertEqual(original, self.legacy.read_bytes())

    def test_plan_validation_happens_before_any_source_read(self):
        planned = migration.plan_migration(self.root)
        with mock.patch.object(
            migration, "_read_regular_file_no_follow", side_effect=AssertionError("read")
        ) as reader:
            with self.assertRaisesRegex(migration.MigrationPlanError, "hash"):
                migration.plan_apply_migration(self.root, planned, "0" * 64)
        reader.assert_not_called()

        unresolved_payload = planned.to_payload(include_hash=False)
        unresolved_payload["operations"] = []
        unresolved_payload["unresolved"] = [
            {"sources": ["chapters/ch-001.md"], "destination": None, "reason": "unknown-role"}
        ]
        unresolved_payload["plan-hash"] = migration.canonical_plan_hash(unresolved_payload)
        unresolved = migration.MigrationPlan(
            plan_version=1,
            source_schema=0,
            target_schema=1,
            operations=(),
            unresolved=tuple(unresolved_payload["unresolved"]),
            plan_hash=unresolved_payload["plan-hash"],
        )
        with mock.patch.object(
            migration, "_read_regular_file_no_follow", side_effect=AssertionError("read")
        ) as reader:
            with self.assertRaisesRegex(migration.MigrationPlanError, "unresolved"):
                migration.plan_apply_migration(self.root, unresolved, unresolved.plan_hash)
        reader.assert_not_called()

    def test_nested_and_symlink_boundaries_are_rejected_before_apply(self):
        nested = self.root / "chapters/nested"
        nested.mkdir()
        (nested / "project.md").write_text("---\nschema-version: 1\n---\n", encoding="utf-8")
        plan = migration.plan_migration(self.root)
        # The planner skips nested content, so exercise strict apply loading with
        # a hand-authored but correctly hashed operation crossing that boundary.
        payload = {
            "plan-version": 1,
            "source-schema": 0,
            "target-schema": 1,
            "operations": [{"source": "chapters/nested/x.md", "destination": "story/chapters/x.md", "action": "move"}],
            "unresolved": [],
        }
        payload["plan-hash"] = migration.canonical_plan_hash(payload)
        path = self.write_plan(payload)
        status, _, _ = self.run_cli(
            ["migrate", "--apply", str(path), "--expect-plan-hash", payload["plan-hash"], "--format", "json"]
        )
        self.assertEqual(1, status)

        link = self.root / "chapters-link"
        try:
            os.symlink(self.root / "chapters", link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        payload["operations"] = [{"source": "chapters-link/ch-001.md", "destination": "story/chapters/x.md", "action": "move"}]
        payload["plan-hash"] = migration.canonical_plan_hash(payload)
        path = self.write_plan(payload)
        status, _, _ = self.run_cli(
            ["migrate", "--apply", str(path), "--expect-plan-hash", payload["plan-hash"], "--format", "json"]
        )
        self.assertEqual(1, status)

    def test_apply_rejects_noncanonical_destinations_before_source_reads(self):
        planned = migration.plan_migration(self.root)
        for destination in (
            "story/chapters/_index.md",
            "story/chapters/project.md",
            "work/unsafe.md",
            ".creative-writing/owned.md",
        ):
            with self.subTest(destination=destination):
                payload = planned.to_payload(include_hash=False)
                payload["operations"] = [
                    {"source": "chapters/ch-001.md", "destination": destination, "action": "move"}
                ]
                payload["plan-hash"] = migration.canonical_plan_hash(payload)
                candidate = migration.MigrationPlan(
                    1, 0, 1,
                    (migration.MigrationOperation("chapters/ch-001.md", destination, "move"),),
                    (), payload["plan-hash"],
                )
                with mock.patch.object(
                    migration, "_read_regular_file_no_follow", side_effect=AssertionError("source read")
                ) as reader:
                    with self.assertRaises(migration.MigrationPlanError):
                        migration.plan_apply_migration(self.root, candidate, candidate.plan_hash)
                reader.assert_not_called()

    def test_apply_requires_actual_source_schema_before_operation_reads(self):
        planned = migration.plan_migration(self.root)
        (self.root / "project.md").write_text(
            "---\nschema-version: 1\ntitle: Changed\nlanguage: en\nstatus: drafting\n---\n",
            encoding="utf-8",
        )
        with mock.patch.object(
            migration, "_require_source_entry", side_effect=AssertionError("operation inspected")
        ) as source_probe:
            with self.assertRaisesRegex(migration.MigrationPlanError, "source schema"):
                migration.plan_apply_migration(self.root, planned, planned.plan_hash)
        source_probe.assert_not_called()

        payload = planned.to_payload(include_hash=False)
        payload["source-schema"] = 1
        payload["plan-hash"] = migration.canonical_plan_hash(payload)
        stale = migration.MigrationPlan(1, 1, 1, planned.operations, (), payload["plan-hash"])
        (self.root / "project.md").write_text("---\nschema-version: 2\n---\n", encoding="utf-8")
        with self.assertRaisesRegex(migration.MigrationPlanError, "newer"):
            migration.plan_apply_migration(self.root, stale, stale.plan_hash)

    def test_cli_integrity_gate_precedes_explicit_root_boundary_inspection(self):
        plan_path, _ = self.preview()
        with mock.patch.object(
            migration, "_reject_nested_boundary", side_effect=AssertionError("root inspected")
        ) as boundary:
            status, payload, _ = self.run_cli(
                [
                    "migrate", "--apply", str(plan_path),
                    "--expect-plan-hash", "0" * 64, "--format", "json",
                ]
            )
        self.assertEqual(1, status)
        self.assertEqual("conflict", payload["status"])
        boundary.assert_not_called()

    def test_portable_destination_collision_precedes_source_read(self):
        planned = migration.plan_migration(self.root)
        (self.root / "Story").mkdir()
        with mock.patch.object(
            migration, "_read_regular_file_no_follow", side_effect=AssertionError("source read")
        ) as reader:
            with self.assertRaisesRegex(migration.MigrationPlanError, "collid"):
                migration.plan_apply_migration(self.root, planned, planned.plan_hash)
        reader.assert_not_called()

if __name__ == "__main__":
    unittest.main()
