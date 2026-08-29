"""Deterministic, read-only context planning from explicit project evidence."""

from __future__ import annotations

import errno
import ctypes
import hashlib
import json
import os
import re
import stat
import unicodedata
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import unquote, urlsplit

from . import __version__
from .checks.continuity import check_continuity
from .documents import Document, canonical_text, logical_hash, parse_document
from .findings import Finding
from .markdown_tables import malformed_table_headers, malformed_table_lines, parse_tables, table_header_lines
from .markdown_links import extract_links
from .project import Project
from .schema import allowed_document_kind


_KINDS = frozenset({"draft", "chapter", "kb"})
_ACTIVE_PLAN = frozenset({"active", "planned", "ready", "review", "working"})
_ACTIVE_ISSUE = frozenset({"active", "blocked", "open", "review", "working"})
_SELECTABLE_KINDS = frozenset(
    {"chapter", "work-artifact", "kb-content", "continuity-record", "continuity-scene", "vocabulary"}
)
_DIRECT_KEYS = ("related", "context", "links", "sources", "subject")
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
_HIDDEN_LIKE = re.compile(r"<\s*/?\s*hidden", re.IGNORECASE)
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
        "unresolved",
        "warnings",
        "boundary_warning",
        "sources",
    }
)
_SOURCE_KEYS = frozenset(
    {"path", "logical_hash", "exact_hash", "snapshot_path", "snapshot_exact_hash"}
)
_PARTIAL_OWNER = ".cw-context-partial-owner"
_PARTIAL_OWNER_KIND = "cw-context-snapshot-v1"


class ContextPlanError(ValueError):
    """Raised when the requested context subject or role is unsafe."""


class ContextSnapshotError(ValueError):
    """Raised when a restricted snapshot cannot be derived or handled safely."""


