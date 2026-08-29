import json
import os
import tempfile
import unittest
from pathlib import Path

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import migration


LAYOUT_A = {
    "chapters/ch-001.md": "# Глава\r\n",
    "drafts/ch-002.md": "# Draft\n",
    "characters/лиса.md": "# Лиса\n",
    "worldbuilding/city.md": "# City\n",
    "samples/voice.md": "# Voice\n",
    "styles/prose.md": "# Style\n",
    "plot/timeline.md": "# Timeline\n",
    "plot/state.md": "# State\n",
    "plot/promises.md": "# Promises\n",
    "plot/questions.md": "# Questions\n",
    "plot/scenes/harbor.md": "# Harbor\n",
    "plot/arc.md": "# Arc\n",
}

LAYOUT_B = {
    "story/ch-001.md": "# One\n",
    "work/outline/arc.md": "# Arc\n",
    "work/critique-reports/pass.md": "# Pass\n",
    "kb/samples/voice.md": "# Voice\n",
    "kb/styles/prose.md": "# Style\n",
    "kb/timeline.md": "# Timeline\n",
    "kb/state.md": "# State\n",
    "kb/promises.md": "# Promises\n",
    "kb/questions.md": "# Questions\n",
    "kb/scenes/harbor.md": "# Harbor\n",
}


