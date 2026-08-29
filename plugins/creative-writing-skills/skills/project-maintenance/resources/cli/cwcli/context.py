"""Deterministic, read-only context planning from explicit project evidence."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import unquote, urlsplit

from . import __version__
from .checks.continuity import check_continuity
from .documents import Document, canonical_text, logical_hash, parse_document
from .findings import Finding
from .markdown_tables import malformed_table_lines, parse_tables, table_header_lines
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
_SOURCE_TAG = re.compile(r"</?(?:AI|hidden)>")
_SNAPSHOT_ID = re.compile(r"^[0-9a-f]{64}$")
_SNAPSHOT_VERSION = 1
_MANIFEST_KEYS = frozenset(
    {
        "snapshot_version",
        "snapshot_id",
        "cli_version",
        "created_at",
        "kind",
        "subject",
        "role",
        "required",
        "suggested",
        "boundary_warning",
        "sources",
    }
)
_SOURCE_KEYS = frozenset(
    {"path", "logical_hash", "exact_hash", "snapshot_path", "snapshot_exact_hash"}
)


class ContextPlanError(ValueError):
    """Raised when the requested context subject or role is unsafe."""


class ContextSnapshotError(ValueError):
    """Raised when a restricted snapshot cannot be derived or handled safely."""


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


@dataclass(frozen=True)
class SnapshotResult:
    """A restricted derived snapshot and its stable on-disk identity."""

    snapshot_id: str
    directory: str
    role: str
    files: dict[str, bytes]
    manifest: dict[str, object]
    boundary_warning: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "status": "created",
            "snapshot_id": self.snapshot_id,
            "directory": self.directory,
            "role": self.role,
            "files": list(self.files),
            "boundary_warning": self.boundary_warning,
            "manifest": self.manifest,
        }


@dataclass(frozen=True)
class ContextCleanupResult:
    """Validated cache directories selected for preview or removal."""

    status: str
    directories: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {"status": self.status, "directories": list(self.directories)}


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


def render_snapshot(project: Project, plan: ContextPlan) -> SnapshotResult:
    """Render and atomically install one explicit-only restricted snapshot."""

    if plan.role == "trusted":
        raise ContextSnapshotError("trusted context uses source paths; a snapshot is unnecessary")
    character = _validate_role(project, plan.role)
    if plan.role != "reader" and character is None:
        raise ContextSnapshotError(f"unsupported restricted snapshot role: {plan.role}")

    selected = _stable_sources(plan)
    if not selected:
        raise ContextSnapshotError("context plan contains no safe selected sources")

    files: dict[str, bytes] = {}
    source_records: list[dict[str, str]] = []
    boundary_warning = False
    for relative in selected:
        if not _safe_regular(project, relative):
            raise ContextSnapshotError(f"snapshot source is missing, linked, nested, or unsafe: {relative}")
        raw = _read_regular_bytes(project.root / relative)
        try:
            rendered, warns = _redact_source(raw, character=character)
            source_logical_hash = logical_hash(raw)
        except (UnicodeError, ValueError) as error:
            raise ContextSnapshotError(f"cannot safely redact {relative}: {error}") from error
        snapshot_path = f"files/{relative}"
        files[relative] = rendered
        boundary_warning = boundary_warning or warns
        source_records.append(
            {
                "path": relative,
                "logical_hash": source_logical_hash,
                "exact_hash": _exact_hash(raw),
                "snapshot_path": snapshot_path,
                "snapshot_exact_hash": _exact_hash(rendered),
            }
        )

    identity = {
        "snapshot_version": _SNAPSHOT_VERSION,
        "cli_version": __version__,
        "kind": plan.kind,
        "subject": plan.subject,
        "role": plan.role,
        "required": list(plan.required),
        "suggested": list(plan.suggested),
        "boundary_warning": boundary_warning,
        "sources": source_records,
    }
    snapshot_id = hashlib.sha256(_canonical_json(identity)).hexdigest()
    manifest: dict[str, object] = {
        **identity,
        "snapshot_id": snapshot_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    cache_root = _ensure_cache_root(project)
    destination = cache_root / snapshot_id
    relative_directory = f".creative-writing/context/{snapshot_id}"

    if destination.exists() or destination.is_symlink():
        existing = _load_snapshot_manifest(cache_root, destination)
        if _manifest_without_created(existing) != _manifest_without_created(manifest):
            raise ContextSnapshotError(f"snapshot identity collision or corrupt existing snapshot: {snapshot_id}")
        _validate_snapshot_files(destination, existing)
        return SnapshotResult(
            snapshot_id=snapshot_id,
            directory=relative_directory,
            role=plan.role,
            files=files,
            manifest=existing,
            boundary_warning=boundary_warning,
        )

    temporary = Path(tempfile.mkdtemp(prefix=f".{snapshot_id}.tmp-", dir=cache_root))
    try:
        for relative, data in files.items():
            _write_new_file(temporary / "files" / PurePosixPath(relative), data, root=temporary)
        _write_new_file(
            temporary / "manifest.json",
            _canonical_json(manifest) + b"\n",
            root=temporary,
        )
        _sync_tree(temporary)
        os.rename(temporary, destination)
        _fsync_directory(cache_root)
    except BaseException:
        if temporary.exists() and not temporary.is_symlink():
            shutil.rmtree(temporary)
        raise

    return SnapshotResult(
        snapshot_id=snapshot_id,
        directory=relative_directory,
        role=plan.role,
        files=files,
        manifest=manifest,
        boundary_warning=boundary_warning,
    )


def snapshot_status(project: Project) -> list[Finding]:
    """Report derived cache health without participating in ordinary checks."""

    findings: list[Finding] = []
    cache_root = project.root / ".creative-writing/context"
    if not cache_root.exists() and not cache_root.is_symlink():
        return findings
    if cache_root.is_symlink() or not cache_root.is_dir():
        return [_context_finding("CW-CONTEXT-UNSAFE", "context cache root is linked or not a directory")]

    for entry in sorted(cache_root.iterdir(), key=lambda item: item.name):
        relative = f".creative-writing/context/{entry.name}"
        if entry.is_symlink() or not entry.is_dir() or _SNAPSHOT_ID.fullmatch(entry.name) is None:
            findings.append(_context_finding("CW-CONTEXT-UNSAFE", "unsafe or unknown context cache entry", relative))
            continue
        try:
            manifest = _load_snapshot_manifest(cache_root, entry)
            _validate_snapshot_files(entry, manifest)
        except (ContextSnapshotError, OSError, UnicodeError, ValueError) as error:
            findings.append(_context_finding("CW-CONTEXT-CORRUPT", str(error), relative))
            continue
        for source in manifest["sources"]:
            assert isinstance(source, dict)
            source_path = source["path"]
            assert isinstance(source_path, str)
            if not _safe_regular(project, source_path):
                findings.append(
                    _context_finding(
                        "CW-CONTEXT-MISSING",
                        f"snapshot source is missing or unsafe: {source_path}",
                        relative,
                    )
                )
                continue
            try:
                data = _read_regular_bytes(project.root / source_path)
                current_exact = _exact_hash(data)
                current_logical = logical_hash(data)
            except (OSError, UnicodeError, ValueError) as error:
                findings.append(_context_finding("CW-CONTEXT-CORRUPT", f"cannot inspect {source_path}: {error}", relative))
                continue
            if current_exact != source["exact_hash"] or current_logical != source["logical_hash"]:
                findings.append(
                    _context_finding(
                        "CW-CONTEXT-STALE",
                        f"snapshot source changed: {source_path}",
                        relative,
                    )
                )
    return findings


def clean_context(project: Project, *, apply: bool = False) -> ContextCleanupResult:
    """Preview or remove only structurally validated snapshot directories."""

    cache_root = project.root / ".creative-writing/context"
    if not cache_root.exists() and not cache_root.is_symlink():
        return ContextCleanupResult("applied" if apply else "preview", ())
    if cache_root.is_symlink() or not cache_root.is_dir():
        raise ContextSnapshotError("unsafe context cache root")

    validated: list[Path] = []
    for entry in sorted(cache_root.iterdir(), key=lambda item: item.name):
        if entry.is_symlink() or not entry.is_dir() or _SNAPSHOT_ID.fullmatch(entry.name) is None:
            raise ContextSnapshotError(f"unsafe or unknown context cache entry: {entry.name}")
        manifest = _load_snapshot_manifest(cache_root, entry)
        _validate_snapshot_files(entry, manifest)
        _validate_cleanup_tree(entry, manifest)
        validated.append(entry)

    directories = tuple(f".creative-writing/context/{entry.name}" for entry in validated)
    if apply:
        for entry in validated:
            _remove_tree_no_follow(cache_root, entry)
        _fsync_directory(cache_root)
    return ContextCleanupResult("applied" if apply else "preview", directories)


def _stable_sources(plan: ContextPlan) -> tuple[str, ...]:
    result: list[str] = []
    identities: set[str] = set()
    for relative in (*plan.required, *plan.suggested):
        normalized = _normalize_relative(relative)
        identity = _identity(normalized)
        if identity not in identities:
            identities.add(identity)
            result.append(normalized)
    return tuple(result)


def _redact_source(data: bytes, *, character: str | None) -> tuple[bytes, bool]:
    text = canonical_text(data)
    text = _remove_hidden(text)
    if malformed_table_lines(text):
        lines = ", ".join(str(line) for line in malformed_table_lines(text))
        raise ContextSnapshotError(f"malformed Markdown table at line(s) {lines}")
    if character is not None:
        text = _filter_character_tables(text, character)
    return text.encode("utf-8"), _has_unmarked_prose(text)


def _remove_hidden(text: str) -> str:
    pieces: list[str] = []
    stack: list[str] = []
    cursor = 0
    hidden_start: int | None = None
    for match in _SOURCE_TAG.finditer(text):
        token = match.group(0)
        closing = token.startswith("</")
        name = token[2:-1] if closing else token[1:-1]
        if closing:
            if not stack or stack[-1] != name:
                raise ContextSnapshotError(f"crossed or unmatched source tag: {token}")
            stack.pop()
            if name == "hidden":
                assert hidden_start is not None
                pieces.append(text[cursor:hidden_start])
                cursor = match.end()
                hidden_start = None
        else:
            if name in stack:
                raise ContextSnapshotError(f"nested source tag is not supported: {token}")
            if name == "hidden":
                hidden_start = match.start()
            stack.append(name)
    if stack:
        raise ContextSnapshotError(f"unclosed source tag: <{stack[-1]}>")
    pieces.append(text[cursor:])
    return "".join(pieces)


def _filter_character_tables(text: str, character: str) -> str:
    lines = text.splitlines(keepends=True)
    remove: set[int] = set()
    expected = _identity(character.strip())
    for header_line, table in zip(table_header_lines(text), parse_tables(text)):
        normalized_headers = tuple(_identity(header.strip()) for header in table.headers)
        column = next(
            (index for index, header in enumerate(normalized_headers) if header in {"character", "knower"}),
            None,
        )
        if column is None:
            continue
        for row in table.rows:
            if _identity(row.cells[column].strip()) != expected:
                remove.add(row.line - 1)
    return "".join(line for index, line in enumerate(lines) if index not in remove)


def _has_unmarked_prose(text: str) -> bool:
    document = parse_document(text.encode("utf-8"))
    body = document.body
    table_lines: set[int] = set()
    for header_line, table in zip(table_header_lines(body), parse_tables(body)):
        table_lines.update((header_line, header_line + 1))
        table_lines.update(row.line for row in table.rows)
    for line_number, line in enumerate(body.splitlines(), 1):
        stripped = line.strip()
        if not stripped or line_number in table_lines:
            continue
        if stripped.startswith("#") or stripped in {"---", "***", "___", "<AI>", "</AI>"}:
            continue
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            continue
        return True
    return False


def _ensure_cache_root(project: Project) -> Path:
    protected = project.root / ".creative-writing"
    if protected.is_symlink() or (protected.exists() and not protected.is_dir()):
        raise ContextSnapshotError("unsafe .creative-writing root")
    if not protected.exists():
        protected.mkdir()
        _fsync_directory(project.root)
    cache_root = protected / "context"
    if cache_root.is_symlink() or (cache_root.exists() and not cache_root.is_dir()):
        raise ContextSnapshotError("unsafe context cache root")
    if not cache_root.exists():
        cache_root.mkdir()
        _fsync_directory(protected)
    _open_directory_no_follow(protected)
    _open_directory_no_follow(cache_root)
    return cache_root


def _load_snapshot_manifest(cache_root: Path, directory: Path) -> dict[str, object]:
    if directory.parent != cache_root or directory.is_symlink() or not directory.is_dir():
        raise ContextSnapshotError("snapshot directory is outside the exact cache root or unsafe")
    if _SNAPSHOT_ID.fullmatch(directory.name) is None:
        raise ContextSnapshotError("snapshot directory has an invalid identifier")
    data = _read_regular_bytes(directory / "manifest.json")
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ContextSnapshotError(f"invalid snapshot manifest: {error}") from error
    if not isinstance(payload, dict) or set(payload) != _MANIFEST_KEYS:
        raise ContextSnapshotError("snapshot manifest has an invalid field set")
    if payload.get("snapshot_version") != _SNAPSHOT_VERSION:
        raise ContextSnapshotError("snapshot manifest has an unsupported version")
    for key in ("snapshot_id", "cli_version", "created_at", "kind", "subject", "role"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ContextSnapshotError(f"snapshot manifest field {key} must be a non-empty string")
    if payload["snapshot_id"] != directory.name:
        raise ContextSnapshotError("snapshot manifest identity does not match its directory")
    if payload["kind"] not in _KINDS:
        raise ContextSnapshotError("snapshot manifest has an invalid context kind")
    if payload["role"] == "trusted" or not (
        payload["role"] == "reader" or str(payload["role"]).startswith("character:")
    ):
        raise ContextSnapshotError("snapshot manifest has an invalid restricted role")
    role = str(payload["role"])
    character = role.removeprefix("character:") if role.startswith("character:") else None
    if character is not None and not _safe_character_stem(character):
        raise ContextSnapshotError("snapshot manifest has an unsafe character role")
    try:
        created_at = datetime.fromisoformat(str(payload["created_at"]).replace("Z", "+00:00"))
    except ValueError as error:
        raise ContextSnapshotError("snapshot manifest has an invalid created_at timestamp") from error
    if created_at.tzinfo is None:
        raise ContextSnapshotError("snapshot manifest created_at must include a timezone")
    subject = _normalize_relative(str(payload["subject"]))
    if allowed_document_kind(subject) not in _SELECTABLE_KINDS:
        raise ContextSnapshotError("snapshot manifest subject is outside selectable roots")
    if not isinstance(payload.get("boundary_warning"), bool):
        raise ContextSnapshotError("snapshot boundary_warning must be boolean")
    for key in ("required", "suggested"):
        value = payload.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ContextSnapshotError(f"snapshot manifest field {key} must be a string list")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ContextSnapshotError("snapshot manifest sources must be a non-empty list")
    seen: set[str] = set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != _SOURCE_KEYS:
            raise ContextSnapshotError("snapshot source record has an invalid field set")
        if not all(isinstance(source[key], str) and source[key] for key in _SOURCE_KEYS):
            raise ContextSnapshotError("snapshot source record values must be non-empty strings")
        relative = _normalize_relative(source["path"])
        if relative in seen or source["snapshot_path"] != f"files/{relative}":
            raise ContextSnapshotError("snapshot source order contains duplicates or an invalid derived path")
        seen.add(relative)
        for hash_key in ("logical_hash", "exact_hash", "snapshot_exact_hash"):
            if _SNAPSHOT_ID.fullmatch(source[hash_key]) is None:
                raise ContextSnapshotError(f"snapshot source {hash_key} is invalid")
    planned_sources: list[str] = []
    planned_identities: set[str] = set()
    for key in ("required", "suggested"):
        value = payload[key]
        assert isinstance(value, list)
        for raw in value:
            normalized = _normalize_relative(raw)
            identity = _identity(normalized)
            if identity not in planned_identities:
                planned_identities.add(identity)
                planned_sources.append(normalized)
    if planned_sources != [str(source["path"]) for source in sources]:
        raise ContextSnapshotError("snapshot source order does not match its context plan")
    identity_payload = {
        key: payload[key]
        for key in _MANIFEST_KEYS
        if key not in {"snapshot_id", "created_at"}
    }
    expected_id = hashlib.sha256(_canonical_json(identity_payload)).hexdigest()
    if expected_id != directory.name:
        raise ContextSnapshotError("snapshot manifest content does not match its stable identifier")
    return payload


def _validate_snapshot_files(directory: Path, manifest: dict[str, object]) -> None:
    _validate_cleanup_tree(directory, manifest)
    sources = manifest["sources"]
    assert isinstance(sources, list)
    for source in sources:
        assert isinstance(source, dict)
        snapshot_path = source["snapshot_path"]
        assert isinstance(snapshot_path, str)
        path = directory / PurePosixPath(snapshot_path)
        data = _read_regular_bytes(path)
        if _exact_hash(data) != source["snapshot_exact_hash"]:
            raise ContextSnapshotError(f"derived snapshot file hash mismatch: {snapshot_path}")


def _validate_cleanup_tree(directory: Path, manifest: dict[str, object]) -> None:
    expected_files = {"manifest.json"}
    sources = manifest["sources"]
    assert isinstance(sources, list)
    expected_files.update(str(source["snapshot_path"]) for source in sources if isinstance(source, dict))
    actual_files: set[str] = set()
    for root, directories, files in os.walk(directory, topdown=True, followlinks=False):
        root_path = Path(root)
        for name in list(directories):
            child = root_path / name
            if child.is_symlink():
                raise ContextSnapshotError(f"unsafe symlink in snapshot tree: {child.relative_to(directory)}")
        for name in files:
            child = root_path / name
            if child.is_symlink() or not child.is_file():
                raise ContextSnapshotError(f"unsafe entry in snapshot tree: {child.relative_to(directory)}")
            actual_files.add(child.relative_to(directory).as_posix())
    if actual_files != expected_files:
        raise ContextSnapshotError("snapshot tree contains missing or unknown files")


def _remove_tree_no_follow(cache_root: Path, directory: Path) -> None:
    try:
        directory.resolve(strict=True).relative_to(cache_root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as error:
        raise ContextSnapshotError("snapshot cleanup target is outside the cache root") from error
    if directory.parent != cache_root or directory.is_symlink() or not directory.is_dir():
        raise ContextSnapshotError("snapshot cleanup target is unsafe")
    for entry in sorted(directory.iterdir(), key=lambda item: item.name):
        if entry.is_symlink():
            raise ContextSnapshotError(f"snapshot cleanup refuses symlink: {entry.name}")
        if entry.is_dir():
            _remove_directory_contents_no_follow(cache_root, entry)
            entry.rmdir()
        elif entry.is_file():
            entry.unlink()
        else:
            raise ContextSnapshotError(f"snapshot cleanup refuses unknown entry: {entry.name}")
    directory.rmdir()


def _remove_directory_contents_no_follow(cache_root: Path, directory: Path) -> None:
    try:
        directory.resolve(strict=True).relative_to(cache_root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as error:
        raise ContextSnapshotError("snapshot cleanup descendant escaped the cache root") from error
    for entry in sorted(directory.iterdir(), key=lambda item: item.name):
        if entry.is_symlink():
            raise ContextSnapshotError(f"snapshot cleanup refuses symlink: {entry.name}")
        if entry.is_dir():
            _remove_directory_contents_no_follow(cache_root, entry)
            entry.rmdir()
        elif entry.is_file():
            entry.unlink()
        else:
            raise ContextSnapshotError(f"snapshot cleanup refuses unknown entry: {entry.name}")


def _write_new_file(path: Path, data: bytes, *, root: Path) -> None:
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ContextSnapshotError("derived snapshot path escaped its temporary root") from error
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _sync_tree(root: Path) -> None:
    for directory, child_directories, _files in os.walk(root, topdown=False, followlinks=False):
        for name in child_directories:
            child = Path(directory) / name
            if child.is_symlink():
                raise ContextSnapshotError("temporary snapshot contains a symlink")
            _fsync_directory(child)
        _fsync_directory(Path(directory))


def _open_directory_no_follow(directory: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(directory, flags)
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise ContextSnapshotError(f"not a safe directory: {directory}")
    finally:
        os.close(descriptor)


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(directory, flags)
    try:
        os.fsync(descriptor)
    except OSError as error:
        unsupported = {
            errno.EINVAL,
            getattr(errno, "ENOTSUP", errno.EINVAL),
            getattr(errno, "EOPNOTSUPP", errno.EINVAL),
        }
        if error.errno not in unsupported:
            raise
    finally:
        os.close(descriptor)


def _read_regular_bytes(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ContextSnapshotError(f"not a regular no-follow file: {path}")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            return stream.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _exact_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest_without_created(manifest: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in manifest.items() if key != "created_at"}


def _context_finding(code: str, message: str, path: str = ".creative-writing/context") -> Finding:
    return Finding(
        code=code,
        severity="warning",
        message=message,
        path=path,
        next_action="run cw clean-context, review the preview, then add --apply",
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


__all__ = [
    "ContextCleanupResult",
    "ContextPlan",
    "ContextPlanError",
    "ContextSnapshotError",
    "SnapshotResult",
    "clean_context",
    "plan_context",
    "render_snapshot",
    "snapshot_status",
]
