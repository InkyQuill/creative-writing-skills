#!/usr/bin/env python3
"""Release identity and packaging checks; never infer a source from a moving tag."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = "plugins/creative-writing-skills/.codex-plugin/plugin.json"
SEMVER = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
SHA = re.compile(r"[a-f0-9]{40}\Z")


def stable_version(value: object) -> str:
    if not isinstance(value, str) or SEMVER.fullmatch(value) is None:
        raise ValueError(f"expected stable semantic version, got {value!r}")
    return value


def canonical_version(root: Path) -> str:
    return stable_version(json.loads((root / MANIFEST).read_text())["version"])


def check_versions(root: Path) -> str:
    version = canonical_version(root)
    mirror = (root / "version.txt").read_text().strip()
    tracking = json.loads((root / ".release-please-manifest.json").read_text())
    if mirror != version or tracking != {".": version}:
        raise ValueError(
            "release-please version tracking differs from the canonical plugin manifest"
        )
    return version


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=True
    ).stdout.strip()


def version_change(root: Path, before: str) -> str | None:
    version = check_versions(root)
    if not before or before == "0" * 40:
        return None
    if SHA.fullmatch(before) is None:
        raise ValueError("previous commit must be a full Git SHA")
    previous = stable_version(
        json.loads(git(root, "show", f"{before}:{MANIFEST}"))["version"]
    )
    if version == previous:
        return None
    if tuple(map(int, version.split("."))) <= tuple(map(int, previous.split("."))):
        raise ValueError("release version must increase")
    return "v" + version


def verify_source(root: Path, tag: str, sha: str) -> None:
    version = check_versions(root)
    if tag != "v" + version or SHA.fullmatch(sha) is None:
        raise ValueError("release tag/SHA does not match the canonical version")
    if git(root, "rev-parse", "HEAD") != sha:
        raise ValueError("checkout is not the requested release commit")
    git(root, "merge-base", "--is-ancestor", sha, "origin/main")
    exists = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", "refs/tags/" + tag],
        cwd=root,
        check=False,
    )
    if exists.returncode not in (0, 1):
        raise ValueError("could not inspect release tag")
    if (
        exists.returncode == 0
        and git(root, "rev-parse", f"refs/tags/{tag}^{{commit}}") != sha
    ):
        raise ValueError("existing release tag points to another commit; never move it")


def release_notes(changelog: str, version: str) -> str:
    stable_version(version)
    # release-please emits both linked and plain version headings.
    pattern = r"^## (?:\[)?v?" + re.escape(version) + r"(?:\]|\s|$)"
    headings = list(re.finditer(r"^## .*$", changelog, re.MULTILINE))
    for index, heading in enumerate(headings):
        if re.match(pattern, heading.group()):
            end = (
                headings[index + 1].start()
                if index + 1 < len(headings)
                else len(changelog)
            )
            return changelog[heading.start() : end].strip() + "\n"
    raise ValueError(f"CHANGELOG.md has no entry for {version}")


def prepare_assets(root: Path, tag: str) -> None:
    version = check_versions(root)
    if tag != "v" + version:
        raise ValueError("asset tag does not match canonical version")
    names = json.loads((root / "config/distribution.json").read_text())[
        "canonical_skills"
    ]
    expected = {name + ".skill" for name in names}
    directory = root / "zips"
    actual = {path.name for path in directory.glob("*.skill")}
    if actual != expected or len(expected) != len(names):
        raise ValueError("release assets do not match the configured skill inventory")
    checksums = []
    for name in sorted(expected):
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"unsafe or empty release asset: {name}")
        checksums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {name}\n")
    notes = release_notes((root / "CHANGELOG.md").read_text(), version)
    (directory / "SHA256SUMS").write_text("".join(checksums))
    (directory / "RELEASE_NOTES.md").write_text(notes)


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    commands.add_parser("sync")
    change = commands.add_parser("version-change")
    change.add_argument("--before", default="")
    verify = commands.add_parser("verify")
    verify.add_argument("--tag", required=True)
    verify.add_argument("--sha", required=True)
    assets = commands.add_parser("prepare-assets")
    assets.add_argument("--tag", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "version-change":
            tag = version_change(root, args.before)
            print("changed=" + ("true" if tag else "false"))
            print("tag=" + (tag or ""))
        elif args.command == "verify":
            verify_source(root, args.tag, args.sha)
        elif args.command == "prepare-assets":
            prepare_assets(root, args.tag)
        else:
            check_versions(root)
            if args.command == "sync":
                for mode in ("--apply", "--check"):
                    subprocess.run(
                        [
                            sys.executable,
                            "-B",
                            "scripts/sync_claude_distribution.py",
                            mode,
                        ],
                        cwd=root,
                        check=True,
                    )
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Release check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
