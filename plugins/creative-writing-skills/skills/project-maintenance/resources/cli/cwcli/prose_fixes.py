"""Read-only plans for conservative Russian manuscript typography repairs."""

from __future__ import annotations

import re
from pathlib import Path

from .checks.prose import _visible_document
from .checks.prose_typography import _BREAKABLE_SINGLE_RE
from .project import Project
from .transactions import Change, TransactionPlan


class ProseFixError(ValueError):
    pass


_DASH_SPACE_RE = re.compile(r"(?<=\S) — (?=\S)")


def plan_safe_typography_fix(project: Project, relative_id: str) -> TransactionPlan:
    """Fix spacing only in visible prose lines of one managed manuscript file."""

    path = Path(relative_id)
    if path.parent.as_posix() not in {"story/chapters", "story/side-stories", "work/drafts"} or path.suffix.casefold() != ".md":
        raise ProseFixError("typography fix requires a chapter, side story, or draft Markdown file")
    source_path = project.resolve(relative_id, for_write=True)
    if not source_path.is_file() or source_path.is_symlink():
        raise ProseFixError("typography fix target must be an existing regular file")
    source = source_path.read_bytes()
    try:
        decoded = source.decode("utf-8-sig")
    except UnicodeError as error:
        raise ProseFixError("typography fix target is not UTF-8") from error
    if str(project.manifest.metadata.get("language", "")).split("-")[0].lower() != "ru":
        raise ProseFixError("automatic typography spacing is available only for Russian projects")

    visible_lines = {number for number, visible in _visible_document(decoded).lines if visible}
    lines = decoded.splitlines(keepends=True)
    changed = False
    for number, line in enumerate(lines, 1):
        if number not in visible_lines or "`" in line or "](" in line or "<!--" in line:
            continue
        repaired = _BREAKABLE_SINGLE_RE.sub(lambda match: match.group().replace(" ", "\u00a0"), line)
        repaired = _DASH_SPACE_RE.sub("\u00a0— ", repaired)
        if repaired != line:
            lines[number - 1] = repaired
            changed = True

    after = (b"\xef\xbb\xbf" if source.startswith(b"\xef\xbb\xbf") else b"") + "".join(lines).encode("utf-8")
    return TransactionPlan(
        command=("fix-prose-typography", relative_id),
        changes=(Change(relative_id, source, after),) if changed else (),
        metadata={"undoable": True},
    )
