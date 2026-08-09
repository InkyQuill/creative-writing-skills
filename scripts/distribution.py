import json
import re
import textwrap
from pathlib import Path
from typing import Callable, cast


REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "creative-writing-skills"
SKILLS_ROOT = PLUGIN_ROOT / "skills"
CW_ROOT = REPO_ROOT / "cw"

_FRONTMATTER_KEYS = {
    "name",
    "description",
    "disable-model-invocation",
    "argument-hint",
}
_LIST_MARKER_RE = re.compile(r"[-+*]|\d{1,9}[.)]")
_CODEX_SKILL_RE = re.compile(r"\$([a-z][a-z0-9-]*)")
_CLAUDE_SKILL_RE = re.compile(
    r"(?<![A-Za-z0-9_.</%-])/([a-z][a-z0-9-]*)(?![A-Za-z0-9/-])"
)
_URL_RE = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s<>]+", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
_MARKDOWN_LINK_OPEN_RE = re.compile(r"\]\(")
_MARKDOWN_REFERENCE_DESTINATION_RE = re.compile(
    r"^[ \t]{0,3}\[[^\]\n]+\]:[ \t]*(?:\r?\n[ \t]+)?"
    r"(?P<destination><[^>\n]+>|\S+)",
    re.MULTILINE,
)
_ROOT_FILE_PATH_RE = re.compile(
    r"^/[A-Za-z0-9._-]+\.[A-Za-z0-9_-]+(?:$|[`'\"),;:!?])"
)


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(dict[str, object], value)


def split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text

    metadata: dict[str, object] = {}
    index = 1
    while index < len(lines):
        line = lines[index]
        if line.strip() == "---":
            return metadata, "".join(lines[index + 1:])
        if not line.strip():
            index += 1
            continue
        if ":" not in line:
            raise ValueError(f"Invalid frontmatter line: {line.rstrip()}")

        key, raw_value = line.rstrip("\r\n").split(":", 1)
        if key not in _FRONTMATTER_KEYS or key in metadata:
            raise ValueError(f"Unsupported frontmatter key: {key}")
        value = raw_value.strip()
        if value in {"|", ">"}:
            if key != "description":
                raise ValueError(f"Block scalar is only supported for description: {key}")
            block: list[str] = []
            index += 1
            while index < len(lines):
                candidate = lines[index]
                if candidate.strip() == "---" or (candidate and not candidate[0].isspace()):
                    break
                block.append(candidate)
                index += 1
            metadata[key] = _parse_block_scalar(value, textwrap.dedent("".join(block)))
            continue
        if not value:
            raise ValueError(f"Missing frontmatter value: {key}")
        metadata[key] = _parse_scalar(value)
        index += 1

    raise ValueError("Unterminated frontmatter")


def _parse_scalar(value: str) -> object:
    if value == "true":
        return True
    if value == "false":
        return False
    if value.startswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid double-quoted scalar: {value}") from error
    if value.startswith("'"):
        if not value.endswith("'") or len(value) < 2:
            raise ValueError("Unterminated single-quoted scalar")
        inner = value[1:-1]
        decoded: list[str] = []
        index = 0
        while index < len(inner):
            if inner[index] != "'":
                decoded.append(inner[index])
                index += 1
                continue
            if index + 1 == len(inner) or inner[index + 1] != "'":
                raise ValueError(
                    "Single quotes inside a single-quoted scalar must be doubled"
                )
            decoded.append("'")
            index += 2
        return "".join(decoded)
    return value


