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
_FENCE_RE = re.compile(
    r"^ {0,3}(?P<marker>`{3,}|~{3,})(?P<tail>[^\r\n]*)(?:\r?\n)?$"
)
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
            metadata[key] = textwrap.dedent("".join(block)).rstrip("\r\n")
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
    if value.startswith('"') and value.endswith('"'):
        return json.loads(value)
    return value


def skill_directories(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        return {}
    return {
        path.name: path
        for path in sorted(root.iterdir())
        if path.is_dir() and (path / "SKILL.md").is_file()
    }


def iter_fenced_lines(text: str):
    marker_character: str | None = None
    marker_length = 0
    for line in text.splitlines(keepends=True):
        match = _FENCE_RE.match(line)
        if marker_character is None:
            if match is None:
                yield line, False
                continue
            marker = match.group("marker")
            marker_character = marker[0]
            marker_length = len(marker)
            yield line, True
            continue

        yield line, True
        if match is None:
            continue
        marker = match.group("marker")
        if (
            marker[0] == marker_character
            and len(marker) >= marker_length
            and not match.group("tail").strip()
        ):
            marker_character = None
            marker_length = 0


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
