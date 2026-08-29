"""Small Markdown-aware inline link extractor with source-line evidence."""

from __future__ import annotations

from dataclasses import dataclass


MarkdownFence = tuple[str, int, str]


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
        if frontmatter:
            if line_number > 1 and original.strip() == "---":
                frontmatter = False
            continue
        marker = markdown_fence_marker(original)
        if in_fence is not None:
            if marker is not None and closes_markdown_fence(marker, in_fence):
                in_fence = None
            continue
        if marker is not None:
            in_fence = marker[:2]
            continue
        if original.startswith("    ") or original.startswith("\t"):
            continue

        visible, in_comment = _mask_comments_and_code(original, in_comment)
        result.extend(_line_links(visible, line_number))
    return tuple(result)


def markdown_fence_marker(line: str) -> MarkdownFence | None:
    """Return a fence marker for a line indented by at most three columns."""

    stripped = line.lstrip(" \t")
    if len(line) - len(stripped) > 3:
        return None
    if not stripped or stripped[0] not in "`~":
        return None
    character = stripped[0]
    length = len(stripped) - len(stripped.lstrip(character))
    return (character, length, stripped[length:]) if length >= 3 else None


def closes_markdown_fence(marker: MarkdownFence, opener: tuple[str, int]) -> bool:
    """Apply the shared conservative closing-fence rule."""

    character, length, suffix = marker
    return character == opener[0] and length >= opener[1] and not suffix.strip()


def _mask_comments_and_code(line: str, in_comment: bool) -> tuple[str, bool]:
    characters = list(line)
    index = 0
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
        if line.startswith("<!--", index):
            in_comment = True
            continue
        if line[index] == "`" and not _is_escaped(line, index):
            code_ticks = len(line[index:]) - len(line[index:].lstrip("`"))
            closing = _matching_backtick_run(line, index + code_ticks, code_ticks)
            if closing < 0:
                index += code_ticks
                continue
            end = closing + code_ticks
            characters[index:end] = " " * (end - index)
            index = end
            continue
        index += 1
    return "".join(characters), in_comment


def _matching_backtick_run(line: str, start: int, length: int) -> int:
    cursor = start
    while cursor < len(line):
        opening = line.find("`", cursor)
        if opening < 0:
            return -1
        run_length = len(line[opening:]) - len(line[opening:].lstrip("`"))
        if run_length == length:
            return opening
        cursor = opening + run_length
    return -1


def _line_links(line: str, line_number: int) -> list[MarkdownLink]:
    links: list[MarkdownLink] = []
    cursor = 0
    while cursor < len(line):
        opening = line.find("[", cursor)
        if opening < 0:
            break
        if _is_escaped(line, opening):
            cursor = opening + 1
            continue
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


def _is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


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


__all__ = [
    "MarkdownFence",
    "MarkdownLink",
    "closes_markdown_fence",
    "extract_links",
    "markdown_fence_marker",
]
