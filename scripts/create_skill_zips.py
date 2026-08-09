#!/usr/bin/env python3
"""
Create `.skill` ZIP files for Claude.ai uploads.

Sources:
- `cw/skills/*`

Each archive is rooted at the skill directory name and contains its complete
generated runtime tree, except harness UI metadata.
"""

import json
import os
import stat
import tempfile
import zipfile
from pathlib import Path


EXCLUDED_PARTS = {".DS_Store", "__pycache__", ".git"}
EXCLUDED_SUFFIXES = {".pyc"}
EXCLUDED_RUNTIME_PATHS = {Path("agents/openai.yaml")}
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def should_exclude(path: Path) -> bool:
    """Check if a path should be excluded from an archive."""
    if any(part in EXCLUDED_PARTS for part in path.parts):
        return True
    if path.name in EXCLUDED_PARTS:
        return True
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    return False


def find_skill_dirs(repo_root: Path) -> list[Path]:
    """Find skills under `cw/skills/*`."""
    skills_root = repo_root / "cw" / "skills"

    skill_dirs = []
    if skills_root.exists():
        skill_dirs.extend(sorted(d for d in skills_root.iterdir() if d.is_dir()))

    return skill_dirs


def validate_skill_set(skill_dirs: list[Path], expected_names: set[str]) -> None:
    """Require the archive source inventory to match the configured skills."""
    actual_names = {skill_dir.name for skill_dir in skill_dirs}
    missing = sorted(expected_names - actual_names)
    extra = sorted(actual_names - expected_names)
    details = []
    if missing:
        details.append(f"missing: {', '.join(missing)}")
    if extra:
        details.append(f"extra: {', '.join(extra)}")
    if details:
        raise ValueError(f"skill archive inventory mismatch ({'; '.join(details)})")


def load_expected_skill_names(repo_root: Path) -> set[str]:
    config_path = repo_root / "config" / "distribution.json"
    if config_path.is_symlink() or not config_path.is_file():
        raise ValueError(f"distribution config must be a regular file: {config_path}")
    config = json.loads(config_path.read_text())
    names = config.get("canonical_skills")
    if (
        not isinstance(names, list)
        or any(not isinstance(name, str) or not name for name in names)
        or len(names) != len(set(names))
    ):
        raise ValueError("distribution canonical_skills must be unique skill names")
    return set(names)


def iter_skill_files(skill_dir: Path) -> list[Path]:
    """Return a safe, deterministic inventory for one generated skill."""
    if skill_dir.is_symlink() or not skill_dir.is_dir():
        raise ValueError(f"skill directory must be a non-symlink directory: {skill_dir}")
    skill_md = skill_dir / "SKILL.md"
    if skill_md.is_symlink() or not skill_md.is_file():
        raise FileNotFoundError(f"Missing SKILL.md in {skill_dir}")

    files = [skill_md]
    for path in sorted(skill_dir.rglob("*")):
        relative = path.relative_to(skill_dir)
        if relative == Path("SKILL.md") or should_exclude(relative):
            continue
        if relative in EXCLUDED_RUNTIME_PATHS:
            continue
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"archive source is a symlink: {skill_dir.name}/{relative}")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError(
                f"archive source is not a regular file: {skill_dir.name}/{relative}"
            )
        files.append(path)
    return files


def _write_skill_zip(skill_dir: Path, files: list[Path], zip_path: Path) -> None:
    temporary = zip_path.with_name(f".{zip_path.name}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for file_path in files:
                arcname = (
                    Path(skill_dir.name) / file_path.relative_to(skill_dir)
                ).as_posix()
                info = zipfile.ZipInfo(arcname, date_time=ZIP_TIMESTAMP)
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(
                    info,
                    file_path.read_bytes(),
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )
        os.replace(temporary, zip_path)
    finally:
        if temporary.exists():
            temporary.unlink()


def create_skill_zip(
    skill_dir: Path,
    output_dir: Path,
    *,
    files: list[Path] | None = None,
) -> None:
    """Create a .skill file (ZIP format) for a single skill directory."""
    skill_name = skill_dir.name
    zip_path = output_dir / f"{skill_name}.skill"

    print(f"Creating {skill_name}.skill...")

    files = iter_skill_files(skill_dir) if files is None else files
    _write_skill_zip(skill_dir, files, zip_path)

    print(f"  ✓ Created {zip_path.name} ({zip_path.stat().st_size // 1024} KB)")


def build_archives(repo_root: Path) -> list[Path]:
    """Validate all inputs, then atomically replace the archive directory."""
    repo_root = Path(repo_root).resolve()
    output_dir = repo_root / "zips"
    expected_names = load_expected_skill_names(repo_root)
    skill_dirs = find_skill_dirs(repo_root)
    if not skill_dirs:
        raise ValueError("no skill directories found under cw/skills")
    validate_skill_set(skill_dirs, expected_names)
    inventories = [
        (skill_dir, iter_skill_files(skill_dir)) for skill_dir in skill_dirs
    ]

    print(f"\nCreating skill ZIPs in {output_dir}\n")
    with tempfile.TemporaryDirectory(prefix=".skill-zips-", dir=repo_root) as temporary:
        transaction_root = Path(temporary)
        candidate = transaction_root / "candidate"
        candidate.mkdir()
        for skill_dir, files in inventories:
            create_skill_zip(skill_dir, candidate, files=files)

        previous = transaction_root / "previous"
        backed_up = False
        try:
            if output_dir.exists():
                if output_dir.is_symlink() or not output_dir.is_dir():
                    raise ValueError(
                        f"archive output must be a non-symlink directory: {output_dir}"
                    )
                os.replace(output_dir, previous)
                backed_up = True
            os.replace(candidate, output_dir)
        except BaseException:
            if backed_up and not output_dir.exists():
                os.replace(previous, output_dir)
            raise

    return sorted(output_dir.glob("*.skill"))


def main(repo_root: Path | None = None) -> int:
    """Create all configured Claude.ai skill archives."""
    repo_root = repo_root or Path(__file__).resolve().parent.parent
    try:
        skill_files = build_archives(repo_root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}")
        return 1

    print(f"\n✓ Successfully created {len(skill_files)} .skill files in {Path(repo_root) / 'zips'}")
    print(f"\nSkill files:")
    for skill_file in skill_files:
        print(f"  - {skill_file.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
