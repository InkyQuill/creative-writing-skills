import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.release import ReleaseError, bump_semver, main, run_command, run_release


class FakeRunner:
    def __init__(
        self,
        *,
        status="",
        branch="main",
        tags="",
        head="1111111111111111111111111111111111111111",
        fail_on=None,
    ):
        self.status = status
        self.branch = branch
        self.tags = tags
        self.head = head
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
        elif command == ["git", "rev-parse", "--verify", "HEAD"]:
            stdout = f"{self.head}\n"
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")


class SideEffectFailureRunner:
    def __init__(self, fail_command, *, foreign_tag_target=None):
        self.fail_command = fail_command
        self.foreign_tag_target = foreign_tag_target
        self.calls = []

    def __call__(self, command, *, cwd, capture_output=False):
        command = list(command)
        cwd = Path(cwd)
        self.calls.append(command)
        if command and command[0] == sys.executable:
            if command[1:] == ["scripts/sync_claude_distribution.py", "--apply"]:
                version = json.loads(
                    (cwd / "plugins/creative-writing-skills/.codex-plugin/plugin.json")
                    .read_text()
                )["version"]
                claude_manifest = cwd / "cw/.claude-plugin/plugin.json"
                claude_manifest.write_text(json.dumps({"version": version}) + "\n")
                marketplace = cwd / ".claude-plugin/marketplace.json"
                marketplace.write_text(
                    json.dumps({"metadata": {"version": version}}) + "\n"
                )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        if command == self.fail_command and self.foreign_tag_target is not None:
            run_command(
                ["git", "tag", command[-1], self.foreign_tag_target],
                cwd=cwd,
            )
            raise subprocess.CalledProcessError(97, command)

        result = run_command(command, cwd=cwd, capture_output=True)
        if command == self.fail_command:
            raise subprocess.CalledProcessError(97, command)
        return result


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
                ["git", "rev-parse", "--verify", "HEAD"],
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
        self.assertEqual(4, len(runner.calls))

    def test_failed_check_requests_restoration_and_never_commits_or_tags(self):
        validation = [sys.executable, "scripts/validate_distribution.py"]
        runner = FakeRunner(fail_on=validation)

        with self.assertRaises(subprocess.CalledProcessError):
            run_release(self.repo_root, "patch", runner=runner)

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
                "--source=1111111111111111111111111111111111111111",
                "--staged",
                "--worktree",
                "--",
                "plugins/creative-writing-skills/.codex-plugin/plugin.json",
                "cw",
                ".claude-plugin/marketplace.json",
            ],
            commands[-1],
        )


class ReleaseCliOutputTests(unittest.TestCase):
    def test_local_release_prints_existing_ref_publish_command(self):
        output = io.StringIO()
        with patch("scripts.release.run_release", return_value="0.5.10"):
            with redirect_stdout(output):
                status = main(["patch"], repo_root=Path("/unused"))

        self.assertEqual(0, status)
        self.assertEqual(
            "Created Release v0.5.10\n"
            "Publish it with: git push --atomic origin main v0.5.10\n",
            output.getvalue(),
        )


class ReleaseGitRecoveryTests(unittest.TestCase):
    def _git(self, root, *arguments, capture_output=True):
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=True,
            text=True,
            capture_output=capture_output,
        )

    def _make_repo(self, root):
        self._git(root, "init", "-b", "main")
        self._git(root, "config", "user.name", "Release Test")
        self._git(root, "config", "user.email", "release@example.com")
        self._git(root, "config", "commit.gpgsign", "false")
        manifest = root / "plugins/creative-writing-skills/.codex-plugin/plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            json.dumps({"name": "creative-writing-skills", "version": "0.5.9"})
            + "\n"
        )
        claude_manifest = root / "cw/.claude-plugin/plugin.json"
        claude_manifest.parent.mkdir(parents=True)
        claude_manifest.write_text(json.dumps({"version": "0.5.9"}) + "\n")
        marketplace = root / ".claude-plugin/marketplace.json"
        marketplace.parent.mkdir(parents=True)
        marketplace.write_text(
            json.dumps({"metadata": {"version": "0.5.9"}}) + "\n"
        )
        self._git(root, "add", ".")
        self._git(root, "commit", "-m", "Initial")
        return self._git(root, "rev-parse", "HEAD", capture_output=True).stdout.strip()

    def _assert_clean_original_state(self, root, original_head, *, tag_target=None):
        self.assertEqual(
            original_head,
            self._git(root, "rev-parse", "HEAD", capture_output=True).stdout.strip(),
        )
        self.assertEqual(
            "",
            self._git(
                root,
                "status",
                "--porcelain",
                "--untracked-files=normal",
                capture_output=True,
            ).stdout,
        )
        self.assertEqual(
            "0.5.9",
            json.loads(
                (
                    root
                    / "plugins/creative-writing-skills/.codex-plugin/plugin.json"
                ).read_text()
            )["version"],
        )
        self.assertEqual(
            "0.5.9",
            json.loads((root / "cw/.claude-plugin/plugin.json").read_text())["version"],
        )
        self.assertEqual(
            "0.5.9",
            json.loads((root / ".claude-plugin/marketplace.json").read_text())[
                "metadata"
            ]["version"],
        )
        tags = self._git(root, "tag", "--list", "v0.5.10", capture_output=True).stdout
        if tag_target is None:
            self.assertEqual("", tags)
        else:
            self.assertEqual("v0.5.10\n", tags)
            self.assertEqual(
                tag_target,
                self._git(
                    root,
                    "rev-parse",
                    "--verify",
                    "refs/tags/v0.5.10^{commit}",
                    capture_output=True,
                ).stdout.strip(),
            )

    def test_side_effect_failures_restore_head_index_worktree_and_created_tag(self):
        failures = {
            "add": [
                "git",
                "add",
                "--",
                "plugins/creative-writing-skills/.codex-plugin/plugin.json",
                "cw/.claude-plugin/plugin.json",
                ".claude-plugin/marketplace.json",
            ],
            "commit": ["git", "commit", "-m", "Release v0.5.10"],
            "tag": ["git", "tag", "v0.5.10"],
        }
        for label, fail_command in failures.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                original_head = self._make_repo(root)
                runner = SideEffectFailureRunner(fail_command)

                with self.assertRaises(subprocess.CalledProcessError):
                    run_release(root, "patch", runner=runner)

                self._assert_clean_original_state(root, original_head)
                self.assertFalse(
                    any(command[:2] == ["git", "push"] for command in runner.calls)
                )
                self.assertFalse(
                    any(command[:2] == ["git", "reset"] for command in runner.calls)
                )

    def test_tag_race_does_not_delete_a_tag_pointing_to_another_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original_head = self._make_repo(root)
            fail_command = ["git", "tag", "v0.5.10"]
            runner = SideEffectFailureRunner(
                fail_command,
                foreign_tag_target=original_head,
            )

            with self.assertRaises(subprocess.CalledProcessError):
                run_release(root, "patch", runner=runner)

            self._assert_clean_original_state(
                root,
                original_head,
                tag_target=original_head,
            )
            self.assertFalse(
                any(command[:2] == ["git", "push"] for command in runner.calls)
            )


if __name__ == "__main__":
    unittest.main()
