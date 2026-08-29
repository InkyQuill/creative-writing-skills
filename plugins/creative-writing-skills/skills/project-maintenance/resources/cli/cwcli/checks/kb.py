"""Explicit knowledge-base provenance checks."""

from __future__ import annotations

import os
import re
import stat
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit

from ..documents import DocumentError, parse_document
from ..findings import Finding, Severity
from ..markdown_links import extract_links
from ..markdown_tables import parse_tables, table_header_lines
from ..project import Project
from ..schema import allowed_document_kind
from .journal import is_committed_decision


UNREADABLE_PAGE = "CW-KB-001"
MISSING_SOURCES = "CW-KB-010"
WORK_ONLY_SOURCE = "CW-KB-020"
INVALID_SOURCE = "CW-KB-030"
VOCABULARY_COLLISION = "CW-KB-040"
ARCHIVED_REFERENCE = "CW-KB-050"


def check_kb(project: Project) -> list[Finding]:
    """Check durable provenance declared by KB pages, never inferred from prose."""

    findings: list[Finding] = []
    for path in project.iter_managed_markdown():
        relative_id = project.relative_id(path)
        if allowed_document_kind(relative_id) not in {"kb-content", "continuity-scene", "vocabulary"}:
            continue
        try:
            raw = _read_regular(path)
            document = parse_document(raw)
            text = raw.decode("utf-8-sig")
        except (DocumentError, OSError, UnicodeError) as error:
            findings.append(_finding(UNREADABLE_PAGE, "warning", f"KB provenance cannot be read safely: {error}", relative_id, "Preserve the page body and repair its UTF-8 frontmatter before relying on provenance.", line=_error_line(error)))
            continue

        if document.metadata.get("status") != "archived":
            findings.extend(_archived_body_references(project, relative_id, text))

        rendered_sources = document.metadata.get("sources")
        if rendered_sources is None or rendered_sources == "":
            findings.append(_finding(MISSING_SOURCES, "warning", "KB page declares no explicit provenance sources", relative_id, "Confirm provenance with the author, then record only explicit sources."))
            if relative_id == "kb/vocab.md":
                findings.extend(_vocabulary_collisions(relative_id, text))
            continue
        sources = rendered_sources if isinstance(rendered_sources, list) else [rendered_sources]
        if not all(isinstance(source, str) and source.strip() for source in sources):
            findings.append(_finding(INVALID_SOURCE, "warning", "sources must contain non-empty explicit source strings", relative_id, "Repair sources as a flat list of explicit paths, URLs, or decision transaction IDs."))
            continue

        kinds = [_source_kind(project, source.strip()) for source in sources]
        for source, kind in zip(sources, kinds):
            if kind == "invalid":
                findings.append(_finding(INVALID_SOURCE, "warning", f"source is not a live durable reference: {source}", relative_id, "Correct the source or confirm and record a live story, KB, URL, or decision reference."))
        if "work" in kinds and "durable" not in kinds:
            findings.append(_finding(WORK_ONLY_SOURCE, "warning", "work artifacts are the only provenance and cannot alone establish durable knowledge", relative_id, "Ask the author to confirm this knowledge, then cite accepted story, live KB, an external source, or decision:<transaction-id>."))
        if relative_id == "kb/vocab.md":
            findings.extend(_vocabulary_collisions(relative_id, text))
    return sorted(findings, key=lambda item: (item.path or "", item.code, item.message))


def _vocabulary_collisions(relative_id: str, body: str) -> list[Finding]:
    occurrences: dict[str, list[tuple[str, int]]] = {}
    for header_line, table in zip(table_header_lines(body), parse_tables(body)):
        headers = tuple(_identity(value) for value in table.headers)
        column = next((headers.index(name) for name in ("term", "canonical", "name") if name in headers), None)
        if column is None or len(headers) != len(set(headers)):
            continue
        for row in table.rows:
            rendered = row.cells[column].strip()
            if rendered:
                occurrences.setdefault(_identity(rendered), []).append((rendered, row.line))
    findings: list[Finding] = []
    for identity, rows in sorted(occurrences.items()):
        if len(rows) < 2:
            continue
        evidence = ", ".join(f"{value!r} at line {line}" for value, line in rows)
        findings.append(_finding(VOCABULARY_COLLISION, "warning", f"vocabulary term has a portable identity collision: {evidence}", relative_id, "Choose one canonical spelling and preserve alternatives explicitly as aliases.", line=rows[1][1]))
    return findings


