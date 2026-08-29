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
_LINK_START = re.compile(r"(?<!!)\[[^\]]*\]\(")
_ACTIVE_PLAN = frozenset({"active", "planned", "ready", "review", "working"})
_ACTIVE_ISSUE = frozenset({"active", "blocked", "open", "review", "working"})
_SELECTABLE_KINDS = frozenset(
    {"chapter", "work-artifact", "kb-content", "continuity-record", "continuity-scene", "vocabulary"}
)
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
    catalog = _PathCatalog.from_project(project)
    if catalog.collision(subject) is None:
        required.add(subject)
    else:
        _record_collision(subject, catalog, unresolved, warnings)
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
                catalog=catalog,
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
            catalog=catalog,
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
            catalog=catalog,
            project_relative=False,
        )
        if resolved is not None:
            anchors.add(resolved)

    for relative in _CONTINUITY:
        _add_selected_path(
            project,
            relative,
            required,
            catalog=catalog,
            unresolved=unresolved,
            warnings=warnings,
            dependency=True,
        )

    chapter = target if kind == "draft" else subject if kind == "chapter" else None
    if chapter is not None:
        for neighbor in _chapter_neighbors(project, chapter, catalog, unresolved, warnings):
            _add_selected_path(
                project, neighbor, suggested, catalog=catalog,
                unresolved=unresolved, warnings=warnings,
            )

    documents = _scan_documents(project, warnings)
    for relative, document in documents:
        if relative.startswith("work/plans/") and _explicitly_active(document, _ACTIVE_PLAN):
            if _document_points_to(project, relative, document, anchors, warnings):
                _add_selected_path(
                    project, relative, suggested, catalog=catalog,
                    unresolved=unresolved, warnings=warnings,
                )

    for relative, document in documents:
        if relative in anchors:
            continue
        if relative.startswith("work/plans/") or relative.startswith("kb/issues/"):
            continue
        if _document_points_to(project, relative, document, anchors, warnings):
            _add_selected_path(
                project, relative, suggested, catalog=catalog,
                unresolved=unresolved, warnings=warnings,
            )

    for relative, document in documents:
        if relative.startswith("kb/issues/") and _explicitly_active(document, _ACTIVE_ISSUE):
            if _document_points_to(project, relative, document, anchors, warnings):
                _add_selected_path(
                    project, relative, suggested, catalog=catalog,
                    unresolved=unresolved, warnings=warnings,
                )

    try:
        continuity_findings = check_continuity(project)
    except Exception as error:
        warnings.add(f"continuity context evidence could not be inspected: {error}")
    else:
        for finding in continuity_findings:
            if finding.path and _safe_regular(project, finding.path):
                _add_selected_path(
                    project, finding.path, suggested, catalog=catalog,
                    unresolved=unresolved, warnings=warnings,
                )
            if finding.severity in {"warning", "error"}:
                location = finding.path or "project"
                warnings.add(f"{finding.code}: structured continuity issue at {location}")

    if character is not None:
        character_path = f"kb/characters/{character}.md"
        if catalog.collision(character_path) is not None:
            _record_collision(character_path, catalog, unresolved, warnings)
            unresolved.add(f"character:{character}")
            warnings.add(f"ambiguous character role: {character}")
        elif not _known_character(project, character):
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
    if not _safe_character_stem(character):
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
    references: list[str] = []
    cursor = 0
    while True:
        match = _LINK_START.search(text, cursor)
        if match is None:
            break
        start = match.end()
        depth = 1
        quote: str | None = None
        angle_destination = False
        escaped = False
        title_space = False
        for index in range(start, len(text)):
            character = text[index]
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if angle_destination:
                if character == ">":
                    angle_destination = False
                continue
            if quote is not None:
                if character == quote:
                    quote = None
                continue
            if index == start and character == "<":
                angle_destination = True
                continue
            if character.isspace():
                title_space = True
                continue
            if title_space and character in {'"', "'"}:
                quote = character
                continue
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    references.append(text[start:index].strip())
                    cursor = index + 1
                    break
        else:
            cursor = match.end()
            continue
    return tuple(references)


def _add_reference(
    project: Project,
    raw: str,
    *,
    source: str,
    required: "_OrderedPaths",
    unresolved: "_OrderedStrings",
    warnings: "_OrderedStrings",
    catalog: "_PathCatalog",
    project_relative: bool,
    expected_kind: str | None = None,
) -> str | None:
    try:
        relative = _resolve_reference(
            raw,
            source,
            project_relative=project_relative,
            markdown=not project_relative,
        )
    except (UnicodeError, ValueError) as error:
        unresolved.add(raw)
        warnings.add(f"invalid explicit reference {raw!r} in {source}: {error}")
        return None
    if relative is None:
        return None
    if not _selectable_context_path(relative):
        unresolved.add(relative)
        warnings.add(f"explicit reference is outside managed context roots: {relative}")
        return None
    if expected_kind is not None and allowed_document_kind(relative) != expected_kind:
        unresolved.add(relative)
        warnings.add(f"explicit reference has the wrong document kind: {relative}")
        return None
    if not _add_selected_path(
        project,
        relative,
        required,
        catalog=catalog,
        unresolved=unresolved,
        warnings=warnings,
    ):
        return None
    return relative


