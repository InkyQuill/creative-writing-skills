"""Read-only validation of the canonical story-project structure."""

from __future__ import annotations

import stat
import unicodedata
from pathlib import Path
from typing import Iterator

from ..documents import DocumentError, parse_document
from ..findings import Finding
from ..project import MANAGED_ROOTS, Project
from ..schema import (
    SCHEMA_VERSION,
    SCAFFOLD_DIRECTORIES,
    SCAFFOLD_FILES,
    allowed_document_kind,
    validate_metadata,
)

NEWER_SCHEMA = "CW-STRUCT-001"
MISSING_PATH = "CW-STRUCT-010"
WRONG_PATH_KIND = "CW-STRUCT-011"
INVALID_FRONTMATTER = "CW-STRUCT-020"
MISSING_FRONTMATTER = "CW-STRUCT-021"
DUPLICATE_CHAPTER = "CW-STRUCT-030"
MIXED_NEWLINES = "CW-STRUCT-040"
CASE_COLLISION = "CW-STRUCT-050"
ILLEGAL_LOCATION = "CW-STRUCT-060"
UNMANAGED_MARKDOWN = "CW-STRUCT-090"


def check_structure(project: Project) -> list[Finding]:
    """Return deterministic findings without mutating or halting on bad files."""

    schema_version = project.manifest.metadata.get("schema-version")
    if isinstance(schema_version, int) and not isinstance(schema_version, bool) and schema_version > SCHEMA_VERSION:
        return [
            Finding(
                code=NEWER_SCHEMA,
                severity="error",
                message=(
                    f"schema-version {schema_version} is newer than this CLI supports; "
                    "update the bundled tool before interpreting this project"
                ),
                path="project.md",
                next_action="Update the bundled cw CLI before making project changes.",
            )
        ]

    findings: list[Finding] = []
    for relative_id in SCAFFOLD_DIRECTORIES:
        finding = _expected_path_finding(project, relative_id, expected_kind="directory")
        if finding is not None:
            findings.append(finding)
    for relative_id in SCAFFOLD_FILES:
        finding = _expected_path_finding(project, relative_id, expected_kind="regular file")
        if finding is not None:
            findings.append(finding)

    manifest_path = project.root / "project.md"
    manifest_data = manifest_path.read_bytes()
    findings.extend(_newline_findings(manifest_path, "project.md", data=manifest_data))
    if _has_frontmatter(manifest_data):
        findings.extend(validate_metadata("project.md", project.manifest))
    else:
        findings.append(_missing_frontmatter_finding("project.md"))

    chapters: dict[int, list[str]] = {}
    for path in project.iter_managed_markdown():
        relative_id = project.relative_id(path)
        if allowed_document_kind(relative_id) is None:
            findings.append(
                Finding(
                    code=ILLEGAL_LOCATION,
                    severity="warning",
                    message="Markdown is not in a schema-v1 allowed managed location",
                    path=relative_id,
                    next_action=(
                        "Identify this artifact's role, then move it to an allowed managed directory "
                        "without overwriting existing content."
                    ),
                )
            )
        try:
            data = path.read_bytes()
            document = parse_document(data)
        except DocumentError as error:
            findings.append(
                Finding(
                    code=INVALID_FRONTMATTER,
                    severity="error",
                    message=f"frontmatter could not be interpreted safely: {error}",
                    path=relative_id,
                    next_action="Preserve the body and repair the document to use only supported flat frontmatter.",
                )
            )
            continue

        findings.extend(_newline_findings(path, relative_id, data=data))
        if not _has_frontmatter(data):
            findings.append(_missing_frontmatter_finding(relative_id))
            continue
        findings.extend(validate_metadata(relative_id, document))
        number = document.metadata.get("number")
        if (
            allowed_document_kind(relative_id) == "chapter"
            and isinstance(number, int)
            and not isinstance(number, bool)
            and number >= 1
        ):
            chapters.setdefault(number, []).append(relative_id)

    for number, paths in sorted(chapters.items()):
        if len(paths) < 2:
            continue
        ordered_paths = sorted(paths)
        for relative_id in ordered_paths:
            others = ", ".join(path for path in ordered_paths if path != relative_id)
            findings.append(
                Finding(
                    code=DUPLICATE_CHAPTER,
                    severity="error",
                    message=f"chapter number {number} is also used by: {others}",
                    path=relative_id,
                    next_action="After confirming the intended order, assign each manuscript chapter a unique number.",
                )
            )

    for path in _iter_unmanaged_markdown(project):
        findings.append(
            Finding(
                code=UNMANAGED_MARKDOWN,
                severity="info",
                message="Markdown outside managed roots is not validated or selected as story context",
                path=project.relative_id(path),
                next_action="Leave it unmanaged, or move it only after confirming it belongs to the story contract.",
            )
        )
    findings.extend(_case_collision_findings(project))
    return sorted(findings, key=_finding_key)


def _newline_findings(path: Path, relative_id: str, *, data: bytes | None = None) -> list[Finding]:
    if data is None:
        data = path.read_bytes()
    if len(_newline_styles(data)) < 2:
        return []
    return [
        Finding(
            code=MIXED_NEWLINES,
            severity="warning",
            message="document uses mixed newline styles",
            path=relative_id,
            next_action="Normalize the document to one newline style when convenient.",
        )
    ]


