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

    conflicts = _conflict_groups(base_lines, draft_edits, current_edits)

    if conflicts:
        return RebaseResult(None, conflicts)

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


def _conflict_groups(
    base: tuple[str, ...],
    draft_edits: tuple[TextEdit, ...],
    current_edits: tuple[TextEdit, ...],
) -> tuple[RebaseConflict, ...]:
    """Return connected competing regions with complete variant fragments."""

    edges = {
        (draft_index, current_index)
        for draft_index, draft_edit in enumerate(draft_edits)
        for current_index, current_edit in enumerate(current_edits)
        if draft_edit != current_edit and _conflict(draft_edit, current_edit)
    }
    conflicts: list[RebaseConflict] = []
    while edges:
        pending_drafts = {next(iter(edges))[0]}
        group_drafts: set[int] = set()
        group_currents: set[int] = set()
        while pending_drafts:
            draft_index = pending_drafts.pop()
            if draft_index in group_drafts:
                continue
            group_drafts.add(draft_index)
            currents = {right for left, right in edges if left == draft_index}
            for current_index in currents - group_currents:
                group_currents.add(current_index)
                pending_drafts.update(
                    left for left, right in edges if right == current_index
                )
        edges = {
            edge
            for edge in edges
            if edge[0] not in group_drafts and edge[1] not in group_currents
        }
        selected_draft = tuple(draft_edits[index] for index in sorted(group_drafts))
        selected_current = tuple(
            current_edits[index] for index in sorted(group_currents)
        )
        start = min(edit.start for edit in (*selected_draft, *selected_current))
        end = max(edit.end for edit in (*selected_draft, *selected_current))
        selected_draft = tuple(
            edit for edit in draft_edits if _edit_in_region(edit, start, end)
        )
        selected_current = tuple(
            edit for edit in current_edits if _edit_in_region(edit, start, end)
        )
        conflicts.append(
            RebaseConflict(
                start=start,
                end=end,
                base=base[start:end],
                draft=_apply_fragment(base, selected_draft, start, end),
                current=_apply_fragment(base, selected_current, start, end),
            )
        )
    return tuple(sorted(conflicts, key=lambda item: (item.start, item.end)))


def _edit_in_region(edit: TextEdit, start: int, end: int) -> bool:
    if edit.start == edit.end:
        return start <= edit.start <= end
    return edit.start < end and edit.end > start


def _apply_fragment(
    base: tuple[str, ...], edits: tuple[TextEdit, ...], start: int, end: int
) -> tuple[str, ...]:
    rendered: list[str] = []
    cursor = start
    for edit in sorted(edits):
        rendered.extend(base[cursor : edit.start])
        rendered.extend(edit.replacement)
        cursor = edit.end
    rendered.extend(base[cursor:end])
    return tuple(rendered)


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
