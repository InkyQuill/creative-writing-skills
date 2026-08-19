#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence


SEMVER_RE = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z"
)
MANIFEST_RELATIVE = Path(
    "plugins/creative-writing-skills/.codex-plugin/plugin.json"
)
CLAUDE_MANIFEST_RELATIVE = Path("cw/.claude-plugin/plugin.json")
CLAUDE_MARKETPLACE_RELATIVE = Path(".claude-plugin/marketplace.json")
ZCODE_MANIFEST_RELATIVE = Path("cw/.zcode-plugin/plugin.json")
ZCODE_MARKETPLACE_RELATIVE = Path("marketplace.json")
STAGED_RELEASE_PATHS = (
    MANIFEST_RELATIVE.as_posix(),
    CLAUDE_MANIFEST_RELATIVE.as_posix(),
    ZCODE_MANIFEST_RELATIVE.as_posix(),
    CLAUDE_MARKETPLACE_RELATIVE.as_posix(),
    ZCODE_MARKETPLACE_RELATIVE.as_posix(),
)
RESTORED_RELEASE_PATHS = (
    MANIFEST_RELATIVE.as_posix(),
    "cw",
    CLAUDE_MARKETPLACE_RELATIVE.as_posix(),
    ZCODE_MARKETPLACE_RELATIVE.as_posix(),
)
STATUS_COMMAND = ("git", "status", "--porcelain", "--untracked-files=normal")
EXPECTED_RELEASE_STATUS = {f" M {path}" for path in STAGED_RELEASE_PATHS}


class ReleaseError(ValueError):
    pass


class ReleaseRecoveryError(ReleaseError):
    pass


Runner = Callable[..., subprocess.CompletedProcess[str]]


def bump_semver(version: str, part: str) -> str:
    match = SEMVER_RE.fullmatch(version)
    if match is None:
        raise ValueError(f"version must be a strict semantic version: {version!r}")
    major, minor, patch = (int(value) for value in match.groups())
    if part == "patch":
        patch += 1
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise ValueError(f"unknown version part: {part!r}")
    return f"{major}.{minor}.{patch}"