def _newline_styles(data: bytes) -> set[bytes]:
    styles: set[bytes] = set()
    index = 0
    while index < len(data):
        if data[index : index + 2] == b"\r\n":
            styles.add(b"\r\n")
            index += 2
        elif data[index : index + 1] == b"\n":
            styles.add(b"\n")
            index += 1
        elif data[index : index + 1] == b"\r":
            styles.add(b"\r")
            index += 1
        else:
            index += 1
    return styles


def _expected_path_finding(project: Project, relative_id: str, *, expected_kind: str) -> Finding | None:
    actual_kind = _path_kind_without_following(project.root, relative_id)
    if actual_kind == "blocked":
        return None
    if actual_kind == "missing":
        return Finding(
            code=MISSING_PATH,
            severity="warning",
            message=f"canonical scaffold {expected_kind} is missing",
            path=relative_id,
            next_action="Preview cw init or restore the missing scaffold path without overwriting content.",
        )
    if actual_kind == expected_kind:
        return None
    return Finding(
        code=WRONG_PATH_KIND,
        severity="error",
        message=f"canonical scaffold path must be a {expected_kind}, not a {actual_kind}",
        path=relative_id,
        next_action=(
            "Move the conflicting entry aside without following it, then restore the expected scaffold path kind."
        ),
    )


def _path_kind_without_following(root: Path, relative_id: str) -> str:
    current = root
    parts = Path(relative_id).parts
    for index, part in enumerate(parts):
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            return "missing"
        except NotADirectoryError:
            return "blocked"

        is_last = index == len(parts) - 1
        if not is_last:
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                return "blocked"
            continue
        if stat.S_ISLNK(mode):
            return "symlink"
        if stat.S_ISREG(mode):
            return "regular file"
        if stat.S_ISDIR(mode):
            return "directory"
        return "other filesystem entry"
    return "directory"


def _has_frontmatter(data: bytes) -> bool:
    text = data.decode("utf-8-sig")
    lines = text.splitlines()
    return bool(lines and lines[0] == "---")


def _missing_frontmatter_finding(relative_id: str) -> Finding:
    return Finding(
        code=MISSING_FRONTMATTER,
        severity="warning",
        message="managed Markdown is missing frontmatter",
        path=relative_id,
        next_action="Preserve the body and add supported flat frontmatter appropriate to this path.",
    )


def _iter_unmanaged_markdown(project: Project) -> Iterator[Path]:
    yield from _iter_unmanaged_markdown_in(project.root, project.root)


def _iter_unmanaged_markdown_in(root: Path, directory: Path) -> Iterator[Path]:
    for path in _sorted_children(directory):
        if path.is_symlink():
            continue
        relative = path.relative_to(root)
        if path.is_dir():
            if relative.parts[0] in (*MANAGED_ROOTS, ".creative-writing"):
                continue
            manifest = path / "project.md"
            if path != root and not manifest.is_symlink() and manifest.is_file():
                continue
            yield from _iter_unmanaged_markdown_in(root, path)
        elif path.is_file() and path.suffix.casefold() == ".md" and relative.as_posix() != "project.md":
            yield path


def _case_collision_findings(project: Project) -> list[Finding]:
    findings: list[Finding] = []
    for directory in _iter_directories(project.root, project.root):
        by_identity: dict[str, list[Path]] = {}
        for path in _sorted_children(directory):
            if path.is_symlink():
                continue
            by_identity.setdefault(_portable_identity(path.name), []).append(path)
        for paths in by_identity.values():
            if len(paths) < 2:
                continue
            ordered_paths = sorted(paths, key=lambda path: path.name)
            names = ", ".join(path.name for path in ordered_paths)
            for path in ordered_paths:
                findings.append(
                    Finding(
                        code=CASE_COLLISION,
                        severity="warning",
                        message=f"path name collides on case-insensitive filesystems: {names}",
                        path=project.relative_id(path),
                        next_action="Rename colliding paths to distinct portable names.",
                    )
                )
    return findings


def _iter_directories(root: Path, directory: Path) -> Iterator[Path]:
    yield directory
    for path in _sorted_children(directory):
        if path.is_symlink() or not path.is_dir():
            continue
        manifest = path / "project.md"
        if path != root and not manifest.is_symlink() and manifest.is_file():
            continue
        yield from _iter_directories(root, path)


def _sorted_children(directory: Path) -> list[Path]:
    return sorted(directory.iterdir(), key=lambda path: (_portable_identity(path.name), path.name))


def _portable_identity(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def _finding_key(finding: Finding) -> tuple[str, str, str, int]:
    return (finding.path or "", finding.code, finding.message, finding.line or 0)


__all__ = [
    "CASE_COLLISION",
    "DUPLICATE_CHAPTER",
    "INVALID_FRONTMATTER",
    "ILLEGAL_LOCATION",
    "MISSING_FRONTMATTER",
    "MISSING_PATH",
    "MIXED_NEWLINES",
    "NEWER_SCHEMA",
    "UNMANAGED_MARKDOWN",
    "WRONG_PATH_KIND",
    "check_structure",
]
