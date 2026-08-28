import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .helpers import app
from cwcli import scaffold, schema


class InitCommandTests(unittest.TestCase):
    def run_cli(self, cwd: Path, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        status = app.run(argv, cwd=cwd, stdout=stdout, stderr=stderr)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_absent_target_preview_is_read_only_and_apply_is_atomic_bootstrap(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "story-project"
            arguments = ["init", str(root), "--title", "Mine", "--language", "ru"]

            status, output, error = self.run_cli(parent, arguments)
            self.assertEqual(0, status)
            self.assertEqual("", error)
            self.assertFalse(root.exists())
            self.assertEqual(
                set(schema.SCAFFOLD_FILES)
                | {".creative-writing/context", ".creative-writing/transactions"},
                {operation["path"] for operation in json.loads(output)},
            )

            status, output, error = self.run_cli(parent, arguments + ["--apply", "--format", "json"])
            result = json.loads(output)
            self.assertEqual(0, status)
            self.assertEqual("", error)
            self.assertEqual("committed", result["status"])
            self.assertTrue((root / "project.md").is_file())
            self.assertTrue((root / ".creative-writing/context").is_dir())
            self.assertTrue((root / ".creative-writing/transactions").is_dir())
            manifest = root / ".creative-writing/transactions" / result["transaction_id"] / "manifest.json"
            self.assertFalse(json.loads(manifest.read_text())["metadata"]["undoable"])

    def test_existing_folder_preserves_every_unknown_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "existing"
            root.mkdir()
            (root / "notes.txt").write_text("mine\n", encoding="utf-8")
            (root / "assets").mkdir()
            (root / "assets/image.bin").write_bytes(b"mine")

            status, output, error = self.run_cli(
                parent,
                ["init", str(root), "--title", "Mine", "--language", "ru", "--apply", "--format", "json"],
            )

            self.assertEqual(0, status)
            self.assertEqual("", error)
            self.assertEqual("committed", json.loads(output)["status"])
            self.assertEqual("mine\n", (root / "notes.txt").read_text())
            self.assertEqual(b"mine", (root / "assets/image.bin").read_bytes())

    def test_existing_empty_canonical_directories_are_safe_to_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "existing"
            (root / "story/chapters").mkdir(parents=True)

            status, _output, error = self.run_cli(
                parent,
                ["init", str(root), "--title", "Mine", "--language", "ru", "--apply"],
            )

            self.assertEqual(0, status)
            self.assertEqual("", error)
            self.assertTrue((root / "story/chapters/_index.md").is_file())

    def test_existing_protected_content_requires_migration_without_adoption(self):
        for relative, content_name in (
            (".creative-writing/context", "stale.json"),
            (".creative-writing/transactions", "corrupt-journal"),
        ):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                parent = Path(directory)
                root = parent / "existing"
                protected = root / relative
                protected.mkdir(parents=True)
                (protected / content_name).write_text("mine\n", encoding="utf-8")

                status, output, error = self.run_cli(
                    parent,
                    [
                        "init", str(root), "--title", "Mine", "--language", "ru",
                        "--apply", "--format", "json",
                    ],
                )

                self.assertEqual(2, status)
                self.assertEqual("", error)
                self.assertIn("cw migrate --plan", json.loads(output)["message"])
                self.assertEqual("mine\n", (protected / content_name).read_text())
                self.assertFalse((root / "project.md").exists())

    def test_populated_managed_root_uses_migration_guidance_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "existing"
            (root / "story").mkdir(parents=True)
            original = root / "story/mine.md"
            original.write_text("mine\n", encoding="utf-8")

            status, output, error = self.run_cli(
                parent,
                ["init", str(root), "--title", "Mine", "--language", "ru", "--apply", "--format", "json"],
            )

            self.assertEqual(2, status)
            self.assertEqual("", error)
            self.assertIn("cw migrate --plan", json.loads(output)["message"])
            self.assertEqual("mine\n", original.read_text())
            self.assertFalse((root / "project.md").exists())

    def test_incompatible_manifest_uses_migration_guidance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "existing"
            root.mkdir()
            (root / "project.md").write_text("---\nschema-version: 99\n---\n", encoding="utf-8")

            status, _output, error = self.run_cli(
                root.parent,
                ["init", str(root), "--title", "Mine", "--language", "ru", "--apply"],
            )

            self.assertEqual(2, status)
            self.assertIn("cw migrate --plan", error)
            self.assertEqual("---\nschema-version: 99\n---\n", (root / "project.md").read_text())

    def test_bootstrap_transaction_cannot_be_undone(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "story-project"
            status, output, _error = self.run_cli(
                parent,
                ["init", str(root), "--title", "Mine", "--language", "ru", "--apply", "--format", "json"],
            )
            transaction_id = json.loads(output)["transaction_id"]
            project_bytes = (root / "project.md").read_bytes()

            status, output, _error = self.run_cli(
                root, ["undo", transaction_id, "--apply", "--format", "json"]
            )

            self.assertEqual(1, status)
            self.assertIn("not undoable", json.loads(output)["message"])
            self.assertEqual(project_bytes, (root / "project.md").read_bytes())

    def test_absent_bootstrap_failure_never_installs_partial_target(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "story-project"
            with mock.patch.object(scaffold.os, "rename", side_effect=OSError("injected rename failure")):
                status, _output, error = self.run_cli(
                    parent,
                    ["init", str(root), "--title", "Mine", "--language", "ru", "--apply"],
                )

            self.assertEqual(2, status)
            self.assertIn("injected rename failure", error)
            self.assertFalse(root.exists())
            self.assertEqual([], list(parent.glob(".story-project.cw-init-*")))

    def test_parent_fsync_failure_reports_installed_success_and_retry_is_non_destructive(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "story-project"
            original_sync = scaffold._fsync_directory

            def fail_installed_parent(path: Path) -> bool:
                if path == parent and root.exists():
                    raise OSError("injected parent fsync failure")
                return original_sync(path)

            with mock.patch.object(scaffold, "_fsync_directory", side_effect=fail_installed_parent):
                status, output, error = self.run_cli(
                    parent,
                    [
                        "init", str(root), "--title", "Mine", "--language", "ru",
                        "--apply", "--format", "json",
                    ],
                )

            result = json.loads(output)
            self.assertEqual(0, status)
            self.assertEqual("", error)
            self.assertEqual("committed", result["status"])
            self.assertIn("durability could not be confirmed", result["diagnostics"][0])
            manifest = root / ".creative-writing/transactions" / result["transaction_id"] / "manifest.json"
            self.assertEqual("committed", json.loads(manifest.read_text())["state"])
            project_bytes = (root / "project.md").read_bytes()

            retry_status, retry_output, retry_error = self.run_cli(
                parent,
                [
                    "init", str(root), "--title", "Mine", "--language", "ru",
                    "--apply", "--format", "json",
                ],
            )
            self.assertEqual(2, retry_status)
            self.assertEqual("", retry_error)
            self.assertIn("cw migrate --plan", json.loads(retry_output)["message"])
            self.assertEqual(project_bytes, (root / "project.md").read_bytes())

    def test_plan_init_has_bootstrap_directory_metadata_and_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "story-project"

            plan = scaffold.plan_init(root, "Mine", "ru")

            self.assertFalse(root.exists())
            self.assertFalse(plan.metadata["undoable"])
            self.assertEqual(
                (".creative-writing/context", ".creative-writing/transactions"),
                plan.metadata["protected-directories"],
            )

    def test_existing_preview_lists_only_missing_protected_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "existing"
            (root / ".creative-writing/context").mkdir(parents=True)

            status, output, error = self.run_cli(
                parent,
                ["init", str(root), "--title", "Mine", "--language", "ru"],
            )

            self.assertEqual(0, status)
            self.assertEqual("", error)
            protected = {
                operation["path"]
                for operation in json.loads(output)
                if operation["op"] == "create-directory"
            }
            self.assertEqual({".creative-writing/transactions"}, protected)
            self.assertFalse((root / "project.md").exists())

    def test_preview_rejects_symlinked_target_ancestor(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            actual = parent / "actual"
            actual.mkdir()
            linked = parent / "linked"
            linked.symlink_to(actual, target_is_directory=True)

            status, _output, error = self.run_cli(
                parent,
                ["init", str(linked / "project"), "--title", "Mine", "--language", "ru"],
            )

            self.assertEqual(2, status)
            self.assertIn("symlink", error)
            self.assertFalse((actual / "project").exists())


if __name__ == "__main__":
    unittest.main()
