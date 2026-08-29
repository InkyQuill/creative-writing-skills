"""Deterministic, read-only context planning from explicit project evidence."""

from __future__ import annotations

import os
import re
import stat
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import unquote, urlsplit

from .checks.continuity import check_continuity
from .documents import Document, parse_document
from .project import Project
from .schema import allowed_document_kind


_KINDS = frozenset({"draft", "chapter", "kb"})
_ROLE_ID = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")
_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
_INACTIVE = frozenset({"accepted", "abandoned", "archived", "closed", "complete", "done", "resolved"})
_ACTIVE_PLAN = frozenset({"active", "planned", "ready", "review", "working"})
_ACTIVE_ISSUE = frozenset({"active", "blocked", "open", "review", "working"})
_DIRECT_KEYS = ("related", "context", "links")
_CONTINUITY = (
    "kb/continuity/state.md",
    "kb/continuity/timeline.md",
    "kb/continuity/promises.md",
    "kb/continuity/questions.md",
    "kb/vocab.md",
)
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)
_WINDOWS_FORBIDDEN = frozenset('<>:"\\|?*')


class ContextPlanError(ValueError):
    """Raised when the requested context subject or role is unsafe."""


@dataclass(frozen=True)
class ContextPlan:
    """An immutable ordered set of source paths and nonfatal diagnostics."""

    kind: str
    subject: str
    role: str
    required: tuple[str, ...]
    suggested: tuple[str, ...]
    unresolved: tuple[str, ...]
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Return the stable JSON/text command representation."""

        return asdict(self)


def plan_context(project: Project, kind: str, path: str, role: str) -> ContextPlan:
    """Plan focused sources without creating cache or journal state."""

    if kind not in _KINDS:
        raise ContextPlanError(f"unknown context kind: {kind}")
    character = _validate_role(project, role)
    subject = _validate_subject(project, kind, path)
    subject_path = project.root / subject
    subject_document = _read_document(subject_path)

    required = _OrderedPaths()
    suggested = _OrderedPaths()
    unresolved = _OrderedStrings()
    warnings = _OrderedStrings()
    required.add(subject)
    anchors = {subject}

    target: str | None = None
    if kind == "draft":
        raw_target = subject_document.metadata.get("target")
        if isinstance(raw_target, str) and raw_target.strip():
            target = _add_reference(
                project,
                raw_target.strip(),
                source=subject,
                required=required,
                unresolved=unresolved,
                warnings=warnings,
                project_relative=True,
                expected_kind="chapter",
            )
            if target is not None:
                anchors.add(target)
        else:
            unresolved.add(f"draft-target:{subject}")

    for raw in _metadata_references(subject_document):
        resolved = _add_reference(
            project,
            raw,
            source=subject,
            required=required,
            unresolved=unresolved,
            warnings=warnings,
            project_relative=True,
        )
        if resolved is not None:
            anchors.add(resolved)
    for raw in _markdown_references(subject_document.body):
        resolved = _add_reference(
            project,
            raw,
            source=subject,
            required=required,
            unresolved=unresolved,
            warnings=warnings,
            project_relative=False,
        )
        if resolved is not None:
            anchors.add(resolved)

    for relative in _CONTINUITY:
        if _safe_regular(project, relative):
            required.add(relative)
        elif (project.root / relative).exists() or (project.root / relative).is_symlink():
            warnings.add(f"unsafe structured context source: {relative}")

    chapter = target if kind == "draft" else subject if kind == "chapter" else None
    if chapter is not None:
        for neighbor in _chapter_neighbors(project, chapter, unresolved, warnings):
            suggested.add(neighbor)

    documents = _scan_documents(project, warnings)
    for relative, document in documents:
        if relative.startswith("work/plans/") and _explicitly_active(document, _ACTIVE_PLAN):
            if _document_points_to(project, relative, document, anchors, warnings):
                suggested.add(relative)

    for relative, document in documents:
        if relative in anchors:
            continue
        if relative.startswith("work/plans/") or relative.startswith("kb/issues/"):
            continue
        if _document_points_to(project, relative, document, anchors, warnings):
            suggested.add(relative)

    for relative, document in documents:
        if relative.startswith("kb/issues/") and _explicitly_active(document, _ACTIVE_ISSUE):
            if _document_points_to(project, relative, document, anchors, warnings):
                suggested.add(relative)

    try:
        continuity_findings = check_continuity(project)
    except Exception as error:
        warnings.add(f"continuity context evidence could not be inspected: {error}")
    else:
        for finding in continuity_findings:
            if finding.path and _safe_regular(project, finding.path):
                suggested.add(finding.path)
            if finding.severity in {"warning", "error"}:
                location = finding.path or "project"
                warnings.add(f"{finding.code}: structured continuity issue at {location}")

    if character is not None and not _known_character(project, character):
        unresolved.add(f"character:{character}")
        warnings.add(f"unknown character role: {character}")

    suggested.discard_identities(required.identities)
    return ContextPlan(
        kind=kind,
        subject=subject,
        role=role,
        required=required.values,
        suggested=suggested.values,
        unresolved=unresolved.values,
        warnings=warnings.values,
    )


def _validate_role(project: Project, role: str) -> str | None:
    if role in {"trusted", "reader"}:
        return None
    if not role.startswith("character:"):
        raise ContextPlanError(f"invalid context role: {role}")
    character = role.removeprefix("character:")
    if not _ROLE_ID.fullmatch(character) or not _portable_component(character):
        raise ContextPlanError(f"invalid character role identifier: {character!r}")
    return character


def _validate_subject(project: Project, kind: str, value: str) -> str:
    relative = _normalize_relative(value)
    expected = {"draft": "work/drafts", "chapter": "story/chapters", "kb": "kb"}[kind]
    inferred = allowed_document_kind(relative)
    if kind == "draft" and not (PurePosixPath(relative).parent.as_posix() == expected and inferred == "work-artifact"):
        raise ContextPlanError("draft context subject must be a direct work/drafts Markdown file")
    if kind == "chapter" and inferred != "chapter":
        raise ContextPlanError("chapter context subject must be a direct story/chapters Markdown file")
    if kind == "kb" and inferred not in {"kb-content", "continuity-record", "continuity-scene", "vocabulary"}:
        raise ContextPlanError("kb context subject must be an authored KB Markdown file")
    if not _safe_regular(project, relative):
        raise ContextPlanError(f"context subject is missing, linked, nested, or not a regular file: {relative}")
    return relative


def _metadata_references(document: Document) -> tuple[str, ...]:
    references: list[str] = []
    for key in _DIRECT_KEYS:
        value = document.metadata.get(key)
        if isinstance(value, str) and value.strip():
            references.append(value.strip())
        elif isinstance(value, list):
            references.extend(item.strip() for item in value if isinstance(item, str) and item.strip())
    return tuple(references)


def _markdown_references(text: str) -> tuple[str, ...]:
    return tuple(match.group(1).strip() for match in _LINK.finditer(text))


def _add_reference(
    project: Project,
    raw: str,
    *,
    source: str,
    required: "_OrderedPaths",
    unresolved: "_OrderedStrings",
    warnings: "_OrderedStrings",
    project_relative: bool,
    expected_kind: str | None = None,
) -> str | None:
    try:
        relative = _resolve_reference(raw, source, project_relative=project_relative)
    except (UnicodeError, ValueError) as error:
        unresolved.add(raw)
        warnings.add(f"invalid explicit reference {raw!r} in {source}: {error}")
        return None
    if relative is None:
        return None
    if expected_kind is not None and allowed_document_kind(relative) != expected_kind:
        unresolved.add(relative)
        warnings.add(f"explicit reference has the wrong document kind: {relative}")
        return None
    if not _safe_regular(project, relative):
        unresolved.add(relative)
        warnings.add(f"explicit reference is missing or unsafe: {relative}")
        return None
    required.add(relative)
    return relative


def _resolve_reference(raw: str, source: str, *, project_relative: bool) -> str | None:
    destination = raw.strip()
    if destination.startswith("<") and destination.endswith(">"):
        destination = destination[1:-1]
    destination = destination.split(maxsplit=1)[0]
    parsed = urlsplit(destination)
    if parsed.scheme.casefold() in {"http", "https", "mailto"} or destination.startswith("//"):
        return None
    if parsed.scheme or parsed.netloc or not parsed.path:
        raise ValueError("unsupported or empty reference")
    if re.search(r"%(?![0-9A-Fa-f]{2})", parsed.path):
        raise ValueError("invalid percent escape")
    decoded = unquote(parsed.path, errors="strict")
    if "\x00" in decoded or "\\" in decoded:
        raise ValueError("unsafe path characters")
    base = PurePosixPath() if project_relative else PurePosixPath(source).parent
    parts: list[str] = []
    for part in (base / decoded).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise ValueError("reference escapes project")
            parts.pop()
        else:
            parts.append(part)
    return _normalize_relative(PurePosixPath(*parts).as_posix())


def _chapter_neighbors(
    project: Project,
    chapter: str,
    unresolved: "_OrderedStrings",
    warnings: "_OrderedStrings",
) -> tuple[str, ...]:
    numbered: dict[int, list[str]] = {}
    directory = project.root / "story/chapters"
    if not directory.is_dir() or directory.is_symlink():
        return ()
    for path in sorted(directory.iterdir(), key=lambda item: _identity(item.name)):
        relative = f"story/chapters/{path.name}"
        if path.name == "_index.md" or path.suffix.casefold() != ".md" or not _safe_regular(project, relative):
            continue
        try:
            number = _read_document(path).metadata.get("number")
        except (OSError, UnicodeError, ValueError) as error:
            warnings.add(f"cannot inspect chapter order for {relative}: {error}")
            continue
        if isinstance(number, int) and not isinstance(number, bool) and number > 0:
            numbered.setdefault(number, []).append(relative)

    duplicates = {number: paths for number, paths in numbered.items() if len(paths) > 1}
    for number, paths in sorted(duplicates.items()):
        unresolved.add(f"chapter-number:{number} ({', '.join(sorted(paths, key=_identity))})")

    subject_number = next((number for number, paths in numbered.items() if chapter in paths), None)
    if subject_number is None:
        unresolved.add(f"chapter-number:{chapter}")
        return ()
    if subject_number in duplicates:
        return ()
    ordered = sorted(numbered.items())
    index = next(index for index, item in enumerate(ordered) if item[0] == subject_number)
    neighbors: list[str] = []
    if index > 0 and len(ordered[index - 1][1]) == 1:
        neighbors.append(ordered[index - 1][1][0])
    if index + 1 < len(ordered) and len(ordered[index + 1][1]) == 1:
        neighbors.append(ordered[index + 1][1][0])
    return tuple(neighbors)


def _scan_documents(project: Project, warnings: "_OrderedStrings") -> tuple[tuple[str, Document], ...]:
    documents: list[tuple[str, Document]] = []
    for path in project.iter_managed_markdown():
        relative = project.relative_id(path)
        if relative.endswith("/_index.md"):
            continue
        try:
            documents.append((relative, _read_document(path)))
        except (OSError, UnicodeError, ValueError) as error:
            warnings.add(f"cannot inspect structured context evidence in {relative}: {error}")
    return tuple(documents)


def _explicitly_active(document: Document, accepted: frozenset[str]) -> bool:
    status = document.metadata.get("status")
    return isinstance(status, str) and status.strip().casefold() in accepted


def _document_points_to(
    project: Project,
    relative: str,
    document: Document,
    anchors: set[str],
    warnings: "_OrderedStrings",
) -> bool:
    values: list[str] = []
    subject = document.metadata.get("subject")
    if isinstance(subject, str) and subject.strip():
        values.append(subject.strip())
    values.extend(_metadata_references(document))
    for raw in values:
        try:
            resolved = _resolve_reference(raw, relative, project_relative=True)
        except (UnicodeError, ValueError) as error:
            warnings.add(f"invalid structured reference {raw!r} in {relative}: {error}")
            continue
        if resolved in anchors:
            return True
    return _markdown_points_to(project, relative, document.body, anchors)


def _markdown_points_to(project: Project, relative: str, body: str, anchors: set[str]) -> bool:
    for raw in _markdown_references(body):
        try:
            resolved = _resolve_reference(raw, relative, project_relative=False)
        except (UnicodeError, ValueError):
            continue
        if resolved in anchors and resolved is not None and _safe_regular(project, resolved):
            return True
    return False


def _known_character(project: Project, character: str) -> bool:
    directory = project.root / "kb/characters"
    if not directory.is_dir() or directory.is_symlink():
        return False
    expected = _identity(character)
    for path in directory.iterdir():
        relative = f"kb/characters/{path.name}"
        if path.name != "_index.md" and path.suffix.casefold() == ".md" and _safe_regular(project, relative):
            if _identity(path.stem) == expected:
                return True
    return False


def _safe_regular(project: Project, relative: str) -> bool:
    try:
        normalized = _normalize_relative(relative)
    except ContextPlanError:
        return False
    current = project.root
    for index, part in enumerate(PurePosixPath(normalized).parts):
        current /= part
        try:
            mode = current.lstat().st_mode
        except (FileNotFoundError, NotADirectoryError, OSError):
            return False
        if stat.S_ISLNK(mode):
            return False
        if index < len(PurePosixPath(normalized).parts) - 1:
            if not stat.S_ISDIR(mode):
                return False
            manifest = current / "project.md"
            if current != project.root and manifest.is_file() and not manifest.is_symlink():
                return False
        elif not stat.S_ISREG(mode):
            return False
    return True


def _normalize_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ContextPlanError("path must be a non-empty forward-slash project-relative string")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or windows.root or ".." in posix.parts:
        raise ContextPlanError("path must stay inside the project")
    parts = tuple(part for part in posix.parts if part not in {"", "."})
    if not parts or any(not _portable_component(part) for part in parts):
        raise ContextPlanError("path is not portable across supported platforms")
    return PurePosixPath(*parts).as_posix()


def _portable_component(value: str) -> bool:
    if unicodedata.normalize("NFC", value) != value:
        return False
    if value.endswith((".", " ")) or any(character in _WINDOWS_FORBIDDEN for character in value):
        return False
    stem = value.rstrip(". ").split(".", 1)[0].upper()
    return stem not in _WINDOWS_RESERVED


def _read_document(path: Path) -> Document:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("not a regular file")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            return parse_document(stream.read())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _identity(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


class _OrderedStrings:
    def __init__(self) -> None:
        self._items: list[str] = []
        self._identities: set[str] = set()

    def add(self, value: str) -> None:
        identity = _identity(value)
        if identity not in self._identities:
            self._identities.add(identity)
            self._items.append(value)

    @property
    def values(self) -> tuple[str, ...]:
        return tuple(self._items)


class _OrderedPaths(_OrderedStrings):
    @property
    def identities(self) -> frozenset[str]:
        return frozenset(self._identities)

    def discard_identities(self, identities: frozenset[str]) -> None:
        self._items = [item for item in self._items if _identity(item) not in identities]
        self._identities = {_identity(item) for item in self._items}


__all__ = ["ContextPlan", "ContextPlanError", "plan_context"]
