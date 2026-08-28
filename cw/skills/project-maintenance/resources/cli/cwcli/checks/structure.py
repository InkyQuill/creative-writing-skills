"""Read-only validation of the canonical story-project structure."""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Iterator

from ..documents import DocumentError, parse_document
from ..findings import Finding
from ..project import MANAGED_ROOTS, Project
from ..schema import SCHEMA_VERSION, SCAFFOLD_FILES, validate_metadata

NEWER_SCHEMA = "CW-STRUCT-001"
MISSING_PATH = "CW-STRUCT-010"
INVALID_FRONTMATTER = "CW-STRUCT-020"
DUPLICATE_CHAPTER = "CW-STRUCT-030"
MIXED_NEWLINES = "CW-STRUCT-040"
CASE_COLLISION = "CW-STRUCT-050"
UNMANAGED_MARKDOWN = "CW-STRUCT-090"

_PROTECTED_DIRECTORIES = (".creative-writing/context", ".creative-writing/transactions")


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
    for relative_id in (*SCAFFOLD_FILES, *_PROTECTED_DIRECTORIES):
        if not project.resolve(relative_id).exists():
            findings.append(
                Finding(
                    code=MISSING_PATH,
                    severity="warning",
                    message="canonical scaffold path is missing",
                    path=relative_id,
                    next_action="Preview cw init or restore the missing scaffold path.",
                )
            )

    manifest_path = project.root / "project.md"
    findings.extend(validate_metadata("project.md", project.manifest))
    findings.extend(_newline_findings(manifest_path, "project.md"))

    chapters: dict[int, list[str]] = {}
    for path in project.iter_managed_markdown():
        relative_id = project.relative_id(path)
        try:
            data = path.read_bytes()
            document = parse_document(data)
        except (DocumentError, OSError) as error:
            findings.append(
                Finding(
                    code=INVALID_FRONTMATTER,
                    severity="error",
                    message=f"frontmatter could not be interpreted safely: {error}",
                    path=relative_id,
                    next_action="Repair the document's supported frontmatter.",
                )
            )
            continue

        findings.extend(_newline_findings(path, relative_id, data=data))
        findings.extend(validate_metadata(relative_id, document))
        number = document.metadata.get("number")
        if relative_id.startswith("story/chapters/") and isinstance(number, int) and not isinstance(number, bool):
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
                    next_action="Assign each manuscript chapter a unique number.",
                )
            )

    for path in _iter_unmanaged_markdown(project):
        findings.append(
            Finding(
                code=UNMANAGED_MARKDOWN,
                severity="info",
                message="Markdown outside managed roots is not validated or selected as story context",
                path=project.relative_id(path),
            )
        )
    findings.extend(_case_collision_findings(project))
    return sorted(findings, key=_finding_key)


def _newline_findings(path: Path, relative_id: str, *, data: bytes | None = None) -> list[Finding]:
    if data is None:
        try:
            data = path.read_bytes()
        except OSError:
            return []
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
            if path != root and (path / "project.md").is_file() and not (path / "project.md").is_symlink():
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
        if not path.is_dir() or path.is_symlink():
            continue
        if path != root and (path / "project.md").is_file() and not (path / "project.md").is_symlink():
            continue
        yield from _iter_directories(root, path)


def _sorted_children(directory: Path) -> list[Path]:
    try:
        return sorted(directory.iterdir(), key=lambda path: (_portable_identity(path.name), path.name))
    except OSError:
        return []


def _portable_identity(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def _finding_key(finding: Finding) -> tuple[str, str, str, int]:
    return (finding.path or "", finding.code, finding.message, finding.line or 0)


__all__ = [
    "CASE_COLLISION",
    "DUPLICATE_CHAPTER",
    "INVALID_FRONTMATTER",
    "MISSING_PATH",
    "MIXED_NEWLINES",
    "NEWER_SCHEMA",
    "UNMANAGED_MARKDOWN",
    "check_structure",
]
