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


class ReleaseError(ValueError):
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
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


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

    status = runner(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=repo_root,
        capture_output=True,
    ).stdout
    if status.strip():
        raise ReleaseError(f"worktree must be clean before release:\n{status.rstrip()}")

    branch = runner(
        ["git", "branch", "--show-current"],
        cwd=repo_root,
        capture_output=True,
    ).stdout.strip()
    if branch != "main":
        raise ReleaseError(f"release branch must be main, found {branch or 'detached HEAD'}")

    original_manifest = manifest_path.read_bytes()
    manifest = json.loads(original_manifest)
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

    manifest["version"] = next_version
    staged = False
    committed = False
    try:
        _write_manifest(manifest_path, manifest)
        commands = [
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
        ]
        for command in commands:
            runner(command, cwd=repo_root)

        runner(
            [
                "git",
                "add",
                "--",
                MANIFEST_RELATIVE.as_posix(),
                CLAUDE_MANIFEST_RELATIVE.as_posix(),
                CLAUDE_MARKETPLACE_RELATIVE.as_posix(),
            ],
            cwd=repo_root,
        )
        staged = True
        runner(["git", "commit", "-m", f"Release {tag}"], cwd=repo_root)
        committed = True
    except BaseException:
        if not committed:
            manifest_path.write_bytes(original_manifest)
            if staged:
                runner(
                    [
                        "git",
                        "restore",
                        "--staged",
                        "--worktree",
                        "--",
                        MANIFEST_RELATIVE.as_posix(),
                        "cw",
                        CLAUDE_MARKETPLACE_RELATIVE.as_posix(),
                    ],
                    cwd=repo_root,
                )
            else:
                runner(
                    [
                        "git",
                        "restore",
                        "--worktree",
                        "--",
                        "cw",
                        CLAUDE_MARKETPLACE_RELATIVE.as_posix(),
                    ],
                    cwd=repo_root,
                )
        raise

    runner(["git", "tag", tag], cwd=repo_root)
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
        print("Release commit and tag are local; rerun with --push to publish them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