def run_command(
    command: Sequence[str],
    *,
    cwd: Path,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _status(runner: Runner, repo_root: Path) -> set[str]:
    output = runner(
        list(STATUS_COMMAND),
        cwd=repo_root,
        capture_output=True,
    ).stdout
    return set(output.splitlines())


def _assert_expected_release_status(
    runner: Runner,
    repo_root: Path,
    stage: str,
) -> None:
    actual = _status(runner, repo_root)
    if actual != EXPECTED_RELEASE_STATUS:
        expected_text = ", ".join(sorted(EXPECTED_RELEASE_STATUS))
        actual_text = ", ".join(sorted(actual)) or "<clean>"
        raise ReleaseError(
            f"unexpected release changes {stage}: expected [{expected_text}], "
            f"found [{actual_text}]"
        )


def _assert_clean_status(runner: Runner, repo_root: Path, stage: str) -> None:
    actual = _status(runner, repo_root)
    if actual:
        raise ReleaseError(
            f"worktree must be clean {stage}:\n" + "\n".join(sorted(actual))
        )


def _stdout(runner: Runner, command: Sequence[str], repo_root: Path) -> str:
    return runner(
        command,
        cwd=repo_root,
        capture_output=True,
    ).stdout.strip()


def _release_commit_at_head(
    runner: Runner,
    repo_root: Path,
    original_head: str,
    tag: str,
) -> str | None:
    current_head = _stdout(
        runner,
        ["git", "rev-parse", "--verify", "HEAD"],
        repo_root,
    )
    if current_head == original_head:
        return None

    parent = _stdout(
        runner,
        ["git", "rev-parse", "--verify", f"{current_head}^"],
        repo_root,
    )
    subject = _stdout(
        runner,
        ["git", "show", "-s", "--format=%s", current_head],
        repo_root,
    )
    changed_paths = set(
        _stdout(
            runner,
            [
                "git",
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                current_head,
            ],
            repo_root,
        ).splitlines()
    )
    if (
        parent != original_head
        or subject != f"Release {tag}"
        or not changed_paths
        or not changed_paths.issubset(set(STAGED_RELEASE_PATHS))
    ):
        raise ReleaseRecoveryError(
            "release failed after HEAD moved, but the new commit could not be "
            "proved to belong to this release; repository left untouched"
        )
    return current_head


def _recover_release(
    runner: Runner,
    repo_root: Path,
    original_head: str,
    tag: str,
) -> None:
    release_commit = _release_commit_at_head(
        runner,
        repo_root,
        original_head,
        tag,
    )
    if release_commit is not None:
        if _stdout(runner, ["git", "tag", "--list", tag], repo_root):
            tag_ref = f"refs/tags/{tag}"
            try:
                raw_tag_oid = _stdout(
                    runner,
                    ["git", "rev-parse", "--verify", tag_ref],
                    repo_root,
                )
            except subprocess.CalledProcessError:
                raw_tag_oid = None
            if raw_tag_oid == release_commit:
                try:
                    runner(
                        [
                            "git",
                            "update-ref",
                            "-d",
                            tag_ref,
                            release_commit,
                        ],
                        cwd=repo_root,
                    )
                except subprocess.CalledProcessError as delete_error:
                    try:
                        current_raw_oid = _stdout(
                            runner,
                            ["git", "rev-parse", "--verify", tag_ref],
                            repo_root,
                        )
                    except subprocess.CalledProcessError:
                        current_raw_oid = None
                    if current_raw_oid == release_commit:
                        raise delete_error
        runner(
            [
                "git",
                "update-ref",
                "refs/heads/main",
                original_head,
                release_commit,
            ],
            cwd=repo_root,
        )

    runner(
        [
            "git",
            "restore",
            f"--source={original_head}",
            "--staged",
            "--worktree",
            "--",
            *RESTORED_RELEASE_PATHS,
        ],
        cwd=repo_root,
    )


def run_release(
    repo_root: Path,
    part: str,
    *,
    push: bool = False,
    runner: Runner = run_command,
) -> str:
    repo_root = Path(repo_root).resolve()
    manifest_path = repo_root / MANIFEST_RELATIVE
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ReleaseError(f"canonical manifest must be a regular file: {manifest_path}")

    initial_status = _status(runner, repo_root)
    if initial_status:
        raise ReleaseError(
            "worktree must be clean before release:\n"
            + "\n".join(sorted(initial_status))
        )

    branch = runner(
        ["git", "branch", "--show-current"],
        cwd=repo_root,
        capture_output=True,
    ).stdout.strip()
    if branch != "main":
        raise ReleaseError(f"release branch must be main, found {branch or 'detached HEAD'}")

    original_head = _stdout(
        runner,
        ["git", "rev-parse", "--verify", "HEAD"],
        repo_root,
    )
    manifest = json.loads(manifest_path.read_bytes())
    if not isinstance(manifest, dict):
        raise ReleaseError("canonical manifest must contain a JSON object")
    current_version = manifest.get("version")
    if not isinstance(current_version, str):
        raise ReleaseError("canonical manifest version must be a string")
    next_version = bump_semver(current_version, part)
    tag = f"v{next_version}"

    existing_tag = runner(
        ["git", "tag", "--list", tag],
        cwd=repo_root,
        capture_output=True,
    ).stdout.strip()
    if existing_tag:
        raise ReleaseError(f"tag {tag} already exists")

    runner(
        [
            sys.executable,
            "-B",
            "scripts/sync_claude_distribution.py",
            "--check",
        ],
        cwd=repo_root,
    )

    manifest["version"] = next_version
    try:
        _write_manifest(manifest_path, manifest)
        runner(
            [
                sys.executable,
                "-B",
                "scripts/sync_claude_distribution.py",
                "--apply",
            ],
            cwd=repo_root,
        )
        _assert_expected_release_status(
            runner,
            repo_root,
            "after Claude generation",
        )
        verification_commands = [
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
        ]
        for command in verification_commands:
            runner(command, cwd=repo_root)

        _assert_expected_release_status(
            runner,
            repo_root,
            "before staging",
        )

        runner(
            [
                "git",
                "add",
                "--",
                *STAGED_RELEASE_PATHS,
            ],
            cwd=repo_root,
        )
        runner(["git", "commit", "-m", f"Release {tag}"], cwd=repo_root)
        runner(["git", "tag", tag], cwd=repo_root)
        _assert_clean_status(runner, repo_root, "after commit and tag")
    except BaseException as release_error:
        try:
            _recover_release(runner, repo_root, original_head, tag)
        except BaseException as recovery_error:
            raise ReleaseRecoveryError(
                f"release failed ({release_error}); recovery also failed: "
                f"{recovery_error}"
            ) from release_error
        raise

    if push:
        runner(
            ["git", "push", "--atomic", "origin", "main", tag],
            cwd=repo_root,
        )
    return next_version


def main(argv: Sequence[str] | None = None, *, repo_root: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a validated plugin release")
    parser.add_argument("part", choices=("patch", "minor", "major"), nargs="?", default="patch")
    parser.add_argument(
        "--push",
        action="store_true",
        help="atomically push the main branch and release tag to origin",
    )
    args = parser.parse_args(argv)
    repo_root = repo_root or Path(__file__).resolve().parent.parent
    try:
        version = run_release(repo_root, args.part, push=args.push)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"Release failed: {error}", file=sys.stderr)
        return 1
    print(f"Created Release v{version}")
    if not args.push:
        print(
            "Publish it with: "
            f"git push --atomic origin main v{version}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
