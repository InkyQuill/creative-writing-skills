"""Deterministic Russian typography findings for cw check prose."""

import re
from dataclasses import dataclass
from typing import Iterable, Tuple

CW_PROSE_100 = "CW-PROSE-100"  # straight double quote
CW_PROSE_101 = "CW-PROSE-101"  # hyphen with whitespace on both sides
CW_PROSE_102 = "CW-PROSE-102"  # literal three-dot ellipsis
CW_PROSE_103 = "CW-PROSE-103"  # breakable space after single-letter word
CW_PROSE_110 = "CW-PROSE-110"  # unseparated run of five or more digits
CW_PROSE_111 = "CW-PROSE-111"  # decimal point between digits
CW_PROSE_112 = "CW-PROSE-112"  # No. / # where № is expected
CW_PROSE_113 = "CW-PROSE-113"  # ordinal suffix like 1ый
CW_PROSE_114 = "CW-PROSE-114"  # closed-up abbreviation т.д.

_EDIT_NEXT_ACTION = (
    "Confirm the project's typography conventions in project.md and apply "
    "the fix through a previewed edit."
)

_STRAIGHT_QUOTE_RE = re.compile(r'"([^"]*)"|"')
_THREE_DOTS_RE = re.compile(r"(?<!\.)\.\.\.(?!\.)")
_SPACED_HYPHEN_RE = re.compile(r"(?<=[\s\u00a0])-(?=[\s\u00a0])")
# A standalone single-letter word followed by an ordinary space.
_BREAKABLE_SINGLE_RE = re.compile(
    r"(?<![А-Яа-яЁёA-Za-z0-9])[вксоуиая] (?=[А-Яа-яЁёA-Za-z0-9«„\u2014])"
)
_LATIN_LETTER = re.compile(r"[A-Za-z]")

_DIGIT_RUN_RE = re.compile(r"(?<!\d)\d{5,}(?!\d)")
_DECIMAL_POINT_RE = re.compile(r"(?<=\d)\.(?=\d)")
_NUMERO_RE = re.compile(r"\bNo\.\s*\d|#(?=\d)")
_ORDINAL_RE = re.compile(r"\d(?:ый|ой|ий|ая|ое|ые)\b")
_ABBREV_RE = re.compile(r"т\.(?:д|п|е|к)\.")


@dataclass(frozen=True)
class TypographyHit:
    line: int
    code: str
    severity: str
    message: str
    next_action: str


def _latin_span(content: str) -> bool:
    if not content:
        return False
    letters = [ch for ch in content if ch.isalpha()]
    return bool(letters) and all(_LATIN_LETTER.match(ch) for ch in letters)


def scan_lines(lines: Iterable[Tuple[int, str]]) -> tuple[TypographyHit, ...]:
    hits = []
    for line_no, text in lines:
        for match in _STRAIGHT_QUOTE_RE.finditer(text):
            content = match.group(1) or ""
            severity = "info" if _latin_span(content) else "warning"
            hits.append(TypographyHit(
                line_no, CW_PROSE_100, severity,
                "Straight double quote; use «» (primary) or „“ (nested).",
                _EDIT_NEXT_ACTION,
            ))
        if _SPACED_HYPHEN_RE.search(text):
            hits.append(TypographyHit(
                line_no, CW_PROSE_101, "warning",
                "Hyphen with whitespace on both sides; use an em dash — "
                "with a non-breaking space before it.",
                _EDIT_NEXT_ACTION,
            ))
        if _THREE_DOTS_RE.search(text):
            hits.append(TypographyHit(
                line_no, CW_PROSE_102, "warning",
                "Literal three-dot sequence; use the ellipsis character ….",
                _EDIT_NEXT_ACTION,
            ))
        if _BREAKABLE_SINGLE_RE.search(text):
            hits.append(TypographyHit(
                line_no, CW_PROSE_103, "warning",
                "Breakable space after a single-letter word; use a "
                "non-breaking space.",
                _EDIT_NEXT_ACTION,
            ))
        if _DIGIT_RUN_RE.search(text):
            hits.append(TypographyHit(
                line_no, CW_PROSE_110, "info",
                "Unseparated digit run; group digits with non-breaking "
                "spaces (1 000 000).",
                _EDIT_NEXT_ACTION,
            ))
        if _DECIMAL_POINT_RE.search(text):
            hits.append(TypographyHit(
                line_no, CW_PROSE_111, "info",
                "Decimal point; Russian convention is a decimal comma (3,14).",
                _EDIT_NEXT_ACTION,
            ))
        for _match in _NUMERO_RE.finditer(text):
            hits.append(TypographyHit(
                line_no, CW_PROSE_112, "info",
                "`No.`/`#`; use `№` with a non-breaking space.",
                _EDIT_NEXT_ACTION,
            ))
        if _ORDINAL_RE.search(text):
            hits.append(TypographyHit(
                line_no, CW_PROSE_113, "info",
                "Ordinal suffix; use the hyphenated form (1-й, 2-я).",
                _EDIT_NEXT_ACTION,
            ))
        for _match in _ABBREV_RE.finditer(text):
            hits.append(TypographyHit(
                line_no, CW_PROSE_114, "info",
                "Closed-up abbreviation; use `т. д.` with a non-breaking "
                "space.",
                _EDIT_NEXT_ACTION,
            ))
    return tuple(hits)


__all__ = [
    "CW_PROSE_100",
    "CW_PROSE_101",
    "CW_PROSE_102",
    "CW_PROSE_103",
    "CW_PROSE_110",
    "CW_PROSE_111",
    "CW_PROSE_112",
    "CW_PROSE_113",
    "CW_PROSE_114",
    "TypographyHit",
    "scan_lines",
]
