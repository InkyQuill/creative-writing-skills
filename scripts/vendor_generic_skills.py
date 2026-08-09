#!/usr/bin/env python3
"""Vendor the licensed generic skills used by the Codex plugin."""

import argparse
import filecmp
import json
import os
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "distribution.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "plugins" / "creative-writing-skills" / "skills"
_SKILL_NAME_RE = re.compile(r"[a-z][a-z0-9-]*\Z")
_SLASH_SKILL_RE = re.compile(r"(?<![A-Za-z0-9_.</%-])/([a-z][a-z0-9-]*)(?!(?:[A-Za-z0-9/-]|\.[A-Za-z0-9]))")
_QI_OWNERSHIP = "`/qi-maintenance` owns when colocated knowledge must move with source changes."
_QI_ADAPTATION = (
    "When colocated knowledge changes, keep its AGENTS.md and .context "
    "documentation synchronized with the source in the same change."
)


@dataclass(frozen=True)
class VendorSource:
    url: str
    commit: str
    skills_path: str
    license: str


SOURCE = VendorSource(
    url="https://github.com/haowjy/creative-writing-skills.git",
    commit="fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3",
    skills_path="cw/skills",
    license="Apache-2.0",
)


class VendorDriftError(RuntimeError):
    """Raised when generated vendored skills differ from their source snapshot."""


