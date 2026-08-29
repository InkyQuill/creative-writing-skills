import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import app, context, project, scaffold


class ContextSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "project"
        for relative, data in scaffold.render_scaffold("Context", "en").items():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (self.root / ".creative-writing/context").mkdir(parents=True)
        (self.root / ".creative-writing/transactions").mkdir(parents=True)
        self.write("kb/characters/mara.md", "---\ntitle: Mara\n---\nMara.\n")
        self.write("kb/characters/ivo.md", "---\ntitle: Ivo\n---\nIvo.\n")
        self.write(
            "story/chapters/ch-004.md",
            "---\nnumber: 4\n---\nVisible prose.\n<hidden>author-only\nsecret</hidden>\n",
        )
        self.write(
            "kb/continuity/state.md",
            "---\ntitle: State\n---\n# State\n\n"
            "| character | fact |\n|---|---|\n"
            "| mara | knows the gate |\n| ivo | knows the crown |\n",
        )
        self.project = project.discover_project(self.root)

    def write(self, relative: str, text: str) -> Path:
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def plan(self, role: str = "reader") -> context.ContextPlan:
        return context.plan_context(
            self.project, "chapter", "story/chapters/ch-004.md", role
        )

    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        status = app.run(argv, cwd=self.root, stdout=stdout, stderr=stderr)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_reader_removes_only_balanced_hidden_and_preserves_visible_material(self):
        result = context.render_snapshot(self.project, self.plan())
        chapter = result.files["story/chapters/ch-004.md"].decode("utf-8")

        self.assertIn("Visible prose.", chapter)
        self.assertNotIn("author-only", chapter)
        self.assertNotIn("<hidden>", chapter)
        self.assertTrue(result.boundary_warning)
        self.assertEqual([], list((self.root / ".creative-writing/transactions").iterdir()))

    def test_character_filters_recognized_tables_only_and_normalizes_id(self):
        result = context.render_snapshot(self.project, self.plan("character:MARA"))
        state = result.files["kb/continuity/state.md"].decode("utf-8")

        self.assertIn("# State", state)
        self.assertIn("| character | fact |", state)
        self.assertIn("| mara | knows the gate |", state)
        self.assertNotIn("| ivo | knows the crown |", state)

    def test_unrecognized_table_is_preserved_and_does_not_infer_knowledge(self):
        self.write(
            "kb/world/place.md",
            "---\n---\n| person | fact |\n|---|---|\n| ivo | visible |\n",
        )
        plan = context.plan_context(self.project, "kb", "kb/world/place.md", "character:mara")
        result = context.render_snapshot(self.project, plan)
        self.assertIn("| ivo | visible |", result.files["kb/world/place.md"].decode())

    def test_broken_nested_and_crossed_source_tags_fail_before_writing(self):
        for body in (
            "<hidden>broken\n",
            "<hidden>outer <hidden>inner</hidden></hidden>\n",
            "<hidden><AI>x</hidden></AI>\n",
        ):
            with self.subTest(body=body):
                self.write("story/chapters/ch-004.md", f"---\nnumber: 4\n---\n{body}")
                before = tuple((self.root / ".creative-writing/context").iterdir())
                with self.assertRaises(context.ContextSnapshotError):
                    context.render_snapshot(self.project, self.plan())
                self.assertEqual(before, tuple((self.root / ".creative-writing/context").iterdir()))

    def test_hidden_like_malformed_or_case_variant_markup_fails_closed(self):
        for body in (
            "<Hidden>case variant</Hidden>\n",
            "<hidden visibility=author>attribute</hidden>\n",
            "<hidden broken\n",
            "closing </hidden > variant\n",
            "<hiddenly>prefix collision\n",
        ):
            with self.subTest(body=body):
                self.write("story/chapters/ch-004.md", f"---\nnumber: 4\n---\n{body}")
                with self.assertRaises(context.ContextSnapshotError):
                    context.render_snapshot(self.project, self.plan())
                self.assertEqual([], list((self.root / ".creative-writing/context").iterdir()))

    def test_malformed_table_and_trusted_role_are_refused(self):
        self.write(
            "story/chapters/ch-004.md",
            "---\nnumber: 4\n---\n| character | fact |\n|---|---|\n| mara | broken | extra |\n",
        )
        with self.assertRaises(context.ContextSnapshotError):
            context.render_snapshot(self.project, self.plan("character:mara"))
        with self.assertRaisesRegex(context.ContextSnapshotError, "trusted"):
            context.render_snapshot(self.project, self.plan("trusted"))

    def test_reader_preserves_repairable_malformed_visible_table(self):
        self.write(
            "story/chapters/ch-004.md",
            "---\nnumber: 4\n---\n| person | fact |\n|---|---|\n| visible | row | extra |\n",
        )
        result = context.render_snapshot(self.project, self.plan("reader"))
        self.assertIn("| visible | row | extra |", result.files["story/chapters/ch-004.md"].decode())

    def test_manifest_id_order_and_hashes_are_stable_and_sources_are_immutable(self):
        source_before = {
            path: (self.root / path).read_bytes()
            for path in self.plan().required + self.plan().suggested
        }
        first = context.render_snapshot(self.project, self.plan())
        second = context.render_snapshot(self.project, self.plan())

        self.assertEqual(first.snapshot_id, second.snapshot_id)
        self.assertEqual(first.manifest, second.manifest)
        self.assertEqual(source_before, {path: (self.root / path).read_bytes() for path in source_before})
        self.assertEqual(list(source_before), [item["path"] for item in first.manifest["sources"]])
        for item in first.manifest["sources"]:
            raw = source_before[item["path"]]
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item["exact_hash"])
            self.assertEqual(
                hashlib.sha256(first.files[item["path"]]).hexdigest(),
                item["snapshot_exact_hash"],
            )

    def test_status_reports_stale_corrupt_missing_and_symlink_without_check_all(self):
        result = context.render_snapshot(self.project, self.plan())
        self.write("story/chapters/ch-004.md", "---\nnumber: 4\n---\nChanged.\n")
        findings = context.snapshot_status(self.project)
        self.assertIn("CW-CONTEXT-STALE", {item.code for item in findings})

        manifest = self.root / result.directory / "manifest.json"
        manifest.write_text("{broken", encoding="utf-8")
        self.assertIn("CW-CONTEXT-CORRUPT", {item.code for item in context.snapshot_status(self.project)})

        status, output, error = self.run_cli(["check", "all", "--format", "json"])
        self.assertIn(status, {0, 1})
        self.assertEqual("", error)
        self.assertNotIn("context", json.loads(output)["checks"])

    def test_status_replans_and_detects_new_portable_collision(self):
        self.write(
            "story/chapters/ch-004.md",
            "---\nnumber: 4\nrelated:\n  - kb/world/place.md\n---\nVisible.\n",
        )
        self.write("kb/world/place.md", "---\n---\nPlace.\n")
        context.render_snapshot(self.project, self.plan())
        self.write("kb/world/Place.md", "---\n---\nCollision.\n")
        findings = context.snapshot_status(self.project)
        self.assertIn("CW-CONTEXT-STALE", {item.code for item in findings})

    def test_status_preserves_and_compares_exact_unresolved_warning_state(self):
        self.write(
            "story/chapters/ch-004.md",
            "---\nnumber: 4\nrelated:\n  - kb/world/missing.md\n---\nVisible.\n",
        )
        plan = self.plan()
        self.assertTrue(plan.unresolved)
        result = context.render_snapshot(self.project, plan)

        self.assertEqual(list(plan.unresolved), result.manifest["unresolved"])
        self.assertEqual(list(plan.warnings), result.manifest["warnings"])
        self.assertEqual([], context.snapshot_status(self.project))

        self.write("kb/world/missing.md", "---\n---\nNow present.\n")
        self.assertIn(
            "CW-CONTEXT-STALE",
            {item.code for item in context.snapshot_status(self.project)},
        )

    def test_retry_removes_only_partial_with_matching_owner_marker(self):
        first = context.render_snapshot(self.project, self.plan())
        stable = self.root / first.directory
        token = "a" * 32
        partial = stable.with_name(f".partial-{first.snapshot_id}-{token}")
        partial.mkdir()
        (partial / context._PARTIAL_OWNER).write_bytes(
            context._canonical_json(
                {
                    "kind": context._PARTIAL_OWNER_KIND,
                    "snapshot_id": first.snapshot_id,
                    "token": token,
                }
            )
            + b"\n"
        )
        second = context.render_snapshot(self.project, self.plan())
        self.assertEqual(first.snapshot_id, second.snapshot_id)
        self.assertTrue((self.root / second.directory / "manifest.json").is_file())
        self.assertFalse(partial.exists())

    def test_retry_preserves_foreign_partial_with_recognized_filename(self):
        first = context.render_snapshot(self.project, self.plan())
        foreign = (self.root / first.directory).with_name(
            f".partial-{first.snapshot_id}-{'b' * 32}"
        )
        foreign.mkdir()
        marker = foreign / "keep"
        marker.write_text("foreign", encoding="utf-8")

        reused = context.render_snapshot(self.project, self.plan())

        self.assertEqual(first.snapshot_id, reused.snapshot_id)
        self.assertEqual("foreign", marker.read_text(encoding="utf-8"))

    def test_retry_recovers_complete_markerless_crash_partial(self):
        first = context.render_snapshot(self.project, self.plan())
        stable = self.root / first.directory
        partial = stable.with_name(f".partial-{first.snapshot_id}-{'c' * 32}")
        stable.rename(partial)

        retried = context.render_snapshot(self.project, self.plan())

        self.assertEqual(first.snapshot_id, retried.snapshot_id)
        self.assertFalse(partial.exists())
        self.assertTrue((self.root / retried.directory / "manifest.json").is_file())

    def test_capability_fallback_keeps_snapshot_status_and_cleanup_working(self):
        with mock.patch.object(context.os, "supports_dir_fd", set()):
            result = context.render_snapshot(self.project, self.plan())
            self.assertEqual([], context.snapshot_status(self.project))
            cleaned = context.clean_context(self.project, apply=True)
        self.assertEqual("applied", cleaned.status)
        self.assertFalse((self.root / result.directory).exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_render_reads_held_source_descriptor_across_directory_swap(self):
        plan = self.plan()
        chapters = self.root / "story/chapters"
        held = self.root / "story/chapters-held"
        outside = Path(self.temporary.name) / "outside-chapters"
        outside.mkdir()
        (outside / "ch-004.md").write_text("OUTSIDE SECRET", encoding="utf-8")
        marker = outside / "keep"
        marker.write_text("outside", encoding="utf-8")
        original = context._open_child_directory
        swapped = False

        def race(parent, name: str, label: str):
            nonlocal swapped
            child = original(parent, name, label)
            if not swapped and parent.path == self.root / "story" and name == "chapters":
                chapters.rename(held)
                chapters.symlink_to(outside, target_is_directory=True)
                swapped = True
            return child

        with mock.patch("cwcli.context._open_child_directory", side_effect=race):
            result = context.render_snapshot(self.project, plan)

        self.assertIn("Visible prose.", result.files["story/chapters/ch-004.md"].decode())
        self.assertNotIn("OUTSIDE SECRET", result.files["story/chapters/ch-004.md"].decode())
        self.assertEqual("outside", marker.read_text(encoding="utf-8"))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_status_reads_held_source_descriptor_across_directory_swap(self):
        context.render_snapshot(self.project, self.plan())
        chapters = self.root / "story/chapters"
        held = self.root / "story/chapters-held"
        outside = Path(self.temporary.name) / "outside-status"
        outside.mkdir()
        (outside / "ch-004.md").write_text("OUTSIDE CHANGED", encoding="utf-8")
        marker = outside / "keep"
        marker.write_text("outside", encoding="utf-8")
        original = context._open_child_directory
        swapped = False

        def race(parent, name: str, label: str):
            nonlocal swapped
            child = original(parent, name, label)
            if not swapped and parent.path == self.root / "story" and name == "chapters":
                chapters.rename(held)
                chapters.symlink_to(outside, target_is_directory=True)
                swapped = True
            return child

        with mock.patch("cwcli.context._open_child_directory", side_effect=race):
            findings = context.snapshot_status(self.project)

        self.assertFalse(any("snapshot source changed" in item.message for item in findings))
        self.assertEqual("outside", marker.read_text(encoding="utf-8"))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_fallback_source_swap_fails_closed_and_closes_descriptors(self):
        plan = self.plan()
        chapters = self.root / "story/chapters"
        held = self.root / "story/chapters-held"
        outside = Path(self.temporary.name) / "outside-fallback"
        outside.mkdir()
        (outside / "ch-004.md").write_text("OUTSIDE SECRET", encoding="utf-8")
        marker = outside / "keep"
        marker.write_text("outside", encoding="utf-8")
        original = context._open_child_directory
        swapped = False
        fd_root = Path("/proc/self/fd")
        before_fds = len(list(fd_root.iterdir())) if fd_root.is_dir() else None

        def race(parent, name: str, label: str):
            nonlocal swapped
            child = original(parent, name, label)
            if not swapped and parent.path == self.root / "story" and name == "chapters":
                chapters.rename(held)
                chapters.symlink_to(outside, target_is_directory=True)
                swapped = True
            return child

        with mock.patch.object(context.os, "supports_dir_fd", set()), mock.patch(
            "cwcli.context._open_child_directory", side_effect=race
        ):
            with self.assertRaises(context.ContextSnapshotError):
                context.render_snapshot(self.project, plan)

        self.assertEqual("outside", marker.read_text(encoding="utf-8"))
        if before_fds is not None:
            self.assertEqual(before_fds, len(list(fd_root.iterdir())))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_fallback_cleanup_reparse_swap_fails_closed_and_closes_descriptors(self):
        result = context.render_snapshot(self.project, self.plan())
        snapshot = self.root / result.directory
        files = snapshot / "files"
        held = snapshot / "files-held"
        outside = Path(self.temporary.name) / "outside-child-cleanup"
        outside.mkdir()
        marker = outside / "keep"
        marker.write_text("outside", encoding="utf-8")
        original = context._remove_directory_contents
        swapped = False
        fd_root = Path("/proc/self/fd")
        before_fds = len(list(fd_root.iterdir())) if fd_root.is_dir() else None

        def race(handle):
            nonlocal swapped
            if not swapped and handle.path == snapshot:
                files.rename(held)
                files.symlink_to(outside, target_is_directory=True)
                swapped = True
            return original(handle)

        with mock.patch.object(context.os, "supports_dir_fd", set()), mock.patch(
            "cwcli.context._remove_directory_contents", side_effect=race
        ):
            with self.assertRaises(context.ContextSnapshotError):
                context.clean_context(self.project, apply=True)

        self.assertEqual("outside", marker.read_text(encoding="utf-8"))
        self.assertTrue(files.is_symlink())
        if before_fds is not None:
            self.assertEqual(before_fds, len(list(fd_root.iterdir())))

    def test_publication_uses_macos_no_replace_fallback_when_renameat2_is_absent(self):
        calls: list[tuple[object, ...]] = []

        class FakeLibc:
            def renameatx_np(self, *args):
                calls.append(args)
                return 0

        cache = context._cache_root(self.project, create=True)
        assert cache is not None
        try:
            with mock.patch("cwcli.context.ctypes.CDLL", return_value=FakeLibc()):
                context._rename_no_replace(cache, "owned-partial", "stable")
        finally:
            cache.close()

        self.assertEqual(1, len(calls))
        self.assertEqual(0x00000004, calls[0][-1])

    def test_windows_fallback_does_not_open_directory_descriptors(self):
        original_open = context.os.open

        def reject_directory_open(path, flags, *args, **kwargs):
            if kwargs.get("dir_fd") is None and Path(path).is_dir():
                raise AssertionError(f"unsupported directory open: {path}")
            return original_open(path, flags, *args, **kwargs)

        with mock.patch.object(context.os, "supports_dir_fd", set()), mock.patch(
            "cwcli.context._is_windows", return_value=True
        ), mock.patch("cwcli.context.os.open", side_effect=reject_directory_open):
            result = context.render_snapshot(self.project, self.plan())
            self.assertEqual([], context.snapshot_status(self.project))
            cleaned = context.clean_context(self.project, apply=True)

        self.assertEqual("applied", cleaned.status)
        self.assertFalse((self.root / result.directory).exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_cleanup_held_snapshot_detects_name_swap_and_preserves_outside(self):
        result = context.render_snapshot(self.project, self.plan())
        snapshot = self.root / result.directory
        held = snapshot.with_name("held-snapshot")
        outside = Path(self.temporary.name) / "outside-cleanup"
        outside.mkdir()
        marker = outside / "keep"
        marker.write_text("outside", encoding="utf-8")
        original = context._remove_directory_contents
        swapped = False

        def race(handle):
            nonlocal swapped
            if not swapped and handle.path == snapshot:
                snapshot.rename(held)
                snapshot.symlink_to(outside, target_is_directory=True)
                swapped = True
            return original(handle)

        with mock.patch("cwcli.context._remove_directory_contents", side_effect=race):
            with self.assertRaises(context.ContextSnapshotError):
                context.clean_context(self.project, apply=True)

        self.assertEqual("outside", marker.read_text(encoding="utf-8"))
        self.assertTrue(snapshot.is_symlink())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_status_does_not_follow_symlink_snapshot_or_source(self):
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        (outside / "manifest.json").write_text("{}", encoding="utf-8")
        (self.root / ".creative-writing/context/link").symlink_to(outside, target_is_directory=True)
        self.assertIn("CW-CONTEXT-UNSAFE", {item.code for item in context.snapshot_status(self.project)})

    def test_atomic_install_failure_leaves_no_partial_or_temporary_snapshot(self):
        with mock.patch("cwcli.context._write_to_handle", side_effect=OSError("injected")):
            with self.assertRaisesRegex(OSError, "injected"):
                context.render_snapshot(self.project, self.plan())
        self.assertEqual([], list((self.root / ".creative-writing/context").iterdir()))

    def test_publication_never_replaces_foreign_empty_destination(self):
        original = context._rename_no_replace

        def race(cache, source: str, destination: str):
            (cache.path / destination).mkdir()
            return original(cache, source, destination)

        with mock.patch("cwcli.context._rename_no_replace", side_effect=race):
            with self.assertRaises(context.ContextSnapshotError):
                context.render_snapshot(self.project, self.plan())

        entries = list((self.root / ".creative-writing/context").iterdir())
        self.assertEqual(1, len(entries))
        self.assertTrue(entries[0].is_dir())
        self.assertEqual([], list(entries[0].iterdir()))

    def test_publication_revalidates_and_reuses_concurrent_valid_winner(self):
        winner = context.render_snapshot(self.project, self.plan())
        destination = self.root / winner.directory
        held = destination.with_name("held-winner")
        destination.rename(held)
        original = context._rename_no_replace

        def race(cache, source: str, requested: str):
            held.rename(cache.path / requested)
            return original(cache, source, requested)

        with mock.patch("cwcli.context._rename_no_replace", side_effect=race):
            reused = context.render_snapshot(self.project, self.plan())

        self.assertEqual(winner.snapshot_id, reused.snapshot_id)
        self.assertEqual(winner.manifest, reused.manifest)
        self.assertTrue(destination.is_dir())

    def test_cli_snapshot_and_cleanup_preview_apply_are_derived_only(self):
        status, output, error = self.run_cli(
            ["context", "chapter", "story/chapters/ch-004.md", "--as", "reader", "--snapshot", "--format", "json"]
        )
        self.assertEqual((0, ""), (status, error))
        payload = json.loads(output)
        self.assertEqual("created", payload["snapshot"]["status"])
        snapshot_dir = self.root / payload["snapshot"]["directory"]
        self.assertTrue(snapshot_dir.is_dir())
        self.assertEqual([], list((self.root / ".creative-writing/transactions").iterdir()))

        status, output, error = self.run_cli(["clean-context", "--format", "json"])
        self.assertEqual((0, ""), (status, error))
        preview = json.loads(output)
        self.assertEqual("preview", preview["status"])
        self.assertEqual([], preview["findings"])
        self.assertTrue(snapshot_dir.exists())

    def test_cleanup_preview_includes_current_staleness(self):
        result = context.render_snapshot(self.project, self.plan())
        self.write("story/chapters/ch-004.md", "---\nnumber: 4\n---\nChanged.\n")
        status, output, error = self.run_cli(["clean-context", "--format", "json"])
        self.assertEqual((0, ""), (status, error))
        payload = json.loads(output)
        self.assertIn(result.directory, payload["directories"])
        self.assertIn("CW-CONTEXT-STALE", {item["code"] for item in payload["findings"]})

        status, output, error = self.run_cli(["clean-context", "--apply", "--format", "json"])
        self.assertEqual((0, ""), (status, error))
        self.assertEqual("applied", json.loads(output)["status"])
        self.assertFalse((self.root / result.directory).exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_cleanup_refuses_symlink_and_unknown_entries_without_removing_anything(self):
        result = context.render_snapshot(self.project, self.plan())
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        (outside / "keep").write_text("keep", encoding="utf-8")
        (self.root / ".creative-writing/context/escape").symlink_to(outside, target_is_directory=True)

        status, _output, error = self.run_cli(["clean-context", "--apply"])
        self.assertEqual(2, status)
        self.assertIn("unsafe", error)
        self.assertTrue((self.root / result.directory).exists())
        self.assertEqual("keep", (outside / "keep").read_text(encoding="utf-8"))

    def test_cleanup_refuses_unknown_empty_directory_and_preserves_snapshot(self):
        result = context.render_snapshot(self.project, self.plan())
        snapshot = self.root / result.directory
        unknown = snapshot / "unknown-empty"
        unknown.mkdir()

        status, _output, error = self.run_cli(["clean-context", "--apply"])

        self.assertEqual(2, status)
        self.assertIn("unknown", error)
        self.assertTrue(unknown.is_dir())
        self.assertTrue((snapshot / "manifest.json").is_file())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_all_cache_operations_refuse_symlinked_protected_ancestor_without_touching_outside(self):
        protected = self.root / ".creative-writing"
        real = self.root / ".creative-writing-real"
        protected.rename(real)
        outside = Path(self.temporary.name) / "outside-cache"
        (outside / "context").mkdir(parents=True)
        marker = outside / "keep"
        marker.write_text("outside", encoding="utf-8")
        protected.symlink_to(outside, target_is_directory=True)

        with self.assertRaises(context.ContextSnapshotError):
            context.render_snapshot(self.project, self.plan())
        findings = context.snapshot_status(self.project)
        self.assertIn("CW-CONTEXT-UNSAFE", {item.code for item in findings})
        status, _output, error = self.run_cli(["clean-context", "--apply"])

        self.assertEqual(2, status)
        self.assertIn("unsafe", error)
        self.assertEqual("outside", marker.read_text(encoding="utf-8"))
        self.assertEqual([], list((outside / "context").iterdir()))


if __name__ == "__main__":
    unittest.main()