def _archived_body_references(project: Project, source: str, body: str) -> list[Finding]:
    findings: list[Finding] = []
    for link in extract_links(body):
        try:
            raw = _body_destination(link.destination)
            parsed = urlsplit(raw)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            decoded = _strict_unquote(parsed.path)
            target = (Path(source).parent / decoded)
            parts: list[str] = []
            for part in target.parts:
                if part in {"", "."}:
                    continue
                if part == "..":
                    if not parts:
                        raise ValueError("body reference escapes project")
                    parts.pop()
                else:
                    parts.append(part)
            relative = Path(*parts).as_posix()
            if not relative.startswith("kb/") or _source_kind(project, relative) != "invalid":
                continue
            path = project.root / relative
            if _path_kind(path) != "file" or _contains_symlink(project.root, path) or _crosses_nested_project(project, path):
                continue
            target_document = parse_document(_read_regular(path))
            if target_document.metadata.get("status") == "archived":
                findings.append(_finding(ARCHIVED_REFERENCE, "warning", f"live KB page links to archived record: {relative}", source, "Update the link to a live record or explicitly restore the archived record before relying on it.", line=link.line))
        except (DocumentError, OSError, UnicodeError, ValueError):
            continue
    return findings


def _body_destination(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<"):
        end = value.find(">", 1)
        if end < 0:
            raise ValueError("unterminated angle destination")
        return value[1:end]
    match = re.match(r"^(.*?)(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?$", value)
    if match is None or not match.group(1).strip():
        raise ValueError("empty destination")
    return match.group(1).strip()


def _identity(value: str) -> str:
    return unicodedata.normalize("NFC", value.strip()).casefold()


def _source_kind(project: Project, source: str) -> str:
    try:
        parsed = urlsplit(source)
        if parsed.scheme.casefold() in {"http", "https"} and parsed.netloc:
            return "durable"
        if source.startswith("decision:"):
            return "durable" if is_committed_decision(project, source.removeprefix("decision:")) else "invalid"
        if parsed.scheme or parsed.netloc:
            return "invalid"

        if "\x00" in source:
            return "invalid"
        decoded_path = _strict_unquote(parsed.path)
        if "\x00" in decoded_path:
            return "invalid"
        if "\\" in decoded_path or decoded_path.startswith("/") or ".." in Path(decoded_path).parts:
            return "invalid"
        target = project.root / decoded_path
        if _path_kind(target) != "file" or _contains_symlink(project.root, target) or _crosses_nested_project(project, target):
            return "invalid"
        relative_id = target.relative_to(project.root).as_posix()
        if relative_id.startswith("work/"):
            return "work" if allowed_document_kind(relative_id) == "work-artifact" else "invalid"
        if relative_id.startswith("story/"):
            if allowed_document_kind(relative_id) != "chapter":
                return "invalid"
            referenced = parse_document(_read_regular(target))
            return "invalid" if referenced.metadata.get("status") == "archived" else "durable"
        if relative_id.startswith("kb/"):
            referenced = parse_document(_read_regular(target))
            if allowed_document_kind(relative_id) not in {"kb-content", "continuity-scene", "continuity-record", "vocabulary"}:
                return "invalid"
            return "invalid" if referenced.metadata.get("status") == "archived" else "durable"
        return "invalid"
    except (DocumentError, OSError, TypeError, UnicodeError, ValueError):
        return "invalid"


def _path_kind(path: Path) -> str:
    try:
        mode = path.lstat().st_mode
    except (FileNotFoundError, NotADirectoryError):
        return "missing"
    return "file" if stat.S_ISREG(mode) else "other"


def _strict_unquote(value: str) -> str:
    if re.search(r"%(?![0-9A-Fa-f]{2})", value):
        raise ValueError("path contains an invalid percent escape")
    return unquote(value, errors="strict")


def _contains_symlink(root: Path, target: Path) -> bool:
    current = root
    for part in target.relative_to(root).parts:
        current /= part
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                return True
        except (FileNotFoundError, NotADirectoryError):
            return False
    return False


def _crosses_nested_project(project: Project, target: Path) -> bool:
    current = project.root
    for part in target.relative_to(project.root).parts[:-1]:
        current /= part
        manifest = current / "project.md"
        if _path_kind(manifest) == "file":
            return True
    return False


def _read_regular(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("not a regular file")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            return stream.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _error_line(error: BaseException) -> int | None:
    match = re.match(r"line (\d+):", str(error))
    return int(match.group(1)) if match else None


def _finding(code: str, severity: Severity, message: str, path: str, next_action: str, *, line: int | None = None) -> Finding:
    return Finding(code=code, severity=severity, message=message, path=path, line=line, next_action=next_action)


__all__ = ["ARCHIVED_REFERENCE", "INVALID_SOURCE", "MISSING_SOURCES", "UNREADABLE_PAGE", "VOCABULARY_COLLISION", "WORK_ONLY_SOURCE", "check_kb"]