def materialize(root: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")


def operation_pairs(plan: migration.MigrationPlan) -> set[tuple[str, str, str]]:
    return {(item.source, item.destination, item.action) for item in plan.operations}


def write_plan(root: Path, payload: dict[str, object], *, rehash: bool = True) -> Path:
    if rehash:
        payload["plan-hash"] = migration.canonical_plan_hash(payload)
    path = root / "migration-plan.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


class MigrationPlanningTests(unittest.TestCase):
    def test_layout_a_complete_mapping_table(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materialize(root, LAYOUT_A)

            pairs = operation_pairs(migration.plan_migration(root))

            expected = {
                ("chapters/ch-001.md", "story/chapters/ch-001.md", "move"),
                ("drafts/ch-002.md", "work/drafts/ch-002.md", "move"),
                ("characters/лиса.md", "kb/characters/лиса.md", "move"),
                ("worldbuilding/city.md", "kb/world/city.md", "move"),
                ("samples/voice.md", "kb/samples/voice.md", "move"),
                ("styles/prose.md", "kb/styles/prose.md", "move"),
                ("plot/timeline.md", "kb/continuity/timeline.md", "move"),
                ("plot/state.md", "kb/continuity/state.md", "move"),
                ("plot/promises.md", "kb/continuity/promises.md", "move"),
                ("plot/questions.md", "kb/continuity/questions.md", "move"),
                ("plot/scenes/harbor.md", "kb/continuity/scenes/harbor.md", "move"),
                ("plot/arc.md", "work/plans/arc.md", "move"),
            }
            self.assertEqual(expected, pairs)

    def test_layout_b_complete_mapping_table_and_canonical_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materialize(root, LAYOUT_B)

            pairs = operation_pairs(migration.plan_migration(root))

            self.assertIn(("story/ch-001.md", "story/chapters/ch-001.md", "move"), pairs)
            self.assertIn(("work/outline/arc.md", "work/plans/arc.md", "move"), pairs)
            self.assertIn(("work/critique-reports/pass.md", "work/reviews/pass.md", "move"), pairs)
            self.assertIn(("kb/samples/voice.md", "kb/samples/voice.md", "preserve"), pairs)
            self.assertIn(("kb/styles/prose.md", "kb/styles/prose.md", "preserve"), pairs)
            for name in ("timeline", "state", "promises", "questions"):
                self.assertIn((f"kb/{name}.md", f"kb/continuity/{name}.md", "move"), pairs)
            self.assertIn(("kb/scenes/harbor.md", "kb/continuity/scenes/harbor.md", "move"), pairs)

    def test_single_timeline_file_maps_but_multiple_remain_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materialize(root, {"kb/timeline/arc.md": "# Arc\n"})
            plan = migration.plan_migration(root)
            self.assertIn(
                ("kb/timeline/arc.md", "kb/continuity/timeline.md", "move"),
                operation_pairs(plan),
            )

            materialize(root, {"kb/timeline/arc-two.md": "# Two\n"})
            plan = migration.plan_migration(root)
            item = next(item for item in plan.unresolved if item["reason"] == "timeline-merge")
            self.assertEqual(("kb/timeline/arc-two.md", "kb/timeline/arc.md"), item["sources"])
            self.assertFalse(any(op.source.startswith("kb/timeline/") for op in plan.operations))

    def test_domain_vocab_and_instruction_material_are_explicit_proposals(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instruction_name = "AG" + "ENTS.md"
            materialize(
                root,
                {
                    "worldbuilding/vocab.md": "# Terms\n",
                    instruction_name: "# Instructions\n",
                    "kb/vocab.md": "# Canonical\n",
                },
            )
            plan = migration.plan_migration(root)
            records = {(item["reason"], item["destination"]): item["sources"] for item in plan.unresolved}
            self.assertEqual(
                ("worldbuilding/vocab.md", "kb/vocab.md"),
                records[("domain-vocab-merge", "kb/vocab.md")],
            )
            self.assertEqual((instruction_name,), records[("project-instructions", "project.md")])
            self.assertFalse(any(operation.destination == "kb/vocab.md" for operation in plan.operations))

    def test_mixed_layout_is_unresolved_and_unknown_markdown_is_unmanaged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materialize(
                root,
                {
                    "chapters/a.md": "# A\n",
                    "kb/world/b.md": "# B\n",
                    "notes.md": "# Unknown\n",
                    "asset.png": "not really an image",
                },
            )
            plan = migration.plan_migration(root)
            reasons = {item["reason"] for item in plan.unresolved}
            self.assertIn("mixed-layout", reasons)
            self.assertIn("unknown-role", reasons)
            self.assertEqual((), plan.operations)
            self.assertNotIn("asset.png", repr(plan.unresolved))

    def test_schema_one_canonical_b_role_still_detects_mixed_layout_a_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materialize(
                root,
                {
                    "project.md": "---\nschema-version: 1\n---\n",
                    "chapters/a.md": "# Legacy A\n",
                    "kb/world/b.md": "# Canonical overlap from B\n",
                },
            )
            plan = migration.plan_migration(root)
            mixed = next(item for item in plan.unresolved if item["reason"] == "mixed-layout")
            self.assertEqual(("chapters/a.md", "kb/world/b.md"), mixed["sources"])

    def test_destination_collision_is_never_guessed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materialize(root, {"chapters/one.md": "Old\n", "story/chapters/one.md": "New\n"})
            plan = migration.plan_migration(root)
            collision = next(item for item in plan.unresolved if item["reason"] == "destination-collision")
            self.assertEqual("story/chapters/one.md", collision["destination"])
            self.assertEqual(("chapters/one.md", "story/chapters/one.md"), collision["sources"])
            self.assertEqual(
                {("story/chapters/one.md", "story/chapters/one.md", "preserve")},
                operation_pairs(plan),
            )

    def test_case_collisions_and_nonportable_sources_become_stable_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materialize(
                root,
                {
                    "kb/styles/Voice.md": "Upper\n",
                    "kb/styles/voice.md": "Lower\n",
                },
            )
            plan = migration.plan_migration(root)
            reasons = {item["reason"] for item in plan.unresolved}
            self.assertIn("destination-collision", reasons)
            payload = plan.to_payload()
            migration.load_migration_plan(write_plan(root, payload))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materialize(root, {"chapters/CON.md": "Reserved\n"})
            plan = migration.plan_migration(root)
            self.assertEqual("nonportable-source", plan.unresolved[0]["reason"].split(":", 1)[0])
            self.assertEqual(("chapters/CON.md",), plan.unresolved[0]["sources"])

    def test_nfd_legacy_source_becomes_stable_unresolved_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = "chapters/e\u0301.md"
            materialize(root, {source: "Accent\n"})
            plan = migration.plan_migration(root)
            self.assertEqual((), plan.operations)
            self.assertEqual((source,), plan.unresolved[0]["sources"])
            self.assertTrue(plan.unresolved[0]["reason"].startswith("nonportable-source"))
            self.assertEqual(plan, migration.load_migration_plan(write_plan(root, plan.to_payload())))

    def test_planning_is_stable_unicode_safe_and_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materialize(root, {"chapters/ёж.md": "# Ёж\r\n", "unknown.bin": "bytes"})
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

            first = migration.plan_migration(root)
            second = migration.plan_migration(root)

            self.assertEqual(first, second)
            self.assertEqual(first.plan_hash, migration.canonical_plan_hash(first.to_payload()))
            self.assertEqual(
                before,
                {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()},
            )
            loaded = migration.load_migration_plan(write_plan(root, first.to_payload()))
            self.assertEqual(first, loaded)

    def test_control_character_unknown_path_is_stably_unresolved(self):
        for name in ("unknown\nrole.md", "unknown\x7frole.md"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                materialize(root, {name: "# Unknown\n"})
                plan = migration.plan_migration(root)
                self.assertEqual("unknown-role", plan.unresolved[0]["reason"])

    def test_plain_manifest_is_upgradeable_but_malformed_frontmatter_is_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materialize(root, {"project.md": "Legacy instructions\r\n", "chapters/a.md": "A\n"})
            plan = migration.plan_migration(root)
            self.assertFalse(any(item["reason"].startswith("manifest-upgrade") for item in plan.unresolved))
            self.assertIn(("project.md", "project.md", "preserve"), operation_pairs(plan))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materialize(root, {"project.md": "---\ntitle: broken\nBody\n"})
            plan = migration.plan_migration(root)
            self.assertTrue(any(item["reason"].startswith("manifest-upgrade") for item in plan.unresolved))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_planning_does_not_follow_links_or_nested_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            external = root.parent / f"{root.name}-external.md"
            try:
                external.write_text("External\n", encoding="utf-8")
                (root / "chapters").mkdir()
                (root / "chapters" / "link.md").symlink_to(external)
                materialize(root, {"chapters/nested/project.md": "---\nschema-version: 1\n---\n", "chapters/nested/x.md": "X\n"})
                plan = migration.plan_migration(root)
                self.assertFalse(any("link.md" in op.source or "nested" in op.source for op in plan.operations))
            finally:
                external.unlink(missing_ok=True)


class MigrationPlanLoadingTests(unittest.TestCase):
    def base_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "plan-version": 1,
            "source-schema": 0,
            "target-schema": 1,
            "operations": [
                {"source": "chapters/one.md", "destination": "story/chapters/one.md", "action": "move"}
            ],
            "unresolved": [],
        }
        payload["plan-hash"] = migration.canonical_plan_hash(payload)
        return payload

    def test_round_trip_loads_strict_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = self.base_payload()
            loaded = migration.load_migration_plan(write_plan(root, payload))
            self.assertEqual(payload, loaded.to_payload())

    def test_loader_accepts_only_strict_content_bearing_merge_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = self.base_payload()
            payload["operations"] = [
                {
                    "sources": ["kb/timeline/a.md", "kb/timeline/b.md"],
                    "destination": "kb/continuity/timeline.md",
                    "action": "merge",
                    "content": "---\ntitle: Timeline\n---\n# Reviewed\n",
                }
            ]
            loaded = migration.load_migration_plan(write_plan(root, payload))
            self.assertEqual(payload, loaded.to_payload())

            for mutation in (
                lambda operation: operation.pop("content"),
                lambda operation: operation.__setitem__("sources", []),
                lambda operation: operation.__setitem__("content", 1),
                lambda operation: operation.__setitem__("source", "extra.md"),
            ):
                with self.subTest(mutation=mutation):
                    candidate = self.base_payload()
                    operation = dict(payload["operations"][0])
                    mutation(operation)
                    candidate["operations"] = [operation]
                    with self.assertRaises(migration.MigrationPlanError):
                        migration.load_migration_plan(write_plan(root, candidate))

    def test_loader_rejects_unknown_missing_and_type_invalid_keys(self):
        mutations = (
            lambda value: value.__setitem__("unknown", 1),
            lambda value: value.pop("unresolved"),
            lambda value: value.__setitem__("operations", {}),
            lambda value: value.__setitem__("source-schema", True),
            lambda value: value["operations"][0].__setitem__("unknown", 1),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as directory:
                payload = self.base_payload()
                mutate(payload)
                with self.assertRaises(migration.MigrationPlanError):
                    migration.load_migration_plan(write_plan(Path(directory), payload))

    def test_loader_rejects_versions_and_hash_mismatch(self):
        for key, value in (("plan-version", 2), ("target-schema", 2), ("source-schema", 2)):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                payload = self.base_payload()
                payload[key] = value
                with self.assertRaises(migration.MigrationPlanError):
                    migration.load_migration_plan(write_plan(Path(directory), payload))
        with tempfile.TemporaryDirectory() as directory:
            payload = self.base_payload()
            payload["operations"][0]["destination"] = "story/chapters/tampered.md"
            with self.assertRaisesRegex(migration.MigrationPlanError, "hash mismatch"):
                migration.load_migration_plan(write_plan(Path(directory), payload, rehash=False))

    def test_loader_rejects_nonportable_absolute_and_traversal_paths(self):
        invalid = (
            "../one.md",
            "/one.md",
            "C:/one.md",
            "story\\one.md",
            "story/CON.md",
            "story/trailing. ",
            "story/nul\0name.md",
            "story/new\nline.md",
            "story/delete\x7fname.md",
        )
        for value in invalid:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                payload = self.base_payload()
                payload["operations"][0]["destination"] = value
                with self.assertRaises(migration.MigrationPlanError):
                    migration.load_migration_plan(write_plan(Path(directory), payload))

    def test_loader_rejects_duplicate_and_case_colliding_destinations(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = self.base_payload()
            payload["operations"].append(
                {"source": "chapters/two.md", "destination": "Story/Chapters/ONE.md", "action": "move"}
            )
            with self.assertRaisesRegex(migration.MigrationPlanError, "case-colliding destination"):
                migration.load_migration_plan(write_plan(Path(directory), payload))

    def test_loader_rejects_source_destination_action_mismatch(self):
        cases = (("same.md", "same.md", "move"), ("one.md", "two.md", "preserve"))
        for source, destination, action in cases:
            with self.subTest(action=action), tempfile.TemporaryDirectory() as directory:
                payload = self.base_payload()
                payload["operations"] = [{"source": source, "destination": destination, "action": action}]
                with self.assertRaisesRegex(migration.MigrationPlanError, "source=destination"):
                    migration.load_migration_plan(write_plan(Path(directory), payload))

    def test_loader_validates_complete_plan_before_resolving_nested_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materialize(root, {"nested/project.md": "---\nschema-version: 1\n---\n", "nested/chapter.md": "X\n"})
            payload = self.base_payload()
            payload["operations"] = [
                {"source": "nested/chapter.md", "destination": "story/chapters/chapter.md", "action": "move"}
            ]
            with self.assertRaisesRegex(migration.MigrationPlanError, "nested project boundary"):
                migration.load_migration_plan(write_plan(root, payload), root=root)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_loader_refuses_symlink_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = write_plan(root, self.base_payload())
            linked = root / "linked-plan.json"
            linked.symlink_to(real)
            with self.assertRaisesRegex(migration.MigrationPlanError, "real file"):
                migration.load_migration_plan(linked)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_loader_refuses_plan_through_symlinked_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real_parent = root / "real"
            real_parent.mkdir()
            plan = write_plan(real_parent, self.base_payload())
            linked_parent = root / "linked"
            linked_parent.symlink_to(real_parent, target_is_directory=True)
            with self.assertRaisesRegex(migration.MigrationPlanError, "directory link"):
                migration.load_migration_plan(linked_parent / plan.name)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_loader_does_not_follow_operation_parent_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            external = root / "external"
            external.mkdir()
            (root / "linked").symlink_to(external, target_is_directory=True)
            payload = self.base_payload()
            payload["operations"] = [
                {"source": "linked/one.md", "destination": "story/chapters/one.md", "action": "move"}
            ]
            with self.assertRaisesRegex(migration.MigrationPlanError, "symlink boundary"):
                migration.load_migration_plan(write_plan(root, payload), root=root)

    def test_explicit_root_controls_nested_boundary_not_plan_storage_location(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as external_directory:
            root = Path(directory)
            materialize(root, {"nested/project.md": "---\nschema-version: 1\n---\n"})
            payload = self.base_payload()
            payload["operations"] = [
                {"source": "nested/chapter.md", "destination": "story/chapters/chapter.md", "action": "move"}
            ]

            storage = root / "plans"
            storage.mkdir()
            stored_inside = write_plan(storage, payload)
            self.assertEqual("nested/chapter.md", migration.load_migration_plan(stored_inside).operations[0].source)
            with self.assertRaisesRegex(migration.MigrationPlanError, "nested project boundary"):
                migration.load_migration_plan(stored_inside, root=root)

            stored_external = write_plan(Path(external_directory), payload)
            with self.assertRaisesRegex(migration.MigrationPlanError, "nested project boundary"):
                migration.load_migration_plan(stored_external, root=root)


if __name__ == "__main__":
    unittest.main()