@dataclass
class _HeldDirectory:
    """An opened directory plus fallback identities retained for one operation."""

    path: Path
    descriptor: int
    identity: tuple[int, int]
    ancestors: tuple[tuple[Path, tuple[int, int]], ...]
    descriptor_relative: bool

    def close(self) -> None:
        if self.descriptor >= 0:
            os.close(self.descriptor)
            self.descriptor = -1

    def revalidate(self, label: str) -> None:
        if self.descriptor >= 0:
            opened = os.fstat(self.descriptor)
            if (opened.st_dev, opened.st_ino) != self.identity or not stat.S_ISDIR(opened.st_mode):
                raise ContextSnapshotError(f"unsafe {label}: opened directory changed")
        if self.descriptor_relative:
            return
        for path, identity in self.ancestors:
            entry = path.lstat()
            if _unsafe_reparse(entry) or not stat.S_ISDIR(entry.st_mode):
                raise ContextSnapshotError(f"unsafe {label}: fallback ancestor became unsafe")
            if (entry.st_dev, entry.st_ino) != identity:
                raise ContextSnapshotError(f"unsafe {label}: fallback ancestor changed")


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
    findings: tuple[Finding, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "directories": list(self.directories),
            "findings": [asdict(finding) for finding in self.findings],
        }


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
    dependency_body = subject_document.body
    if role != "trusted":
        dependency_body = _remove_hidden(dependency_body)
    for raw in _markdown_references(dependency_body):
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
            if _document_points_to(project, relative, document, anchors, warnings, restricted=role != "trusted"):
                _add_selected_path(
                    project, relative, suggested, catalog=catalog,
                    unresolved=unresolved, warnings=warnings,
                )

    for relative, document in documents:
        if relative in anchors:
            continue
        if relative.startswith("work/plans/") or relative.startswith("kb/issues/"):
            continue
        if _document_points_to(project, relative, document, anchors, warnings, restricted=role != "trusted"):
            _add_selected_path(
                project, relative, suggested, catalog=catalog,
                unresolved=unresolved, warnings=warnings,
            )

    for relative, document in documents:
        if relative.startswith("kb/issues/") and _explicitly_active(document, _ACTIVE_ISSUE):
            if _document_points_to(project, relative, document, anchors, warnings, restricted=role != "trusted"):
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
    cache = _cache_root(project, create=True)
    assert cache is not None
    project_root = _hold_directory_no_follow(project.root, "project root")
    temporary: _HeldDirectory | None = None
    temporary_name = ""
    owner_token = ""
    try:
        files: dict[str, bytes] = {}
        source_records: list[dict[str, str]] = []
        boundary_warning = False
        for relative in selected:
            raw = _read_from_handle(
                project_root,
                relative,
                "snapshot source",
                reject_nested_projects=True,
            )
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
            "unresolved": list(plan.unresolved),
            "warnings": list(plan.warnings),
            "boundary_warning": boundary_warning,
            "sources": source_records,
        }
        snapshot_id = hashlib.sha256(_canonical_json(identity)).hexdigest()
        manifest: dict[str, object] = {
            **identity,
            "snapshot_id": snapshot_id,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        relative_directory = f".creative-writing/context/{snapshot_id}"
        _cleanup_recognized_partials(cache, snapshot_id)
        owner_token = uuid.uuid4().hex
        temporary_name = f".partial-{snapshot_id}-{owner_token}"
        try:
            temporary = _reserve_snapshot_directory(
                cache,
                temporary_name,
                snapshot_id=snapshot_id,
                owner_token=owner_token,
            )
        except FileExistsError:
            raise ContextSnapshotError("could not reserve a unique owned snapshot partial")
        try:
            for relative, data in files.items():
                _write_to_handle(temporary, f"files/{relative}", data)
            _write_to_handle(temporary, "manifest.json", _canonical_json(manifest) + b"\n")
            _sync_handle_tree(temporary)
            _validate_snapshot_files(temporary, manifest, allow_owner=True)
            owner_info = _stat_child(temporary, _PARTIAL_OWNER, "snapshot partial owner")
            _unlink_child(
                temporary,
                _PARTIAL_OWNER,
                (owner_info.st_dev, owner_info.st_ino),
                "snapshot partial owner",
            )
            _fsync_handle(temporary)
            temporary.close()
            try:
                _rename_no_replace(cache, temporary_name, snapshot_id)
            except FileExistsError:
                _cleanup_owned_reservation(
                    cache,
                    temporary_name,
                    temporary.identity,
                    snapshot_id=snapshot_id,
                    owner_token=owner_token,
                )
                return _reuse_snapshot_winner(
                    cache,
                    snapshot_id=snapshot_id,
                    relative_directory=relative_directory,
                    role=plan.role,
                    files=files,
                    manifest=manifest,
                    boundary_warning=boundary_warning,
                )
            _fsync_handle(cache)
        except BaseException:
            _cleanup_owned_reservation(
                cache,
                temporary_name,
                temporary.identity,
                snapshot_id=snapshot_id,
                owner_token=owner_token,
            )
            raise

        return SnapshotResult(
            snapshot_id=snapshot_id,
            directory=relative_directory,
            role=plan.role,
            files=files,
            manifest=manifest,
            boundary_warning=boundary_warning,
        )
    finally:
        if temporary is not None:
            temporary.close()
        project_root.close()
        cache.close()


def snapshot_status(project: Project) -> list[Finding]:
    """Report derived cache health without participating in ordinary checks."""

    findings: list[Finding] = []
    try:
        cache = _cache_root(project, create=False)
    except (ContextSnapshotError, OSError, ValueError) as error:
        return [_context_finding("CW-CONTEXT-UNSAFE", str(error))]
    if cache is None:
        return findings
    project_root: _HeldDirectory | None = None
    try:
        project_root = _hold_directory_no_follow(project.root, "project root")
        for name in _directory_names(cache, "context cache root"):
            relative = f".creative-writing/context/{name}"
            try:
                info = _stat_child(cache, name, "context cache entry")
            except OSError as error:
                findings.append(_context_finding("CW-CONTEXT-UNSAFE", str(error), relative))
                continue
            if _unsafe_reparse(info) or not stat.S_ISDIR(info.st_mode) or _SNAPSHOT_ID.fullmatch(name) is None:
                findings.append(_context_finding("CW-CONTEXT-UNSAFE", "unsafe or unknown context cache entry", relative))
                continue
            snapshot: _HeldDirectory | None = None
            try:
                snapshot = _open_child_directory(cache, name, "snapshot directory")
                manifest = _load_snapshot_manifest(snapshot, name)
                _validate_snapshot_files(snapshot, manifest)
            except (ContextSnapshotError, OSError, UnicodeError, ValueError) as error:
                findings.append(_context_finding("CW-CONTEXT-CORRUPT", str(error), relative))
                continue
            finally:
                if snapshot is not None:
                    snapshot.close()
            for source in manifest["sources"]:
                assert isinstance(source, dict)
                source_path = source["path"]
                assert isinstance(source_path, str)
                try:
                    data = _read_from_handle(
                        project_root,
                        source_path,
                        "snapshot source",
                        reject_nested_projects=True,
                    )
                    current_exact = _exact_hash(data)
                    current_logical = logical_hash(data)
                except (FileNotFoundError, NotADirectoryError, ContextSnapshotError) as error:
                    findings.append(
                        _context_finding(
                            "CW-CONTEXT-MISSING",
                            f"snapshot source is missing or unsafe: {source_path}: {error}",
                            relative,
                        )
                    )
                    continue
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
            try:
                current_plan = plan_context(
                    project,
                    str(manifest["kind"]),
                    str(manifest["subject"]),
                    str(manifest["role"]),
                )
            except (ContextPlanError, ContextSnapshotError, OSError, UnicodeError, ValueError) as error:
                findings.append(_context_finding("CW-CONTEXT-STALE", f"snapshot plan can no longer be reproduced: {error}", relative))
            else:
                if any(
                    list(getattr(current_plan, key)) != manifest[key]
                    for key in ("required", "suggested", "unresolved", "warnings")
                ):
                    findings.append(_context_finding("CW-CONTEXT-STALE", "snapshot context plan changed", relative))
    finally:
        if project_root is not None:
            project_root.close()
        cache.close()
    return sorted(findings, key=lambda item: (item.path or "", item.code, item.message))


def clean_context(project: Project, *, apply: bool = False) -> ContextCleanupResult:
    """Preview or remove only structurally validated snapshot directories."""

    cache = _cache_root(project, create=False)
    if cache is None:
        return ContextCleanupResult("applied" if apply else "preview", (), ())
    validated: list[tuple[str, _HeldDirectory]] = []
    try:
        status_findings = tuple(snapshot_status(project))
        blocked = any(item.code in {"CW-CONTEXT-CORRUPT", "CW-CONTEXT-UNSAFE"} for item in status_findings)
        for name in _directory_names(cache, "context cache root"):
            info = _stat_child(cache, name, "context cache entry")
            if _unsafe_reparse(info) or not stat.S_ISDIR(info.st_mode) or _SNAPSHOT_ID.fullmatch(name) is None:
                raise ContextSnapshotError(f"unsafe or unknown context cache entry: {name}")
            snapshot: _HeldDirectory | None = None
            try:
                snapshot = _open_child_directory(cache, name, "snapshot cleanup target")
                manifest = _load_snapshot_manifest(snapshot, name)
                _validate_snapshot_files(snapshot, manifest)
                _validate_cleanup_tree(snapshot, manifest)
            except (ContextSnapshotError, OSError, UnicodeError, ValueError):
                if snapshot is not None:
                    snapshot.close()
                continue
            validated.append((name, snapshot))

        directories = tuple(f".creative-writing/context/{name}" for name, _snapshot in validated)
        if apply and blocked:
            raise ContextSnapshotError("context cleanup is blocked by corrupt, unsafe, or unknown cache entries")
        if apply:
            for name, snapshot in validated:
                _remove_directory_contents(snapshot)
                snapshot.revalidate("snapshot cleanup target")
                snapshot.close()
                _rmdir_child(cache, name, snapshot.identity, "snapshot cleanup target")
            _fsync_handle(cache)
        return ContextCleanupResult("applied" if apply else "preview", directories, status_findings)
    finally:
        for _name, snapshot in validated:
            snapshot.close()
        cache.close()


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
    if character is not None:
        unsafe_lines = [
            line
            for line, headers in malformed_table_headers(text)
            if {"character", "knower"} & {_identity(header) for header in headers}
        ]
        if unsafe_lines:
            lines = ", ".join(str(line) for line in unsafe_lines)
            raise ContextSnapshotError(f"malformed character-knowledge table at line(s) {lines}")
    if character is not None:
        text = _filter_character_tables(text, character)
    return text.encode("utf-8"), _has_unmarked_prose(text)


def _remove_hidden(text: str) -> str:
    exact_starts = {match.start() for match in _SOURCE_TAG.finditer(text) if "hidden" in match.group(0)}
    suspicious = next(
        (match for match in _HIDDEN_LIKE.finditer(text) if match.start() not in exact_starts),
        None,
    )
    if suspicious is not None:
        raise ContextSnapshotError(
            f"malformed or case-variant hidden source tag near offset {suspicious.start()}"
        )
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
    result = "".join(pieces)
    if _HIDDEN_LIKE.search(result) is not None:
        raise ContextSnapshotError("restricted snapshot would retain suspicious hidden markup")
    return result


def _filter_character_tables(text: str, character: str) -> str:
    lines = text.splitlines(keepends=True)
    remove: set[int] = set()
    expected = _identity(character.strip())
    for table in parse_tables(text):
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


def _cache_root(project: Project, *, create: bool) -> _HeldDirectory | None:
    root = Path(os.path.abspath(project.root))
    current = _hold_directory_no_follow(root, "project root")
    for component, label in (
        (".creative-writing", ".creative-writing root"),
        ("context", "context cache root"),
    ):
        try:
            child = _open_child_directory(current, component, label)
        except FileNotFoundError:
            if not create:
                current.close()
                return None
            try:
                current.revalidate(f"{label} parent")
                if current.descriptor_relative:
                    os.mkdir(component, mode=0o700, dir_fd=current.descriptor)
                else:
                    (current.path / component).mkdir(mode=0o700)
                    current.revalidate(f"{label} parent")
                child = _open_child_directory(current, component, label)
            except BaseException:
                current.close()
                raise
        except BaseException:
            current.close()
            raise
        current.close()
        current = child
    return current


def _reserve_snapshot_directory(
    cache: _HeldDirectory,
    name: str,
    *,
    snapshot_id: str,
    owner_token: str,
) -> _HeldDirectory:
    """Exclusively reserve and mark an owned sibling partial directory."""

    if name != f".partial-{snapshot_id}-{owner_token}" or not re.fullmatch(
        r"\.partial-[0-9a-f]{64}-[0-9a-f]{32}", name
    ):
        raise ContextSnapshotError("invalid snapshot reservation target")
    cache.revalidate("context cache root")
    if cache.descriptor_relative:
        os.mkdir(name, mode=0o700, dir_fd=cache.descriptor)
    else:
        (cache.path / name).mkdir(mode=0o700)
        cache.revalidate("context cache root")
    partial = _open_child_directory(cache, name, "snapshot partial")
    try:
        marker = _canonical_json(
            {"kind": _PARTIAL_OWNER_KIND, "snapshot_id": snapshot_id, "token": owner_token}
        )
        _write_to_handle(partial, _PARTIAL_OWNER, marker + b"\n")
        _fsync_handle(partial)
        return partial
    except BaseException:
        try:
            _remove_directory_contents(partial)
            partial.close()
            _rmdir_child(cache, name, partial.identity, "snapshot partial reservation")
        except (ContextSnapshotError, OSError):
            pass
        finally:
            partial.close()
        raise


def _reuse_snapshot_winner(
    cache: _HeldDirectory,
    *,
    snapshot_id: str,
    relative_directory: str,
    role: str,
    files: dict[str, bytes],
    manifest: dict[str, object],
    boundary_warning: bool,
) -> SnapshotResult:
    winner: _HeldDirectory | None = None
    try:
        winner = _open_child_directory(cache, snapshot_id, "snapshot winner")
        existing = _load_snapshot_manifest(winner, snapshot_id)
        _validate_snapshot_files(winner, existing)
    except (ContextSnapshotError, OSError, UnicodeError, ValueError) as error:
        raise ContextSnapshotError(
            f"snapshot destination already exists but is not a complete valid winner: {snapshot_id}"
        ) from error
    finally:
        if winner is not None:
            winner.close()
    if _manifest_without_created(existing) != _manifest_without_created(manifest):
        raise ContextSnapshotError(f"snapshot identity collision at existing destination: {snapshot_id}")
    return SnapshotResult(
        snapshot_id=snapshot_id,
        directory=relative_directory,
        role=role,
        files=files,
        manifest=existing,
        boundary_warning=boundary_warning,
    )


def _cleanup_owned_reservation(
    cache: _HeldDirectory,
    name: str,
    identity: tuple[int, int],
    *,
    snapshot_id: str,
    owner_token: str,
) -> None:
    partial: _HeldDirectory | None = None
    try:
        entry = _stat_child(cache, name, "snapshot partial cleanup")
        if _unsafe_reparse(entry) or not stat.S_ISDIR(entry.st_mode):
            return
        if (entry.st_dev, entry.st_ino) != identity:
            return
        partial = _open_child_directory(cache, name, "snapshot partial cleanup")
        if not _partial_owner_matches(partial, snapshot_id, owner_token, allow_missing=True):
            return
        _remove_directory_contents(partial)
        partial.close()
        _rmdir_child(cache, name, identity, "snapshot partial cleanup")
        _fsync_handle(cache)
    except (ContextSnapshotError, FileNotFoundError, OSError):
        # Never broaden failure cleanup into deletion of a changed or unsafe tree.
        return
    finally:
        if partial is not None:
            partial.close()


def _cleanup_recognized_partials(cache: _HeldDirectory, snapshot_id: str) -> None:
    pattern = re.compile(rf"^\.partial-{re.escape(snapshot_id)}-([0-9a-f]{{32}})$")
    for name in _directory_names(cache, "context cache root"):
        match = pattern.fullmatch(name)
        if match is None:
            continue
        partial: _HeldDirectory | None = None
        try:
            info = _stat_child(cache, name, "snapshot partial")
            if _unsafe_reparse(info) or not stat.S_ISDIR(info.st_mode):
                continue
            partial = _open_child_directory(cache, name, "snapshot partial")
            token = match.group(1)
            if not _partial_owner_matches(partial, snapshot_id, token) and not _complete_partial_matches(
                partial, snapshot_id
            ):
                continue
            _remove_directory_contents(partial)
            partial.close()
            _rmdir_child(cache, name, partial.identity, "snapshot partial cleanup")
            _fsync_handle(cache)
        except (ContextSnapshotError, OSError):
            continue
        finally:
            if partial is not None:
                partial.close()


def _partial_owner_matches(
    partial: _HeldDirectory,
    snapshot_id: str,
    owner_token: str,
    *,
    allow_missing: bool = False,
) -> bool:
    try:
        raw = _read_from_handle(partial, _PARTIAL_OWNER, "snapshot partial owner")
    except FileNotFoundError:
        return allow_missing
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return False
    return payload == {
        "kind": _PARTIAL_OWNER_KIND,
        "snapshot_id": snapshot_id,
        "token": owner_token,
    }


def _complete_partial_matches(partial: _HeldDirectory, snapshot_id: str) -> bool:
    """Recognize a crash-ready partial after its transient owner marker was removed."""

    try:
        manifest = _load_snapshot_manifest(partial, snapshot_id)
        _validate_snapshot_files(partial, manifest)
    except (ContextSnapshotError, OSError, UnicodeError, ValueError):
        return False
    return True


def _rename_no_replace(cache: _HeldDirectory, source: str, destination: str) -> None:
    cache.revalidate("context cache publication root")
    if _is_windows():
        os.rename(cache.path / source, cache.path / destination)
        cache.revalidate("context cache publication root")
        return
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is not None:
        result = renameat2(
            cache.descriptor,
            os.fsencode(source),
            cache.descriptor,
            os.fsencode(destination),
            1,
        )
    else:
        renameatx_np = getattr(libc, "renameatx_np", None)
        if renameatx_np is None:
            raise ContextSnapshotError("atomic no-replace snapshot publication is unavailable")
        result = renameatx_np(
            cache.descriptor,
            os.fsencode(source),
            cache.descriptor,
            os.fsencode(destination),
            0x00000004,
        )
    if result == 0:
        cache.revalidate("context cache publication root")
        return
    error = ctypes.get_errno()
    if error in {errno.EEXIST, errno.ENOTEMPTY}:
        raise FileExistsError(cache.path / destination)
    raise OSError(error, os.strerror(error), cache.path / destination)


def _load_snapshot_manifest(directory: _HeldDirectory, directory_name: str) -> dict[str, object]:
    directory.revalidate("snapshot directory")
    if _SNAPSHOT_ID.fullmatch(directory_name) is None:
        raise ContextSnapshotError("snapshot directory has an invalid identifier")
    data = _read_from_handle(directory, "manifest.json", "snapshot manifest")
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
    if payload["snapshot_id"] != directory_name:
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
    for key in ("required", "suggested", "unresolved", "warnings"):
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
    if expected_id != directory_name:
        raise ContextSnapshotError("snapshot manifest content does not match its stable identifier")
    return payload


def _validate_snapshot_files(
    directory: _HeldDirectory,
    manifest: dict[str, object],
    *,
    allow_owner: bool = False,
) -> None:
    _validate_cleanup_tree(directory, manifest, allow_owner=allow_owner)
    sources = manifest["sources"]
    assert isinstance(sources, list)
    for source in sources:
        assert isinstance(source, dict)
        snapshot_path = source["snapshot_path"]
        assert isinstance(snapshot_path, str)
        data = _read_from_handle(directory, snapshot_path, "derived snapshot file")
        if _exact_hash(data) != source["snapshot_exact_hash"]:
            raise ContextSnapshotError(f"derived snapshot file hash mismatch: {snapshot_path}")


def _validate_cleanup_tree(
    directory: _HeldDirectory,
    manifest: dict[str, object],
    *,
    allow_owner: bool = False,
) -> None:
    expected_files = {"manifest.json"}
    if allow_owner:
        expected_files.add(_PARTIAL_OWNER)
    sources = manifest["sources"]
    assert isinstance(sources, list)
    expected_files.update(str(source["snapshot_path"]) for source in sources if isinstance(source, dict))
    expected_directories: set[str] = set()
    for relative in expected_files:
        parent = PurePosixPath(relative).parent
        while parent.as_posix() != ".":
            expected_directories.add(parent.as_posix())
            parent = parent.parent
    actual_files, actual_directories = _directory_inventory(directory)
    if actual_files != expected_files or actual_directories != expected_directories:
        raise ContextSnapshotError("snapshot tree contains missing or unknown files or directories")


def _remove_directory_contents(directory: _HeldDirectory) -> None:
    """Remove a validated tree, checking every child identity before mutation."""

    for name in reversed(_directory_names(directory, "snapshot cleanup directory")):
        info = _stat_child(directory, name, "snapshot cleanup directory")
        identity = (info.st_dev, info.st_ino)
        if _unsafe_reparse(info):
            raise ContextSnapshotError(f"snapshot cleanup refuses link or reparse point: {name}")
        if stat.S_ISDIR(info.st_mode):
            child = _open_child_directory(directory, name, "snapshot cleanup child")
            try:
                _remove_directory_contents(child)
                child.revalidate("snapshot cleanup child")
            finally:
                child.close()
            _rmdir_child(directory, name, identity, "snapshot cleanup child")
        elif stat.S_ISREG(info.st_mode):
            _unlink_child(directory, name, identity, "snapshot cleanup file")
        else:
            raise ContextSnapshotError(f"snapshot cleanup refuses unknown entry: {name}")
        directory.revalidate("snapshot cleanup directory")


def _directory_inventory(directory: _HeldDirectory) -> tuple[set[str], set[str]]:
    files: set[str] = set()
    directories: set[str] = set()

    def visit(handle: _HeldDirectory, prefix: PurePosixPath) -> None:
        for name in _directory_names(handle, "snapshot tree"):
            info = _stat_child(handle, name, "snapshot tree")
            relative = (prefix / name).as_posix()
            if _unsafe_reparse(info):
                raise ContextSnapshotError(f"unsafe link in snapshot tree: {relative}")
            if stat.S_ISDIR(info.st_mode):
                directories.add(relative)
                child = _open_child_directory(handle, name, "snapshot tree child")
                try:
                    visit(child, prefix / name)
                finally:
                    child.close()
            elif stat.S_ISREG(info.st_mode):
                files.add(relative)
            else:
                raise ContextSnapshotError(f"unsafe entry in snapshot tree: {relative}")
        handle.revalidate("snapshot tree")

    visit(directory, PurePosixPath())
    return files, directories


def _unsafe_reparse(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(info.st_mode) or bool(attributes & reparse)


def _is_windows() -> bool:
    return os.name == "nt"


def _hold_directory_no_follow(directory: Path, label: str) -> _HeldDirectory:
    """Open every path component and retain its identity for the operation."""

    absolute = Path(os.path.abspath(directory))
    anchor = Path(absolute.anchor)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    secure_dirfd = bool(
        getattr(os, "O_DIRECTORY", 0)
        and getattr(os, "O_NOFOLLOW", 0)
        and os.open in os.supports_dir_fd
        and os.stat in os.supports_dir_fd
        and os.stat in os.supports_follow_symlinks
    )
    if not secure_dirfd:
        identities: list[tuple[Path, tuple[int, int]]] = []
        current = anchor
        anchor_entry = anchor.lstat()
        if _unsafe_reparse(anchor_entry) or not stat.S_ISDIR(anchor_entry.st_mode):
            raise ContextSnapshotError(f"unsafe {label} anchor")
        identities.append((anchor, (anchor_entry.st_dev, anchor_entry.st_ino)))
        for component in absolute.relative_to(anchor).parts:
            current /= component
            try:
                entry = current.lstat()
            except OSError as error:
                raise ContextSnapshotError(f"unsafe or missing {label} component") from error
            if _unsafe_reparse(entry) or not stat.S_ISDIR(entry.st_mode):
                raise ContextSnapshotError(f"unsafe {label} component without no-follow support")
            identities.append((current, (entry.st_dev, entry.st_ino)))
        descriptor = -1 if _is_windows() else os.open(absolute, os.O_RDONLY)
        try:
            if descriptor >= 0:
                opened = os.fstat(descriptor)
                if not stat.S_ISDIR(opened.st_mode):
                    raise ContextSnapshotError(f"unsafe {label}: not an ordinary directory")
                opened_identity = (opened.st_dev, opened.st_ino)
            else:
                opened_identity = identities[-1][1]
            if opened_identity != identities[-1][1]:
                raise ContextSnapshotError(f"unsafe {label}: directory changed during fallback open")
            for path, expected_identity in identities:
                entry = path.lstat()
                if _unsafe_reparse(entry) or (entry.st_dev, entry.st_ino) != expected_identity:
                    raise ContextSnapshotError(f"unsafe {label}: ancestor changed during validation")
            return _HeldDirectory(
                absolute,
                descriptor,
                opened_identity,
                tuple(identities),
                False,
            )
        except BaseException:
            if descriptor >= 0:
                os.close(descriptor)
            raise

    descriptor = os.open(anchor, flags)
    try:
        for component in absolute.relative_to(anchor).parts:
            entry = os.stat(component, dir_fd=descriptor, follow_symlinks=False)
            if _unsafe_reparse(entry) or not stat.S_ISDIR(entry.st_mode):
                raise ContextSnapshotError(f"unsafe {label} component")
            child = os.open(component, flags, dir_fd=descriptor)
            opened = os.fstat(child)
            if (opened.st_dev, opened.st_ino) != (entry.st_dev, entry.st_ino):
                os.close(child)
                raise ContextSnapshotError(f"unsafe {label}: ancestor changed during validation")
            os.close(descriptor)
            descriptor = child
        opened = os.fstat(descriptor)
        return _HeldDirectory(
            absolute,
            descriptor,
            (opened.st_dev, opened.st_ino),
            (),
            True,
        )
    except BaseException:
        os.close(descriptor)
        raise


def _open_child_directory(parent: _HeldDirectory, name: str, label: str) -> _HeldDirectory:
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise ContextSnapshotError(f"unsafe {label} name")
    parent.revalidate(f"{label} parent")
    child_path = parent.path / name
    if parent.descriptor_relative:
        before = os.stat(name, dir_fd=parent.descriptor, follow_symlinks=False)
        if _unsafe_reparse(before) or not stat.S_ISDIR(before.st_mode):
            raise ContextSnapshotError(f"unsafe {label}")
        descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent.descriptor,
        )
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            os.close(descriptor)
            raise ContextSnapshotError(f"unsafe {label}: child changed during open")
        return _HeldDirectory(
            child_path,
            descriptor,
            (opened.st_dev, opened.st_ino),
            (),
            True,
        )
    before = child_path.lstat()
    if _unsafe_reparse(before) or not stat.S_ISDIR(before.st_mode):
        raise ContextSnapshotError(f"unsafe {label}")
    child = _hold_directory_no_follow(child_path, label)
    try:
        if child.identity != (before.st_dev, before.st_ino):
            raise ContextSnapshotError(f"unsafe {label}: child changed during open")
        parent.revalidate(f"{label} parent")
        return child
    except BaseException:
        child.close()
        raise


def _directory_names(handle: _HeldDirectory, label: str) -> list[str]:
    handle.revalidate(label)
    if handle.descriptor_relative:
        try:
            names = sorted(os.listdir(handle.descriptor))
        except (TypeError, NotImplementedError) as error:
            raise ContextSnapshotError(f"descriptor-relative {label} enumeration is unavailable") from error
    else:
        names = sorted(os.listdir(handle.path))
        handle.revalidate(label)
    return names


def _read_from_handle(
    handle: _HeldDirectory,
    relative: str,
    label: str,
    *,
    reject_nested_projects: bool = False,
) -> bytes:
    parts = PurePosixPath(relative).parts
    if not parts or ".." in parts or PurePosixPath(relative).is_absolute():
        raise ContextSnapshotError(f"unsafe relative {label} path")
    current = handle
    owned: list[_HeldDirectory] = []
    descriptor = -1
    try:
        for component in parts[:-1]:
            child = _open_child_directory(current, component, label)
            owned.append(child)
            current = child
            if reject_nested_projects:
                try:
                    if current.descriptor_relative:
                        nested = os.stat(
                            "project.md",
                            dir_fd=current.descriptor,
                            follow_symlinks=False,
                        )
                    else:
                        nested = (current.path / "project.md").lstat()
                        current.revalidate(label)
                except FileNotFoundError:
                    pass
                else:
                    if not _unsafe_reparse(nested) and stat.S_ISREG(nested.st_mode):
                        raise ContextSnapshotError(
                            f"snapshot source crosses nested project boundary: {relative}"
                        )
        current.revalidate(label)
        if current.descriptor_relative:
            before = os.stat(parts[-1], dir_fd=current.descriptor, follow_symlinks=False)
            if _unsafe_reparse(before) or not stat.S_ISREG(before.st_mode):
                raise ContextSnapshotError(f"unsafe {label} file: {relative}")
            descriptor = os.open(
                parts[-1],
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=current.descriptor,
            )
        else:
            path = current.path / parts[-1]
            before = path.lstat()
            if _unsafe_reparse(before) or not stat.S_ISREG(before.st_mode):
                raise ContextSnapshotError(f"unsafe {label} file: {relative}")
            descriptor = os.open(path, os.O_RDONLY)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ContextSnapshotError(f"unsafe {label}: file changed during open: {relative}")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            data = stream.read()
        current.revalidate(label)
        handle.revalidate(label)
        return data
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        for child in reversed(owned):
            child.close()


def _write_to_handle(handle: _HeldDirectory, relative: str, data: bytes) -> None:
    parts = PurePosixPath(relative).parts
    if not parts or ".." in parts or PurePosixPath(relative).is_absolute():
        raise ContextSnapshotError("derived snapshot path escaped its temporary root")
    current = handle
    owned: list[_HeldDirectory] = []
    descriptor = -1
    try:
        for component in parts[:-1]:
            try:
                child = _open_child_directory(current, component, "temporary snapshot directory")
            except FileNotFoundError:
                current.revalidate("temporary snapshot directory parent")
                if current.descriptor_relative:
                    os.mkdir(component, mode=0o700, dir_fd=current.descriptor)
                else:
                    (current.path / component).mkdir(mode=0o700)
                    current.revalidate("temporary snapshot directory parent")
                child = _open_child_directory(current, component, "temporary snapshot directory")
            owned.append(child)
            current = child
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        current.revalidate("temporary snapshot file parent")
        if current.descriptor_relative:
            descriptor = os.open(parts[-1], flags, 0o600, dir_fd=current.descriptor)
        else:
            target = current.path / parts[-1]
            descriptor = os.open(target, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        current.revalidate("temporary snapshot file parent")
        handle.revalidate("temporary snapshot root")
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        for child in reversed(owned):
            child.close()


def _stat_child(handle: _HeldDirectory, name: str, label: str) -> os.stat_result:
    handle.revalidate(label)
    if handle.descriptor_relative:
        return os.stat(name, dir_fd=handle.descriptor, follow_symlinks=False)
    result = (handle.path / name).lstat()
    handle.revalidate(label)
    return result


def _unlink_child(handle: _HeldDirectory, name: str, expected: tuple[int, int], label: str) -> None:
    before = _stat_child(handle, name, label)
    if _unsafe_reparse(before) or (before.st_dev, before.st_ino) != expected:
        raise ContextSnapshotError(f"unsafe {label}: entry changed before delete")
    if handle.descriptor_relative:
        os.unlink(name, dir_fd=handle.descriptor)
    else:
        (handle.path / name).unlink()
        handle.revalidate(label)


def _rmdir_child(handle: _HeldDirectory, name: str, expected: tuple[int, int], label: str) -> None:
    before = _stat_child(handle, name, label)
    if _unsafe_reparse(before) or not stat.S_ISDIR(before.st_mode):
        raise ContextSnapshotError(f"unsafe {label}: directory became unsafe")
    if (before.st_dev, before.st_ino) != expected:
        raise ContextSnapshotError(f"unsafe {label}: directory changed before delete")
    if handle.descriptor_relative:
        os.rmdir(name, dir_fd=handle.descriptor)
    else:
        (handle.path / name).rmdir()
        handle.revalidate(label)


def _fsync_handle(handle: _HeldDirectory) -> None:
    if handle.descriptor < 0:
        return
    try:
        os.fsync(handle.descriptor)
    except OSError as error:
        unsupported = {
            errno.EACCES,
            errno.EINVAL,
            getattr(errno, "ENOTSUP", errno.EINVAL),
            getattr(errno, "EOPNOTSUPP", errno.EINVAL),
        }
        if error.errno not in unsupported:
            raise


def _sync_handle_tree(handle: _HeldDirectory) -> None:
    for name in _directory_names(handle, "temporary snapshot tree"):
        info = _stat_child(handle, name, "temporary snapshot tree")
        if _unsafe_reparse(info):
            raise ContextSnapshotError("temporary snapshot contains a link or reparse point")
        if stat.S_ISDIR(info.st_mode):
            child = _open_child_directory(handle, name, "temporary snapshot directory")
            try:
                _sync_handle_tree(child)
            finally:
                child.close()
        elif not stat.S_ISREG(info.st_mode):
            raise ContextSnapshotError("temporary snapshot contains an unsafe entry")
    _fsync_handle(handle)


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
    return tuple(link.destination for link in extract_links(text))


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
    *,
    restricted: bool = False,
) -> bool:
    values = list(_metadata_references(document))
    for raw in values:
        try:
            resolved = _resolve_reference(raw, relative, project_relative=True, markdown=False)
        except (UnicodeError, ValueError) as error:
            warnings.add(f"invalid structured reference {raw!r} in {relative}: {error}")
            continue
        if resolved in anchors:
            return True
    body = _remove_hidden(document.body) if restricted else document.body
    return _markdown_points_to(project, relative, body, anchors)


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
            info = current.lstat()
            mode = info.st_mode
        except (FileNotFoundError, NotADirectoryError, OSError):
            return False
        if _unsafe_reparse(info):
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
