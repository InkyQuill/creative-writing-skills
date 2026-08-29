"""Explicit Markdown link and generated-index validation."""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from ..findings import Finding, Severity
from ..indexes import plan_reindex
from ..project import Project
from ..schema import GENERATED_INDEX_FILES, allowed_document_kind


MISSING_TARGET = "CW-LINK-010"
EXTERNAL_REFERENCE = "CW-LINK-011"
TARGET_CLASS = "CW-LINK-020"
ORPHAN_PAGE = "CW-LINK-030"
INDEX_DRIFT = "CW-LINK-040"
UNREADABLE_SOURCE = "CW-LINK-090"

_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")
_EXTERNAL_SCHEMES = frozenset({"http", "https", "mailto"})


def check_links(project: Project) -> list[Finding]:
    """Validate only explicit Markdown links without crossing project boundaries."""

    findings: list[Finding] = []
    inbound: set[str] = set()
    authored: set[str] = set()
    sources = [project.root / "project.md", *project.iter_managed_markdown()]
    for source in sources:
        relative_source = project.relative_id(source)
        if _is_authored_page(relative_source):
            authored.add(relative_source)
        try:
            text = _read_regular(source).decode("utf-8-sig")
        except (OSError, UnicodeError) as error:
            findings.append(_finding(UNREADABLE_SOURCE, "warning", f"cannot inspect explicit links: {error}", relative_source, None, "Preserve the bytes and repair the file path kind or UTF-8 encoding."))
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            for match in _LINK_RE.finditer(line):
                rendered = _link_destination(match.group(2))
                if rendered is None:
                    continue
                destination, _fragment = rendered
                parsed = urlsplit(destination)
                if parsed.scheme.casefold() in _EXTERNAL_SCHEMES or destination.startswith("//"):
                    continue
                if parsed.scheme or parsed.netloc:
                    findings.append(_finding(EXTERNAL_REFERENCE, "info", "link uses an external or unsupported URI scheme and is not followed", relative_source, line_number, "Review this external reference manually if it is required as context."))
                    continue

                reference = unquote(parsed.path)
                if not reference:
                    continue
                target = Path(os.path.normpath(source.parent / reference))
                boundary = _boundary_kind(project, target)
                if boundary is not None:
                    findings.append(_finding(EXTERNAL_REFERENCE, "info", f"link is outside the nearest project boundary ({boundary}) and is not followed", relative_source, line_number, "Review the external reference manually; keep managed context inside this project."))
                    continue

                relative_target = target.relative_to(project.root).as_posix()
                actual_kind = _path_kind(target)
                if actual_kind == "missing":
                    findings.append(_finding(MISSING_TARGET, "warning", f"local link target does not exist: {relative_target}", relative_source, line_number, "Create the intended target or correct the explicit Markdown link."))
                    continue
                if actual_kind == "symlink":
                    findings.append(_finding(EXTERNAL_REFERENCE, "info", "local link target is a filesystem link and is not followed", relative_source, line_number, "Review the linked location manually; use a regular in-project target for managed context."))
                    continue
                expected = "directory" if reference.endswith("/") else "file"
                if actual_kind != expected:
                    findings.append(_finding(TARGET_CLASS, "warning", f"link syntax expects a {expected}, but target is a {actual_kind}", relative_source, line_number, "Correct the link destination or point it at the intended target class."))
                    continue
                if actual_kind == "file":
                    inbound.add(relative_target)

    for relative_id in sorted(authored - inbound):
        findings.append(_finding(ORPHAN_PAGE, "info", "authored managed page has no inbound explicit Markdown link", relative_id, None, "Add an explicit link from a relevant authored page if this artifact should be discoverable."))

    try:
        reindex = plan_reindex(project, skip_unparseable=True)
    except (OSError, UnicodeError, ValueError) as error:
        findings.append(_finding(INDEX_DRIFT, "warning", f"derived index drift could not be calculated safely: {error}", None, None, "Repair unreadable managed paths, then preview cw reindex."))
    else:
        for change in reindex.changes:
            if change.path in GENERATED_INDEX_FILES:
                findings.append(_finding(INDEX_DRIFT, "warning", "generated registry differs from authored managed documents", change.path, None, "Preview cw reindex, review the diff, then apply it explicitly."))
    return sorted(findings, key=_finding_key)


def _link_destination(raw: str) -> tuple[str, str] | None:
    value = raw.strip()
    if not value:
        return None
    if value.startswith("<") and ">" in value:
        value = value[1:value.index(">")]
    elif " " in value:
        value = value.split(None, 1)[0]
    destination, marker, fragment = value.partition("#")
    return destination, fragment if marker else ""


def _boundary_kind(project: Project, target: Path) -> str | None:
    try:
        relative = target.relative_to(project.root)
    except ValueError:
        return "parent or sibling project reference"
    current = project.root
    for part in relative.parts:
        current /= part
        if _path_kind(current) == "symlink":
            return "filesystem link"
        manifest = current / "project.md"
        if _path_kind(manifest) == "file":
            return "nested project reference"
    return None


def _path_kind(path: Path) -> str:
    try:
        mode = path.lstat().st_mode
    except (FileNotFoundError, NotADirectoryError):
        return "missing"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    return "other filesystem entry"


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


def _is_authored_page(relative_id: str) -> bool:
    return allowed_document_kind(relative_id) in {
        "chapter",
        "work-artifact",
        "kb-content",
        "continuity-scene",
    }


def _finding(code: str, severity: Severity, message: str, path: str | None, line: int | None, next_action: str) -> Finding:
    return Finding(code=code, severity=severity, message=message, path=path, line=line, next_action=next_action)


def _finding_key(item: Finding) -> tuple[str, str, int, str]:
    return (item.path or "", item.code, item.line or 0, item.message)


__all__ = ["EXTERNAL_REFERENCE", "INDEX_DRIFT", "MISSING_TARGET", "ORPHAN_PAGE", "TARGET_CLASS", "check_links"]
