"""Conservative line-based three-way merge for working drafts."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True, order=True)
class TextEdit:
    """One variant edit expressed exclusively in base-line coordinates."""

    start: int
    end: int
    replacement: tuple[str, ...]


@dataclass(frozen=True)
class RebaseConflict:
    """Competing fragments for one overlapping pair of variant edits."""

    start: int
    end: int
    base: tuple[str, ...]
    draft: tuple[str, ...]
    current: tuple[str, ...]


@dataclass(frozen=True)
class RebaseResult:
    """A complete merge result, or every conflict found during its scan."""

    text: str | None
    conflicts: tuple[RebaseConflict, ...]


def three_way_rebase(base: str, draft: str, current: str) -> RebaseResult:
    """Merge non-overlapping line edits without applying cross-variant offsets."""

    if not all(isinstance(value, str) for value in (base, draft, current)):
        raise TypeError("rebase inputs must be strings")

    if _logical_text(current) == _logical_text(base):
        return RebaseResult(draft, ())
    if _logical_text(draft) == _logical_text(base):
        return RebaseResult(current, ())

    output_newline = _newline_style(draft, base, current)
    base_lines = tuple(_logical_text(base).splitlines(keepends=True))
    draft_lines = tuple(_logical_text(draft).splitlines(keepends=True))
    current_lines = tuple(_logical_text(current).splitlines(keepends=True))
    draft_edits = _extract_edits(base_lines, draft_lines)
    current_edits = _extract_edits(base_lines, current_lines)

    conflicts: list[RebaseConflict] = []
    seen_conflicts: set[RebaseConflict] = set()
    for draft_edit in draft_edits:
        for current_edit in current_edits:
            if draft_edit == current_edit or not _conflict(draft_edit, current_edit):
                continue
            start = min(draft_edit.start, current_edit.start)
            end = max(draft_edit.end, current_edit.end)
            conflict = RebaseConflict(
                start=start,
                end=end,
                base=base_lines[start:end],
                draft=_fragment(base_lines, draft_edit, start, end),
                current=_fragment(base_lines, current_edit, start, end),
            )
            if conflict not in seen_conflicts:
                conflicts.append(conflict)
                seen_conflicts.add(conflict)

    if conflicts:
        return RebaseResult(None, tuple(conflicts))

    edits = sorted(set((*draft_edits, *current_edits)))
    merged: list[str] = []
    cursor = 0
    for edit in edits:
        if edit.start < cursor:
            raise RuntimeError("non-conflicting rebase edits unexpectedly overlap")
        merged.extend(base_lines[cursor : edit.start])
        merged.extend(edit.replacement)
        cursor = edit.end
    merged.extend(base_lines[cursor:])
    return RebaseResult(_with_newline("".join(merged), output_newline), ())


def _extract_edits(
    base: tuple[str, ...], variant: tuple[str, ...]
) -> tuple[TextEdit, ...]:
    matcher = SequenceMatcher(a=base, b=variant, autojunk=False)
    return tuple(
        TextEdit(base_start, base_end, variant[variant_start:variant_end])
        for operation, base_start, base_end, variant_start, variant_end in matcher.get_opcodes()
        if operation != "equal"
    )


def _conflict(left: TextEdit, right: TextEdit) -> bool:
    left_insert = left.start == left.end
    right_insert = right.start == right.end
    if left_insert and right_insert:
        return left.start == right.start and left.replacement != right.replacement
    if left_insert:
        return right.start < left.start < right.end
    if right_insert:
        return left.start < right.start < left.end
    return max(left.start, right.start) < min(left.end, right.end)


def _fragment(
    base: tuple[str, ...], edit: TextEdit, start: int, end: int
) -> tuple[str, ...]:
    return base[start : edit.start] + edit.replacement + base[edit.end : end]


def _logical_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _newline_style(*texts: str) -> str:
    for text in texts:
        crlf = text.find("\r\n")
        lf = text.find("\n")
        cr = text.find("\r")
        candidates = [position for position in (crlf, lf, cr) if position >= 0]
        if not candidates:
            continue
        first = min(candidates)
        if crlf == first:
            return "\r\n"
        if lf == first:
            return "\n"
        return "\r"
    return "\n"


def _with_newline(text: str, newline: str) -> str:
    return text if newline == "\n" else text.replace("\n", newline)


__all__ = [
    "RebaseConflict",
    "RebaseResult",
    "TextEdit",
    "three_way_rebase",
]
