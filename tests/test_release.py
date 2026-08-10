import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.release import ReleaseError, bump_semver, main, run_command, run_release


EXPECTED_RELEASE_STATUS = (
    " M .claude-plugin/marketplace.json\n"
    " M cw/.claude-plugin/plugin.json\n"
    " M plugins/creative-writing-skills/.codex-plugin/plugin.json\n"
)


class FakeRunner:
    def __init__(
        self,
        *,
        status=None,
        branch="main",
        tags="",
        head="1111111111111111111111111111111111111111",
        fail_on=None,
    ):
        self.status = status
        self.status_calls = 0
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
            if self.status is not None:
                stdout = self.status
            else:
                stdout = ("", EXPECTED_RELEASE_STATUS, EXPECTED_RELEASE_STATUS, "")[
                    min(self.status_calls, 3)
                ]
            self.status_calls += 1
        elif command == ["git", "branch", "--show-current"]:
            stdout = self.branch
        elif command[:3] == ["git", "tag", "--list"]:
            stdout = self.tags
        elif command == ["git", "rev-parse", "--verify", "HEAD"]:
            stdout = f"{self.head}\n"
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")


class SideEffectFailureRunner:
    def __init__(
        self,
        fail_command,
        *,
        foreign_tag_target=None,
        move_tag_before_delete_to=None,
        replace_tag_with_annotated=False,
        residue=None,
        residue_stage="apply",
    ):
        self.fail_command = fail_command
        self.foreign_tag_target = foreign_tag_target
        self.move_tag_before_delete_to = move_tag_before_delete_to
        self.replace_tag_with_annotated = replace_tag_with_annotated
        self.residue = residue
        self.residue_stage = residue_stage
        self.release_commit = None
        self.replacement_raw_oid = None
        self.calls = []

    def __call__(self, command, *, cwd, capture_output=False):
        command = list(command)
        cwd = Path(cwd)
        self.calls.append(command)
        if command[:2] == [sys.executable, "-B"]:
            if command[2:] == ["scripts/sync_claude_distribution.py", "--apply"]:
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
                if self.residue_stage == "apply":
                    self._write_residue(cwd)
            elif command[2:] == ["scripts/create_skill_zips.py"]:
                if self.residue_stage == "verification":
                    self._write_residue(cwd)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        if command == self.fail_command and self.foreign_tag_target is not None:
            run_command(
                ["git", "tag", command[-1], self.foreign_tag_target],
                cwd=cwd,
            )
            raise subprocess.CalledProcessError(97, command)

        tag_ref = "refs/tags/v0.5.10"
        if (
            command[:4] == ["git", "update-ref", "-d", tag_ref]
            and self.move_tag_before_delete_to is not None
        ):
            run_command(
                ["git", "update-ref", tag_ref, self.move_tag_before_delete_to],
                cwd=cwd,
            )
        if (
            command == ["git", "rev-parse", "--verify", tag_ref]
            and self.replace_tag_with_annotated
        ):
            self.release_commit = run_command(
                ["git", "rev-parse", "--verify", "HEAD"],
                cwd=cwd,
                capture_output=True,
            ).stdout.strip()
            run_command(["git", "tag", "--delete", "v0.5.10"], cwd=cwd)
            run_command(
                [
                    "git",
                    "tag",
                    "-a",
                    "-m",
                    "Replacement tag",
                    "v0.5.10",
                    self.release_commit,
                ],
                cwd=cwd,
            )
            self.replacement_raw_oid = run_command(
                ["git", "rev-parse", "--verify", tag_ref],
                cwd=cwd,
                capture_output=True,
            ).stdout.strip()
            self.replace_tag_with_annotated = False

        result = run_command(command, cwd=cwd, capture_output=True)
        if command == self.fail_command:
            raise subprocess.CalledProcessError(97, command)
        return result

    def _write_residue(self, cwd):
        if self.residue == "untracked":
            (cwd / "release-residue.txt").write_text("unexpected\n")
        elif self.residue == "tracked":
            tracked = cwd / "tests/probe_helper.py"
            tracked.write_text(tracked.read_text() + "# unexpected\n")


class RecordingRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, command, *, cwd, capture_output=False):
        command = list(command)
        self.calls.append(command)
        environment = os.environ.copy()
        environment.pop("PYTHONDONTWRITEBYTECODE", None)
        return subprocess.run(
            command,
            cwd=Path(cwd),
            check=True,
            text=True,
            capture_output=capture_output,
            env=environment,
        )


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
                "-B",
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
                [
                    sys.executable,
                    "-B",
                    "scripts/sync_claude_distribution.py",
                    "--check",
                ],
                [
                    sys.executable,
                    "-B",
                    "scripts/sync_claude_distribution.py",
                    "--apply",
                ],
                ["git", "status", "--porcelain", "--untracked-files=normal"],
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-v",
                ],
                [sys.executable, "-B", "scripts/validate_distribution.py"],
                [
                    sys.executable,
                    "-B",
                    "scripts/sync_claude_distribution.py",
                    "--check",
                ],
                [sys.executable, "-B", "scripts/create_skill_zips.py"],
                ["git", "status", "--porcelain", "--untracked-files=normal"],
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
                ["git", "status", "--porcelain", "--untracked-files=normal"],
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
        validation = [sys.executable, "-B", "scripts/validate_distribution.py"]
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
        canonical_skill = (
            root / "plugins/creative-writing-skills/skills/demo/SKILL.md"
        )
        canonical_skill.parent.mkdir(parents=True)
        canonical_skill.write_text("generated skill\n")
        claude_skill = root / "cw/skills/demo/SKILL.md"
        claude_skill.parent.mkdir(parents=True)
        claude_skill.write_text("generated skill\n")
        scripts = root / "scripts"
        scripts.mkdir()
        (scripts / "sync_claude_distribution.py").write_text(
            textwrap.dedent(
                """\
                import json
                import sys
                from pathlib import Path

                root = Path.cwd()
                manifest_path = root / "plugins/creative-writing-skills/.codex-plugin/plugin.json"
                claude_manifest_path = root / "cw/.claude-plugin/plugin.json"
                marketplace_path = root / ".claude-plugin/marketplace.json"
                source_skill = root / "plugins/creative-writing-skills/skills/demo/SKILL.md"
                claude_skill = root / "cw/skills/demo/SKILL.md"
                version = json.loads(manifest_path.read_text())["version"]
                if sys.argv[1] == "--apply":
                    claude_manifest_path.write_text(json.dumps({"version": version}) + "\\n")
                    marketplace_path.write_text(json.dumps({"metadata": {"version": version}}) + "\\n")
                    claude_skill.write_bytes(source_skill.read_bytes())
                elif sys.argv[1] == "--check":
                    matches = (
                        json.loads(claude_manifest_path.read_text())["version"] == version
                        and json.loads(marketplace_path.read_text())["metadata"]["version"] == version
                        and claude_skill.read_bytes() == source_skill.read_bytes()
                    )
                    if not matches:
                        raise SystemExit("generated distribution drift")
                else:
                    raise SystemExit("unknown mode")
                """
            )
        )
        (scripts / "validate_distribution.py").write_text("raise SystemExit(0)\n")
        (scripts / "create_skill_zips.py").write_text("raise SystemExit(0)\n")
        tests = root / "tests"
        tests.mkdir()
        (tests / "probe_helper.py").write_text("VALUE = 1\n")
        (tests / "test_probe.py").write_text(
            textwrap.dedent(
                """\
                import unittest
                import probe_helper

                class ProbeTests(unittest.TestCase):
                    def test_probe(self):
                        self.assertEqual(1, probe_helper.VALUE)
                """
            )
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

    def test_compare_and_delete_preserves_tag_moved_after_raw_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original_head = self._make_repo(root)
            runner = SideEffectFailureRunner(
                ["git", "tag", "v0.5.10"],
                move_tag_before_delete_to=original_head,
            )

            with self.assertRaises(subprocess.CalledProcessError):
                run_release(root, "patch", runner=runner)

            self._assert_clean_original_state(
                root,
                original_head,
                tag_target=original_head,
            )

    def test_annotated_replacement_tag_with_same_peeled_commit_survives(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original_head = self._make_repo(root)
            runner = SideEffectFailureRunner(
                ["git", "tag", "v0.5.10"],
                replace_tag_with_annotated=True,
            )

            with self.assertRaises(subprocess.CalledProcessError):
                run_release(root, "patch", runner=runner)

            self._assert_clean_original_state(
                root,
                original_head,
                tag_target=runner.release_commit,
            )
            raw_oid = self._git(
                root,
                "rev-parse",
                "--verify",
                "refs/tags/v0.5.10",
            ).stdout.strip()
            self.assertEqual(runner.replacement_raw_oid, raw_oid)
            self.assertEqual(
                "tag",
                self._git(root, "cat-file", "-t", raw_oid).stdout.strip(),
            )

    def test_stale_committed_distribution_aborts_before_manifest_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._make_repo(root)
            (root / "cw/skills/demo/SKILL.md").write_text("stale generated skill\n")
            self._git(root, "add", "cw/skills/demo/SKILL.md")
            self._git(root, "commit", "-m", "Commit stale generated output")
            original_head = self._git(root, "rev-parse", "HEAD").stdout.strip()
            original_manifest = (
                root
                / "plugins/creative-writing-skills/.codex-plugin/plugin.json"
            ).read_bytes()
            runner = RecordingRunner()

            with self.assertRaises(subprocess.CalledProcessError):
                run_release(root, "patch", runner=runner)

            self.assertEqual(
                original_head,
                self._git(root, "rev-parse", "HEAD").stdout.strip(),
            )
            self.assertEqual(
                original_manifest,
                (
                    root
                    / "plugins/creative-writing-skills/.codex-plugin/plugin.json"
                ).read_bytes(),
            )
            self.assertEqual("", self._git(root, "status", "--porcelain").stdout)
            self.assertNotIn(
                [
                    sys.executable,
                    "-B",
                    "scripts/sync_claude_distribution.py",
                    "--apply",
                ],
                runner.calls,
            )
            self.assertEqual("", self._git(root, "tag", "--list", "v0.5.10").stdout)

    def test_successful_real_release_commits_exact_metadata_and_leaves_no_residue(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original_head = self._make_repo(root)
            runner = RecordingRunner()

            version = run_release(root, "patch", runner=runner)

            self.assertEqual("0.5.10", version)
            release_head = self._git(root, "rev-parse", "HEAD").stdout.strip()
            self.assertNotEqual(original_head, release_head)
            self.assertEqual(
                release_head,
                self._git(
                    root,
                    "rev-parse",
                    "--verify",
                    "refs/tags/v0.5.10",
                ).stdout.strip(),
            )
            changed_paths = set(
                self._git(
                    root,
                    "diff-tree",
                    "--no-commit-id",
                    "--name-only",
                    "-r",
                    release_head,
                ).stdout.splitlines()
            )
            self.assertEqual(
                {
                    ".claude-plugin/marketplace.json",
                    "cw/.claude-plugin/plugin.json",
                    "plugins/creative-writing-skills/.codex-plugin/plugin.json",
                },
                changed_paths,
            )
            self.assertEqual("", self._git(root, "status", "--porcelain").stdout)
            self.assertEqual([], list(root.rglob("__pycache__")))
            for path, keys in (
                (
                    "plugins/creative-writing-skills/.codex-plugin/plugin.json",
                    ("version",),
                ),
                ("cw/.claude-plugin/plugin.json", ("version",)),
                (".claude-plugin/marketplace.json", ("metadata", "version")),
            ):
                value = json.loads((root / path).read_text())
                for key in keys:
                    value = value[key]
                self.assertEqual("0.5.10", value)

    def test_unexpected_post_generation_residue_blocks_release_and_is_preserved(self):
        cases = {
            ("apply", "tracked"): " M tests/probe_helper.py\n",
            ("apply", "untracked"): "?? release-residue.txt\n",
            ("verification", "tracked"): " M tests/probe_helper.py\n",
            ("verification", "untracked"): "?? release-residue.txt\n",
        }
        for (stage, residue), expected_status in cases.items():
            with (
                self.subTest(stage=stage, residue=residue),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                original_head = self._make_repo(root)
                runner = SideEffectFailureRunner(
                    ["never"],
                    residue=residue,
                    residue_stage=stage,
                )

                with self.assertRaisesRegex(ReleaseError, "unexpected release changes"):
                    run_release(root, "patch", runner=runner)

                self.assertEqual(
                    original_head,
                    self._git(root, "rev-parse", "HEAD").stdout.strip(),
                )
                self.assertEqual(
                    expected_status,
                    self._git(root, "status", "--porcelain").stdout,
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
                    "",
                    self._git(root, "tag", "--list", "v0.5.10").stdout,
                )
                self.assertFalse(
                    any(command[:2] == ["git", "push"] for command in runner.calls)
                )


if __name__ == "__main__":
    unittest.main()
