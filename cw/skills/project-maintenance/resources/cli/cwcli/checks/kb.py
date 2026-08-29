"""Explicit knowledge-base provenance checks."""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit

from ..documents import DocumentError, parse_document
from ..findings import Finding, Severity
from ..project import Project
from ..schema import allowed_document_kind


UNREADABLE_PAGE = "CW-KB-001"
MISSING_SOURCES = "CW-KB-010"
WORK_ONLY_SOURCE = "CW-KB-020"
INVALID_SOURCE = "CW-KB-030"


def check_kb(project: Project) -> list[Finding]:
    """Check durable provenance declared by KB pages, never inferred from prose."""

    findings: list[Finding] = []
    for path in project.iter_managed_markdown():
        relative_id = project.relative_id(path)
        if allowed_document_kind(relative_id) not in {"kb-content", "continuity-scene"}:
            continue
        try:
            document = parse_document(_read_regular(path))
        except (DocumentError, OSError, UnicodeError) as error:
            findings.append(_finding(UNREADABLE_PAGE, "warning", f"KB provenance cannot be read safely: {error}", relative_id, "Preserve the page body and repair its UTF-8 frontmatter before relying on provenance.", line=_error_line(error)))
            continue

        rendered_sources = document.metadata.get("sources")
        if rendered_sources is None or rendered_sources == "":
            findings.append(_finding(MISSING_SOURCES, "warning", "KB page declares no explicit provenance sources", relative_id, "Confirm provenance with the author, then record only explicit sources."))
            continue
        sources = rendered_sources if isinstance(rendered_sources, list) else [rendered_sources]
        if not all(isinstance(source, str) and source.strip() for source in sources):
            findings.append(_finding(INVALID_SOURCE, "warning", "sources must contain non-empty explicit source strings", relative_id, "Repair sources as a flat list of explicit paths, URLs, or decision transaction IDs."))
            continue

        kinds = [_source_kind(project, source.strip()) for source in sources]
        for source, kind in zip(sources, kinds):
            if kind == "invalid":
                findings.append(_finding(INVALID_SOURCE, "warning", f"source is not a live durable reference: {source}", relative_id, "Correct the source or confirm and record a live story, KB, URL, or decision reference."))
        if kinds and all(kind == "work" for kind in kinds):
            findings.append(_finding(WORK_ONLY_SOURCE, "warning", "work artifacts are the only provenance and cannot alone establish durable knowledge", relative_id, "Ask the author to confirm this knowledge, then cite accepted story, live KB, an external source, or decision:<transaction-id>."))
    return sorted(findings, key=lambda item: (item.path or "", item.code, item.message))


def _source_kind(project: Project, source: str) -> str:
    parsed = urlsplit(source)
    if parsed.scheme.casefold() in {"http", "https"} and parsed.netloc:
        return "durable"
    if source.startswith("decision:"):
        transaction_id = source.removeprefix("decision:")
        if not transaction_id or Path(transaction_id).name != transaction_id:
            return "invalid"
        manifest = project.root / ".creative-writing" / "transactions" / transaction_id / "manifest.json"
        if _contains_symlink(project.root, manifest):
            return "invalid"
        try:
            payload = json.loads(_read_regular(manifest).decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return "invalid"
        return "durable" if isinstance(payload, dict) and payload.get("state") == "committed" else "invalid"
    if "\\" in source or source.startswith("/") or ".." in Path(source).parts:
        return "invalid"
    target = project.root / source
    if _path_kind(target) != "file" or _contains_symlink(project.root, target) or _crosses_nested_project(project, target):
        return "invalid"
    if source.startswith("work/"):
        return "work"
    if source.startswith("story/"):
        return "durable"
    if source.startswith("kb/"):
        try:
            referenced = parse_document(_read_regular(target))
        except (DocumentError, OSError, UnicodeError):
            return "invalid"
        return "invalid" if referenced.metadata.get("status") == "archived" else "durable"
    return "invalid"


def _path_kind(path: Path) -> str:
    try:
        mode = path.lstat().st_mode
    except (FileNotFoundError, NotADirectoryError):
        return "missing"
    return "file" if stat.S_ISREG(mode) else "other"


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


__all__ = ["INVALID_SOURCE", "MISSING_SOURCES", "UNREADABLE_PAGE", "WORK_ONLY_SOURCE", "check_kb"]
