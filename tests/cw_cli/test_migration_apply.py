import hashlib
import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import app, documents, migration


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

    def test_preview_exposes_full_transaction_diff_without_writes(self):
        plan_path, expected = self.preview()
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        status, preview, error = self.run_cli(
            [
                "migrate", "--preview", str(plan_path),
                "--expect-plan-hash", expected, "--format", "json",
            ]
        )
        self.assertEqual((0, ""), (status, error))
        self.assertEqual("preview", preview["status"])
        self.assertTrue(any(item["path"] == "story/chapters/ch-001.md" for item in preview["changes"]))
        self.assertTrue(all("diff" in item for item in preview["changes"]))
        text_status, text_preview, text_error = self.run_cli(
            [
                "migrate", "--preview", str(plan_path),
                "--expect-plan-hash", expected,
            ]
        )
        self.assertEqual((0, ""), (text_status, text_error))
        self.assertEqual(preview, text_preview)
        self.assertEqual(
            before,
            {
                path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*")
                if path.is_file()
            },
        )

    def test_content_merge_applies_atomically_and_undo_restores_every_source(self):
        first = self.root / "kb/timeline/a.md"
        second = self.root / "kb/timeline/b.md"
        first.parent.mkdir(parents=True)
        first.write_bytes(b"First\r\n")
        second.write_bytes(b"Second\n")
        self.legacy.unlink()
        merged = "---\ntitle: Timeline\n---\n# Reviewed merge\n"
        payload = {
            "plan-version": 1,
            "source-schema": 0,
            "target-schema": 1,
            "operations": [
                {
                    "sources": ["kb/timeline/a.md", "kb/timeline/b.md"],
                    "destination": "kb/continuity/timeline.md",
                    "action": "merge",
                    "content": merged,
                }
            ],
            "unresolved": [],
        }
        payload["plan-hash"] = migration.canonical_plan_hash(payload)
        plan_path = self.write_plan(payload)
        status, applied, error = self.run_cli(
            ["migrate", "--apply", str(plan_path), "--expect-plan-hash", payload["plan-hash"], "--format", "json"]
        )
        self.assertEqual((0, ""), (status, error))
        self.assertEqual(merged.encode(), (self.root / "kb/continuity/timeline.md").read_bytes())
        self.assertFalse(first.exists())
        self.assertFalse(second.exists())
        status, _, _ = self.run_cli(
            ["undo", applied["transaction_id"], "--apply", "--format", "json"]
        )
        self.assertEqual(0, status)
        self.assertEqual(b"First\r\n", first.read_bytes())
        self.assertEqual(b"Second\n", second.read_bytes())
        self.assertFalse((self.root / "kb/continuity/timeline.md").exists())

    def test_cross_operation_merge_destination_source_is_rejected_without_overwrite(self):
        first = self.root / "kb/timeline/a.md"
        second = self.root / "kb/timeline/b.md"
        reviewed_destination = self.root / "kb/continuity/timeline.md"
        first.parent.mkdir(parents=True)
        reviewed_destination.parent.mkdir(parents=True)
        first.write_bytes(b"First\n")
        second.write_bytes(b"Second\n")
        reviewed_destination.write_bytes(b"Existing timeline\n")
        self.legacy.unlink()
        payload = {
            "plan-version": 1,
            "source-schema": 0,
            "target-schema": 1,
            "operations": [
                {
                    "sources": ["kb/timeline/a.md", "kb/timeline/b.md"],
                    "destination": "kb/continuity/timeline.md",
                    "action": "merge",
                    "content": "# MERGED reviewed content\n",
                },
                {
                    "source": "kb/continuity/timeline.md",
                    "destination": "work/plans/stolen.md",
                    "action": "move",
                },
            ],
            "unresolved": [],
        }
        payload["plan-hash"] = migration.canonical_plan_hash(payload)

        status, result, _ = self.run_cli(
            [
                "migrate", "--apply", str(self.write_plan(payload)),
                "--expect-plan-hash", payload["plan-hash"], "--format", "json",
            ]
        )

        self.assertEqual(1, status)
        self.assertEqual("conflict", result["status"])
        self.assertEqual(b"First\n", first.read_bytes())
        self.assertEqual(b"Second\n", second.read_bytes())
        self.assertEqual(b"Existing timeline\n", reviewed_destination.read_bytes())
        self.assertFalse((self.root / "work/plans/stolen.md").exists())

    def test_plain_manifest_body_is_upgraded_and_exactly_restored_by_undo(self):
        legacy_manifest = b"Legacy instructions\r\nKeep every word.\r\n"
        (self.root / "project.md").write_bytes(legacy_manifest)
        plan_path, expected = self.preview()
        status, applied, _ = self.run_cli(
            ["migrate", "--apply", str(plan_path), "--expect-plan-hash", expected, "--format", "json"]
        )
        self.assertEqual(0, status)
        manifest = documents.parse_document((self.root / "project.md").read_bytes())
        self.assertEqual(1, manifest.metadata["schema-version"])
        self.assertEqual("Legacy instructions\r\nKeep every word.\r\n", manifest.body)
        self.run_cli(["undo", applied["transaction_id"], "--apply", "--format", "json"])
        self.assertEqual(legacy_manifest, (self.root / "project.md").read_bytes())

    def test_malformed_markdown_bytes_survive_and_post_checks_are_reported(self):
        malformed = b"---\ntitle: [unsupported]\n---\nBody\r\n"
        self.legacy.write_bytes(malformed)
        plan_path, expected = self.preview()
        status, applied, error = self.run_cli(
            ["migrate", "--apply", str(plan_path), "--expect-plan-hash", expected, "--format", "json"]
        )
        self.assertEqual((0, ""), (status, error))
        self.assertEqual(malformed, (self.root / "story/chapters/ch-001.md").read_bytes())
        self.assertEqual(["structure", "drafts"], applied["checks"])
        self.assertTrue(applied["findings"])

    def test_invalid_utf8_migration_previews_applies_and_undoes_exact_bytes(self):
        legacy = b"---\nnumber: 1\n---\nInvalid: \xff\xfe\x80\r\n"
        self.legacy.write_bytes(legacy)
        plan_path, expected = self.preview()

        status, preview, error = self.run_cli(
            [
                "migrate", "--preview", str(plan_path),
                "--expect-plan-hash", expected, "--format", "json",
            ]
        )
        self.assertEqual((0, ""), (status, error))
        binary_diffs = [
            item["diff"] for item in preview["changes"] if item["path"] in {
                "chapters/ch-001.md", "story/chapters/ch-001.md"
            }
        ]
        self.assertEqual(2, len(binary_diffs))
        digest = hashlib.sha256(legacy).hexdigest()
        self.assertTrue(all("Binary change:" in diff for diff in binary_diffs))
        self.assertTrue(all(f"size={len(legacy)} sha256={digest}" in diff for diff in binary_diffs))
        self.assertEqual(legacy, self.legacy.read_bytes())

        status, applied, error = self.run_cli(
            [
                "migrate", "--apply", str(plan_path),
                "--expect-plan-hash", expected, "--format", "json",
            ]
        )
        self.assertEqual((0, ""), (status, error))
        destination = self.root / "story/chapters/ch-001.md"
        self.assertEqual(legacy, destination.read_bytes())
        self.assertFalse(self.legacy.exists())

        status, _, error = self.run_cli(
            ["undo", applied["transaction_id"], "--apply", "--format", "json"]
        )
        self.assertEqual((0, ""), (status, error))
        self.assertEqual(legacy, self.legacy.read_bytes())
        self.assertFalse(destination.exists())

    def test_fallback_no_follow_path_supports_plan_and_source_reads(self):
        plan_path, expected = self.preview()
        with mock.patch.object(migration, "_secure_dirfd_supported", return_value=False):
            loaded = migration.load_migration_plan(plan_path, root=self.root)
            plan = migration.plan_apply_migration(self.root, loaded, expected)
        self.assertTrue(plan.changes)

    def test_fallback_rejects_reparse_attributes_and_simulated_reparse_leaf(self):
        reparse_info = mock.Mock(st_file_attributes=0x400)
        self.assertTrue(migration._is_reparse_point(reparse_info))
        leaf = self.legacy.lstat()
        with mock.patch.object(
            migration,
            "_is_reparse_point",
            side_effect=lambda info: (
                stat.S_ISREG(info.st_mode)
                and info.st_dev == leaf.st_dev
                and info.st_ino == leaf.st_ino
            ),
        ):
            with self.assertRaisesRegex(migration.MigrationPlanError, "real file without links"):
                migration._fallback_regular_identity(
                    self.legacy, "migration source", root=self.root
                )

    def test_fallback_read_detects_replacement_and_closes_both_descriptors(self):
        replacement = self.root / "replacement.md"
        replacement.write_bytes(b"Replacement\n")
        first_descriptor = os.open(self.legacy, os.O_RDONLY)
        second_descriptor = os.open(replacement, os.O_RDONLY)
        with mock.patch.object(migration, "_secure_dirfd_supported", return_value=False), mock.patch.object(
            migration,
            "_fallback_regular_identity",
            side_effect=[first_descriptor, second_descriptor],
        ) as fallback:
            with self.assertRaisesRegex(migration.MigrationPlanError, "changed while it was read"):
                migration._read_regular_file_no_follow(
                    self.legacy, "migration source", root=self.root
                )
        self.assertEqual(2, fallback.call_count)
        for descriptor in (first_descriptor, second_descriptor):
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_fallback_source_probe_closes_its_descriptor_once(self):
        descriptor = os.open(self.legacy, os.O_RDONLY)
        real_close = os.close
        with mock.patch.object(migration, "_secure_dirfd_supported", return_value=False), mock.patch.object(
            migration, "_fallback_regular_identity", return_value=descriptor
        ) as fallback, mock.patch.object(migration.os, "close", wraps=real_close) as closer:
            migration._require_source_entry(self.root, "chapters/ch-001.md")
        fallback.assert_called_once()
        closer.assert_called_once_with(descriptor)
        with self.assertRaises(OSError):
            os.fstat(descriptor)

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
