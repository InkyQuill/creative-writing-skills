"""Conservative parsing for simple GitHub-style Markdown tables."""

from __future__ import annotations

import re
from dataclasses import dataclass


_DELIMITER = re.compile(r"^:?-{3,}:?$")


@dataclass(frozen=True)
class TableRow:
    """A parsed table row with one-based source-line evidence."""

    cells: tuple[str, ...]
    line: int


@dataclass(frozen=True)
class MarkdownTable:
    """A table whose delimiter made its header unambiguous."""

    headers: tuple[str, ...]
    rows: tuple[TableRow, ...]


def parse_tables(text: str) -> tuple[MarkdownTable, ...]:
    """Parse only header/delimiter tables, without interpreting column roles."""

    lines = text.splitlines()
    tables: list[MarkdownTable] = []
    index = 0
    while index + 1 < len(lines):
        header = _split_row(lines[index])
        delimiter = _split_row(lines[index + 1])
        if (
            header is None
            or delimiter is None
            or len(header) == 0
            or len(header) != len(delimiter)
            or not all(_DELIMITER.fullmatch(cell) for cell in delimiter)
        ):
            index += 1
            continue

        rows: list[TableRow] = []
        cursor = index + 2
        while cursor < len(lines):
            cells = _split_row(lines[cursor])
            if cells is None or len(cells) != len(header):
                break
            rows.append(TableRow(cells=cells, line=cursor + 1))
            cursor += 1
        tables.append(MarkdownTable(headers=header, rows=tuple(rows)))
        index = max(cursor, index + 2)
    return tuple(tables)


def _split_row(line: str) -> tuple[str, ...] | None:
    stripped = line.strip()
    if not stripped or not _has_unescaped_pipe(stripped):
        return None

    parts: list[str] = []
    start = 0
    for index, character in enumerate(stripped):
        if character == "|" and not _is_escaped(stripped, index):
            parts.append(stripped[start:index])
            start = index + 1
    parts.append(stripped[start:])

    if stripped.startswith("|"):
        parts.pop(0)
    if stripped.endswith("|") and not _is_escaped(stripped, len(stripped) - 1):
        parts.pop()
    return tuple(part.strip() for part in parts)


def _has_unescaped_pipe(text: str) -> bool:
    return any(character == "|" and not _is_escaped(text, index) for index, character in enumerate(text))


def _is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


__all__ = ["MarkdownTable", "TableRow", "parse_tables"]