def _parse_block_scalar(style: str, value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines()
    if not lines:
        return ""
    if style == "|":
        return "\n".join(lines).rstrip("\n") + "\n"

    folded: list[str] = []
    for index, line in enumerate(lines):
        folded.append(line)
        if index == len(lines) - 1:
            continue
        following = lines[index + 1]
        if not line:
            separator = "\n" if not following else ""
        elif not following:
            separator = "\n"
        elif line[:1].isspace() or following[:1].isspace():
            separator = "\n"
        else:
            separator = " "
        folded.append(separator)
    return "".join(folded).rstrip("\n") + "\n"


def skill_directories(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        return {}
    return {
        path.name: path
        for path in sorted(root.iterdir())
        if path.is_dir() and (path / "SKILL.md").is_file()
    }


def _advance_column(column: int, character: str) -> int:
    if character == "\t":
        return column + 4 - (column % 4)
    return column + 1


def _column_at(line: str, index: int, initial_column: int = 0) -> int:
    column = initial_column
    for character in line[:index]:
        column = _advance_column(column, character)
    return column


def _consume_block_quote(line: str, index: int) -> int | None:
    end = index
    while end < len(line) and end - index < 3 and line[end] == " ":
        end += 1
    if end == len(line) or line[end] != ">":
        return None
    end += 1
    if end < len(line) and line[end] in " \t":
        end += 1
    return end


def _consume_list_item(
    line: str,
    index: int,
    initial_column: int = 0,
) -> tuple[int, int] | None:
    end = index
    while end < len(line) and end - index < 3 and line[end] == " ":
        end += 1
    marker = _LIST_MARKER_RE.match(line, end)
    if marker is None:
        return None
    end = marker.end()
    marker_column = _column_at(line, end, initial_column)
    if end == len(line):
        return end, marker_column + 1
    if line[end] not in " \t":
        return None
    first_whitespace_end = end + 1
    while end < len(line) and line[end] in " \t":
        end += 1
    if _column_at(line, end, initial_column) - marker_column > 4:
        end = first_whitespace_end
    return end, _column_at(line, end, initial_column)


def _opening_fence_line(
    line: str,
    initial_column: int = 0,
) -> tuple[str, tuple[tuple[str, int], ...]]:
    index = 0
    containers: list[tuple[str, int]] = []
    while True:
        block_quote = _consume_block_quote(line, index)
        if block_quote is not None:
            containers.append(("block-quote", 0))
            index = block_quote
            continue
        list_item = _consume_list_item(line, index, initial_column)
        if list_item is not None:
            index, content_column = list_item
            containers.append(("list-item", content_column))
            continue
        return line[index:], tuple(containers)


def _container_fence_line(
    line: str,
    containers: tuple[tuple[str, int], ...],
) -> tuple[int, int]:
    index = 0
    for matched, (kind, content_column) in enumerate(containers):
        if kind == "block-quote":
            block_quote = _consume_block_quote(line, index)
            if block_quote is None:
                return index, matched
            index = block_quote
            continue
        while _column_at(line, index) < content_column:
            if index == len(line) or line[index] not in " \t":
                return index, matched
            index += 1
        if _column_at(line, index) != content_column:
            return index, matched
    return index, len(containers)


def iter_fenced_lines(text: str):
    fence: tuple[str, int, tuple[tuple[str, int], ...]] | None = None
    pending_containers: tuple[tuple[str, int], ...] = ()
    for line in text.splitlines(keepends=True):
        fence_line = line.rstrip("\r\n")
        opening_containers: tuple[tuple[str, int], ...] | None = None
        opening_content: str | None = None
        if fence is not None:
            marker, length, containers = fence
            index, matched = _container_fence_line(fence_line, containers)
            content = fence_line[index:]
            if matched != len(containers):
                if (
                    not content.strip()
                    and all(kind == "list-item" for kind, _ in containers[matched:])
                ):
                    yield line, True
                    continue
                fence = None
                surviving = containers[:matched]
                opening_content, new_containers = _opening_fence_line(
                    content,
                    _column_at(fence_line, index),
                )
                opening_containers = surviving + new_containers
            else:
                closing = re.fullmatch(
                    r" {0,3}" + re.escape(marker) + rf"{{{length},}}[ \t]*",
                    content,
                )
                yield line, True
                if closing is not None:
                    fence = None
                continue

        if pending_containers:
            index, matched = _container_fence_line(
                fence_line,
                pending_containers,
            )
            content = fence_line[index:]
            if matched == len(pending_containers):
                if not content.strip():
                    yield line, False
                    continue
                opening_content = content
                opening_containers = pending_containers
            else:
                surviving = pending_containers[:matched]
                if (
                    not content.strip()
                    and all(
                        kind == "list-item"
                        for kind, _ in pending_containers[matched:]
                    )
                ):
                    yield line, False
                    continue
                opening_content, new_containers = _opening_fence_line(
                    content,
                    _column_at(fence_line, index),
                )
                opening_containers = surviving + new_containers
            pending_containers = ()

        if opening_content is None or opening_containers is None:
            opening_content, opening_containers = _opening_fence_line(fence_line)
        opening = re.match(r" {0,3}(([`~])\2{2,})(.*)", opening_content)
        if opening is not None and not (
            opening.group(2) == "`" and "`" in opening.group(3)
        ):
            fence = (
                opening.group(2),
                len(opening.group(1)),
                opening_containers,
            )
            yield line, True
            continue
        if (
            not opening_content.strip()
            and opening_containers
            and opening_containers[-1][0] == "list-item"
        ):
            pending_containers = opening_containers
        yield line, False


def map_outside_fences(text: str, transform: Callable[[str], str]) -> str:
    result: list[str] = []
    segment: list[str] = []
    for line, fenced in iter_fenced_lines(text):
        if fenced:
            if segment:
                result.append(transform("".join(segment)))
                segment = []
            result.append(line)
        else:
            segment.append(line)
    if segment:
        result.append(transform("".join(segment)))
    return "".join(result)


def _mask_span(characters: list[str], start: int, end: int) -> None:
    for index in range(start, end):
        if characters[index] not in {"\r", "\n"}:
            characters[index] = " "


def _is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    index -= 1
    while index >= 0 and text[index] == "\\":
        backslashes += 1
        index -= 1
    return backslashes % 2 == 1


def _mask_markdown_link_destinations(text: str, characters: list[str]) -> None:
    for match in _MARKDOWN_LINK_OPEN_RE.finditer(text):
        if _is_escaped(text, match.start()):
            continue
        depth = 1
        index = match.end()
        while index < len(text) and depth:
            if text[index] == "\\":
                index += 2
                continue
            if text[index] == "(":
                depth += 1
            elif text[index] == ")":
                depth -= 1
            index += 1
        if depth == 0:
            _mask_span(characters, match.end(), index - 1)

    for match in _MARKDOWN_REFERENCE_DESTINATION_RE.finditer(text):
        _mask_span(characters, match.start("destination"), match.end("destination"))


def _is_filesystem_path_token(token: str) -> bool:
    core = token.strip("`*_'\"(),;:!?")
    if not core or "</" in core:
        return False
    if core.startswith(("~/", "./", "../")):
        return True
    if core.startswith("/"):
        return "/" in core[1:] or _ROOT_FILE_PATH_RE.match(core) is not None
    return re.search(r"/(?:\{[^/}\s]+\}|\[[^/\]\s]+\])/", core) is not None


def _mask_slash_non_call_contexts(text: str) -> str:
    characters = list(text)
    _mask_markdown_link_destinations(text, characters)
    for pattern in (_URL_RE, _HTML_TAG_RE):
        for match in pattern.finditer(text):
            _mask_span(characters, match.start(), match.end())

    masked = "".join(characters)
    for match in re.finditer(r"\S+", masked):
        if _is_filesystem_path_token(match.group()):
            _mask_span(characters, match.start(), match.end())
    return "".join(characters)


def extract_skill_references(text: str, sigil: str) -> set[str]:
    if sigil == "$":
        pattern = _CODEX_SKILL_RE
    elif sigil == "/":
        pattern = _CLAUDE_SKILL_RE
    else:
        raise ValueError(f"Unsupported skill reference sigil: {sigil}")

    references: set[str] = set()

    def collect(segment: str) -> str:
        searchable = _mask_slash_non_call_contexts(segment) if sigil == "/" else segment
        references.update(match.group(1) for match in pattern.finditer(searchable))
        return segment

    map_outside_fences(text, collect)
    return references
