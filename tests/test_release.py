import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.release import ReleaseError, bump_semver, run_release


class FakeRunner:
    def __init__(self, *, status="", branch="main", tags="", fail_on=None):
        self.status = status
        self.branch = branch
        self.tags = tags
        self.fail_on = fail_on
        self.calls = []

    def __call__(self, command, *, cwd, capture_output=False):
        command = list(command)
        self.calls.append((command, Path(cwd), capture_output))
        if self.fail_on is not None and command == self.fail_on:
            raise subprocess.CalledProcessError(1, command)
        stdout = ""
        if command == ["git", "status", "--porcelain", "--untracked-files=normal"]:
            stdout = self.status
        elif command == ["git", "branch", "--show-current"]:
            stdout = self.branch
        elif command[:3] == ["git", "tag", "--list"]:
            stdout = self.tags
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")


class ReleaseVersionTests(unittest.TestCase):
    def test_bump_semver(self):
        self.assertEqual(bump_semver("0.5.9", "patch"), "0.5.10")
        self.assertEqual(bump_semver("0.5.9", "minor"), "0.6.0")
        self.assertEqual(bump_semver("0.5.9", "major"), "1.0.0")

    def test_bump_rejects_non_semver(self):
        for version in ("0.5", "v0.5.9", "01.2.3", "1.02.3", "1.2.03"):
            with self.subTest(version=version), self.assertRaisesRegex(
                ValueError, "strict semantic version"
            ):
                bump_semver(version, "patch")

    def test_bump_rejects_unknown_part(self):
        with self.assertRaisesRegex(ValueError, "unknown version part"):
            bump_semver("0.5.9", "build")


class ReleaseOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo_root = Path(self.temporary.name)
        self.manifest_path = (
            self.repo_root
            / "plugins/creative-writing-skills/.codex-plugin/plugin.json"
        )
        self.manifest_path.parent.mkdir(parents=True)
        self.manifest_path.write_text(
            json.dumps({"name": "creative-writing-skills", "version": "0.5.9"})
            + "\n"
        )

    def test_release_runs_checks_before_commit_and_does_not_push_by_default(self):
        fake_runner = FakeRunner()
        version_during_tests = []

        def runner(command, *, cwd, capture_output=False):
            if list(command) == [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-v",
            ]:
                version_during_tests.append(
                    json.loads(self.manifest_path.read_text())["version"]
                )
            return fake_runner(
                command,
                cwd=cwd,
                capture_output=capture_output,
            )

        version = run_release(self.repo_root, "patch", runner=runner)

        self.assertEqual("0.5.10", version)
        self.assertEqual(
            "0.5.10", json.loads(self.manifest_path.read_text())["version"]
        )
        self.assertEqual(["0.5.10"], version_during_tests)
        commands = [call[0] for call in fake_runner.calls]
        self.assertEqual(
            [
                ["git", "status", "--porcelain", "--untracked-files=normal"],
                ["git", "branch", "--show-current"],
                ["git", "tag", "--list", "v0.5.10"],
                [sys.executable, "scripts/sync_claude_distribution.py", "--apply"],
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-v",
                ],
                [sys.executable, "scripts/validate_distribution.py"],
                [sys.executable, "scripts/sync_claude_distribution.py", "--check"],
                [sys.executable, "scripts/create_skill_zips.py"],
                [
                    "git",
                    "add",
                    "--",
                    "plugins/creative-writing-skills/.codex-plugin/plugin.json",
                    "cw/.claude-plugin/plugin.json",
                    ".claude-plugin/marketplace.json",
                ],
                ["git", "commit", "-m", "Release v0.5.10"],
                ["git", "tag", "v0.5.10"],
            ],
            commands,
        )
        self.assertTrue(
            all(call[1] == self.repo_root.resolve() for call in fake_runner.calls)
        )

    def test_push_is_explicit_and_atomic(self):
        runner = FakeRunner()

        run_release(self.repo_root, "minor", push=True, runner=runner)

        self.assertEqual(
            ["git", "push", "--atomic", "origin", "main", "v0.6.0"],
            runner.calls[-1][0],
        )

    def test_dirty_worktree_is_rejected_before_manifest_changes(self):
        original = self.manifest_path.read_bytes()
        runner = FakeRunner(status=" M README.md\n")

        with self.assertRaisesRegex(ReleaseError, "worktree must be clean"):
            run_release(self.repo_root, "patch", runner=runner)

        self.assertEqual(original, self.manifest_path.read_bytes())
        self.assertEqual(1, len(runner.calls))

    def test_non_main_branch_is_rejected_before_manifest_changes(self):
        original = self.manifest_path.read_bytes()
        runner = FakeRunner(branch="feature/release")

        with self.assertRaisesRegex(ReleaseError, "branch must be main"):
            run_release(self.repo_root, "patch", runner=runner)

        self.assertEqual(original, self.manifest_path.read_bytes())
        self.assertEqual(2, len(runner.calls))

    def test_existing_tag_is_rejected_before_manifest_changes(self):
        original = self.manifest_path.read_bytes()
        runner = FakeRunner(tags="v0.5.10\n")

        with self.assertRaisesRegex(ReleaseError, "tag v0.5.10 already exists"):
            run_release(self.repo_root, "patch", runner=runner)

        self.assertEqual(original, self.manifest_path.read_bytes())
        self.assertEqual(3, len(runner.calls))

    def test_failed_check_restores_manifest_and_never_commits_or_tags(self):
        validation = [sys.executable, "scripts/validate_distribution.py"]
        original = self.manifest_path.read_bytes()
        runner = FakeRunner(fail_on=validation)

        with self.assertRaises(subprocess.CalledProcessError):
            run_release(self.repo_root, "patch", runner=runner)

        self.assertEqual(original, self.manifest_path.read_bytes())
        commands = [call[0] for call in runner.calls]
        self.assertNotIn(["git", "commit", "-m", "Release v0.5.10"], commands)
        self.assertNotIn(["git", "tag", "v0.5.10"], commands)
        self.assertNotIn(
            ["git", "push", "--atomic", "origin", "main", "v0.5.10"],
            commands,
        )
        self.assertEqual(
            [
                "git",
                "restore",
                "--worktree",
                "--",
                "cw",
                ".claude-plugin/marketplace.json",
            ],
            commands[-1],
        )


if __name__ == "__main__":
    unittest.main()