def distribution() -> dict[str, object]:
    value = json.loads(CONFIG_PATH.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {CONFIG_PATH}")
    return value


def vendored_skills() -> tuple[str, ...]:
    skills = distribution()["vendored_skills"]
    if not isinstance(skills, list) or not all(isinstance(skill, str) for skill in skills):
        raise ValueError("config/distribution.json vendored_skills must be a list of strings")
    return tuple(skills)


def canonical_skills() -> set[str]:
    skills = distribution()["canonical_skills"]
    if not isinstance(skills, list) or not all(isinstance(skill, str) for skill in skills):
        raise ValueError("config/distribution.json canonical_skills must be a list of strings")
    return set(skills)


def validated_vendored_skills() -> tuple[str, ...]:
    skills = vendored_skills()
    canonical = canonical_skills()
    if len(set(skills)) != len(skills):
        raise ValueError("config/distribution.json vendored_skills must not contain duplicates")
    for skill in skills:
        if _SKILL_NAME_RE.fullmatch(skill) is None:
            raise ValueError(f"config/distribution.json has invalid vendored skill name: {skill!r}")
        if skill not in canonical:
            raise ValueError(f"config/distribution.json vendored skill is not canonical: {skill}")
    return skills


def normalize_codex_references(text: str, canonical_skills: set[str], skill_name: str) -> str:
    """Convert Claude slash skill references outside fenced code blocks to Codex syntax."""

    rendered: list[str] = []
    fence: tuple[str, int] | None = None

    def normalize(segment_text: str) -> str:
        def replace(match: re.Match[str]) -> str:
            reference = match.group(1)
            if reference not in canonical_skills:
                raise ValueError(f"{skill_name}: unbundled skill reference /{reference}")
            return f"${reference}"

        return _SLASH_SKILL_RE.sub(replace, segment_text)

    for line in text.splitlines(keepends=True):
        fence_line = line.rstrip("\r\n")
        if fence is not None:
            marker, length = fence
            closing = re.fullmatch(r" {0,3}" + re.escape(marker) + rf"{{{length},}}[ \t]*", fence_line)
            rendered.append(line)
            if closing is not None:
                fence = None
            continue

        opening = re.match(r" {0,3}(([`~])\2{2,})(.*)", fence_line)
        if opening is not None and not (opening.group(2) == "`" and "`" in opening.group(3)):
            rendered.append(line)
            fence = (opening.group(2), len(opening.group(1)))
            continue
        rendered.append(normalize(line))
    return "".join(rendered)


def _adapt_markdown(text: str, skill_name: str, known_skills: set[str], is_skill_document: bool) -> str:
    if skill_name == "qi-layer" and is_skill_document:
        if _QI_OWNERSHIP not in text:
            raise ValueError("qi-layer: expected licensed ownership sentence was not found")
        text = text.replace(_QI_OWNERSHIP, _QI_ADAPTATION, 1)
    return normalize_codex_references(text, known_skills, skill_name)


def _copy_skill(source: Path, destination: Path, skill_name: str, known_skills: set[str]) -> None:
    if not (source / "SKILL.md").is_file():
        raise ValueError(f"{skill_name}: missing SKILL.md in licensed source")
    shutil.copytree(source, destination)
    for markdown in destination.rglob("*.md"):
        markdown.write_text(
            _adapt_markdown(
                markdown.read_text(),
                skill_name,
                known_skills,
                markdown == destination / "SKILL.md",
            )
        )


def _replace_directory(staged: Path, destination: Path) -> None:
    backup_root: Path | None = None
    backup: Path | None = None
    keep_backup = False
    try:
        if destination.exists():
            backup_root = Path(tempfile.mkdtemp(prefix=f".{destination.name}.vendor-backup-", dir=destination.parent))
            backup = backup_root / "previous"
            os.replace(destination, backup)
        os.replace(staged, destination)
    except BaseException:
        if backup is not None and backup.exists():
            try:
                os.replace(backup, destination)
            except BaseException:
                keep_backup = True
                raise
        raise
    finally:
        if backup_root is not None and not keep_backup:
            shutil.rmtree(backup_root)


def render_from_checkout(checkout: Path, output_root: Path) -> None:
    """Render configured skill snapshots from a licensed source checkout."""

    source_root = checkout / SOURCE.skills_path
    configured_skills = validated_vendored_skills()
    known_skills = canonical_skills()
    output_root.mkdir(parents=True, exist_ok=True)
    for skill_name in configured_skills:
        source = source_root / skill_name
        with tempfile.TemporaryDirectory(prefix=f".{skill_name}.vendor-", dir=output_root) as temporary:
            staged = Path(temporary) / skill_name
            _copy_skill(source, staged, skill_name, known_skills)
            _replace_directory(staged, output_root / skill_name)


def _relative_files(root: Path) -> set[Path]:
    if not root.exists():
        return set()
    return {path.relative_to(root) for path in root.rglob("*") if path.is_file()}


def _drifted_files(expected_root: Path, output_root: Path) -> list[str]:
    changed: list[str] = []
    for skill_name in validated_vendored_skills():
        expected = expected_root / skill_name
        actual = output_root / skill_name
        expected_files = _relative_files(expected)
        actual_files = _relative_files(actual)
        for relative in sorted(expected_files | actual_files):
            expected_file = expected / relative
            actual_file = actual / relative
            if not expected_file.is_file() or not actual_file.is_file() or not filecmp.cmp(expected_file, actual_file, shallow=False):
                changed.append((Path(skill_name) / relative).as_posix())
    return changed


def check_checkout(checkout: Path, output_root: Path) -> None:
    """Raise a concise drift error if the output differs from a source render."""

    with tempfile.TemporaryDirectory(prefix="vendor-generic-skills-check-") as temporary:
        expected_root = Path(temporary) / "skills"
        render_from_checkout(checkout, expected_root)
        changed = _drifted_files(expected_root, output_root)
    if changed:
        raise VendorDriftError("vendored skill drift:\n" + "\n".join(changed))


@contextmanager
def source_checkout(source_checkout: Path | None) -> Iterator[Path]:
    if source_checkout is not None:
        yield source_checkout.resolve()
        return

    with tempfile.TemporaryDirectory(prefix="vendor-generic-skills-source-") as temporary:
        checkout = Path(temporary) / "source"
        subprocess.run(
            ["git", "clone", "--filter=blob:none", "--no-checkout", SOURCE.url, str(checkout)],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(checkout), "checkout", SOURCE.commit, "--", SOURCE.skills_path],
            check=True,
        )
        yield checkout


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="refresh the vendored skill snapshots")
    mode.add_argument("--check", action="store_true", help="verify the vendored skill snapshots")
    parser.add_argument("--source-checkout", type=Path, help="use an existing licensed source checkout")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with source_checkout(args.source_checkout) as checkout:
        if args.apply:
            render_from_checkout(checkout, DEFAULT_OUTPUT_ROOT)
            for skill_name in vendored_skills():
                print(f"synced {skill_name}")
            return 0
        try:
            check_checkout(checkout, DEFAULT_OUTPUT_ROOT)
        except VendorDriftError as error:
            print(error)
            return 1
    print(f"{len(vendored_skills())} vendored skills in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
