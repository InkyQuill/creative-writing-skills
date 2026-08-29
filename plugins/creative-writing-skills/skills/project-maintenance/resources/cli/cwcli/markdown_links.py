"""Small Markdown-aware inline link extractor with source-line evidence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarkdownLink:
    destination: str
    line: int
    image: bool = False


def extract_links(text: str) -> tuple[MarkdownLink, ...]:
    """Extract inline links/images while ignoring non-prose Markdown regions."""

    lines = text.splitlines(keepends=True)
    result: list[MarkdownLink] = []
    in_fence: tuple[str, int] | None = None
    in_comment = False
    frontmatter = bool(lines and lines[0].strip() == "---")
    for line_number, original in enumerate(lines, 1):
        stripped = original.lstrip(" \t")
        if frontmatter:
            if line_number > 1 and original.strip() == "---":
                frontmatter = False
            continue
        indent = len(original) - len(stripped)
        marker = _fence_marker(stripped)
        if in_fence is not None:
            if marker is not None and marker[0] == in_fence[0] and marker[1] >= in_fence[1]:
                in_fence = None
            continue
        if marker is not None and indent <= 3:
            in_fence = marker
            continue
        if original.startswith("    ") or original.startswith("\t"):
            continue

        visible, in_comment = _mask_comments_and_code(original, in_comment)
        result.extend(_line_links(visible, line_number))
    return tuple(result)


def _fence_marker(stripped: str) -> tuple[str, int] | None:
    if not stripped or stripped[0] not in "`~":
        return None
    character = stripped[0]
    length = len(stripped) - len(stripped.lstrip(character))
    return (character, length) if length >= 3 else None


def _mask_comments_and_code(line: str, in_comment: bool) -> tuple[str, bool]:
    characters = list(line)
    index = 0
    code_ticks = 0
    while index < len(line):
        if in_comment:
            closing = line.find("-->", index)
            end = len(line) if closing < 0 else closing + 3
            characters[index:end] = " " * (end - index)
            if closing < 0:
                return "".join(characters), True
            in_comment = False
            index = end
            continue
        if code_ticks:
            marker = "`" * code_ticks
            closing = line.find(marker, index)
            end = len(line) if closing < 0 else closing + code_ticks
            characters[index:end] = " " * (end - index)
            code_ticks = 0
            index = end
            continue
        if line.startswith("<!--", index):
            in_comment = True
            continue
        if line[index] == "`":
            code_ticks = len(line[index:]) - len(line[index:].lstrip("`"))
            characters[index : index + code_ticks] = " " * code_ticks
            index += code_ticks
            continue
        index += 1
    return "".join(characters), in_comment


def _line_links(line: str, line_number: int) -> list[MarkdownLink]:
    links: list[MarkdownLink] = []
    cursor = 0
    while cursor < len(line):
        opening = line.find("[", cursor)
        if opening < 0:
            break
        image = opening > 0 and line[opening - 1] == "!"
        closing = _balanced_close(line, opening, "[", "]")
        if closing < 0 or closing + 1 >= len(line) or line[closing + 1] != "(":
            cursor = opening + 1
            continue
        end = _destination_close(line, closing + 2)
        if end < 0:
            cursor = closing + 1
            continue
        links.append(MarkdownLink(line[closing + 2 : end].strip(), line_number, image))
        cursor = end + 1
    return links


def _balanced_close(text: str, start: int, opening: str, closing: str) -> int:
    depth = 0
    escaped = False
    for index in range(start, len(text)):
        character = text[index]
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == opening:
            depth += 1
        elif character == closing:
            depth -= 1
            if depth == 0:
                return index
    return -1


def _destination_close(text: str, start: int) -> int:
    depth = 1
    angle = False
    quote: str | None = None
    escaped = False
    for index in range(start, len(text)):
        character = text[index]
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if angle:
            if character == ">":
                angle = False
            continue
        if quote is not None:
            if character == quote:
                quote = None
            continue
        if index == start and character == "<":
            angle = True
        elif character in {'"', "'"} and index > start and text[index - 1].isspace():
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


__all__ = ["MarkdownLink", "extract_links"]