def _resolve_reference(
    raw: str,
    source: str,
    *,
    project_relative: bool,
    markdown: bool,
) -> str | None:
    destination = _markdown_destination(raw) if markdown else raw.strip()
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


def _markdown_destination(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<"):
        closing = value.find(">", 1)
        if closing < 0:
            raise ValueError("unterminated angle-bracket link destination")
        destination = value[1:closing]
        title = value[closing + 1 :].strip()
    else:
        match = re.match(r"^(\S+)(?:\s+(.+))?$", value)
        if match is None:
            raise ValueError("empty Markdown link destination")
        destination, title = match.groups()
        title = title or ""
    if title and not (
        (title.startswith('"') and title.endswith('"'))
        or (title.startswith("'") and title.endswith("'"))
        or (title.startswith("(") and title.endswith(")"))
    ):
        raise ValueError("invalid Markdown link title")
    return destination


def _chapter_neighbors(
    project: Project,
    chapter: str,
    catalog: "_PathCatalog",
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
        if catalog.collision(relative) is not None:
            _record_collision(relative, catalog, unresolved, warnings)
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
            resolved = _resolve_reference(raw, relative, project_relative=True, markdown=False)
        except (UnicodeError, ValueError) as error:
            warnings.add(f"invalid structured reference {raw!r} in {relative}: {error}")
            continue
        if resolved in anchors:
            return True
    return _markdown_points_to(project, relative, document.body, anchors)


def _markdown_points_to(project: Project, relative: str, body: str, anchors: set[str]) -> bool:
    for raw in _markdown_references(body):
        try:
            resolved = _resolve_reference(raw, relative, project_relative=False, markdown=True)
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
        if (
            path.name != "_index.md"
            and path.suffix.casefold() == ".md"
            and _safe_character_stem(path.stem)
            and _safe_regular(project, relative)
        ):
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
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return False
    stem = value.rstrip(". ").split(".", 1)[0].upper()
    return stem not in _WINDOWS_RESERVED


def _safe_character_stem(value: str) -> bool:
    return (
        bool(value)
        and value == value.strip()
        and value not in {".", ".."}
        and "/" not in value
        and _portable_component(value)
    )


def _selectable_context_path(relative: str) -> bool:
    return allowed_document_kind(relative) in _SELECTABLE_KINDS


def _add_selected_path(
    project: Project,
    relative: str,
    selected: "_OrderedPaths",
    *,
    catalog: "_PathCatalog",
    unresolved: "_OrderedStrings",
    warnings: "_OrderedStrings",
    dependency: bool = False,
) -> bool:
    if not _selectable_context_path(relative):
        unresolved.add(relative)
        warnings.add(f"context source is outside managed story/work/kb roots: {relative}")
        return False
    if catalog.collision(relative) is not None:
        _record_collision(relative, catalog, unresolved, warnings)
        selected.discard_identity(_identity(relative))
        return False
    if not _safe_regular(project, relative):
        unresolved.add(relative)
        qualifier = "canonical dependency" if dependency else "context source"
        warnings.add(f"missing or unsafe {qualifier}: {relative}")
        return False
    selected.add(relative)
    return True


def _record_collision(
    relative: str,
    catalog: "_PathCatalog",
    unresolved: "_OrderedStrings",
    warnings: "_OrderedStrings",
) -> None:
    paths = catalog.collision(relative)
    assert paths is not None
    rendered = ", ".join(paths)
    unresolved.add(f"portable-path-collision:{rendered}")
    warnings.add(f"ambiguous portable path identity selects neither source: {rendered}")


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


@dataclass(frozen=True)
class _PathCatalog:
    collisions: dict[str, tuple[str, ...]]

    @classmethod
    def from_project(cls, project: Project) -> "_PathCatalog":
        identities: dict[str, list[str]] = {}
        for path in project.iter_managed_markdown():
            relative = project.relative_id(path)
            if _selectable_context_path(relative):
                identities.setdefault(_identity(relative), []).append(relative)
        return cls(
            collisions={
                identity: tuple(sorted(paths, key=lambda item: (item.casefold(), item)))
                for identity, paths in identities.items()
                if len(paths) > 1
            }
        )

    def collision(self, relative: str) -> tuple[str, ...] | None:
        return self.collisions.get(_identity(relative))


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

    def discard_identity(self, identity: str) -> None:
        self._items = [item for item in self._items if _identity(item) != identity]
        self._identities.discard(identity)


__all__ = ["ContextPlan", "ContextPlanError", "plan_context"]
