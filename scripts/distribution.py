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
_FENCE_RE = re.compile(r"^(?:`{3,}|~{3,})")
_CODEX_SKILL_RE = re.compile(r"\$([a-z][a-z0-9-]*)")
_CLAUDE_SKILL_RE = re.compile(
    r"(?<![A-Za-z0-9_.</%-])(?<![>}\]])/([a-z][a-z0-9-]*)(?![A-Za-z0-9/-])"
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


def map_outside_fences(text: str, transform: Callable[[str], str]) -> str:
    result: list[str] = []
    segment: list[str] = []
    fenced = False
    for line in text.splitlines(keepends=True):
        if _FENCE_RE.match(line):
            if not fenced:
                result.append(transform("".join(segment)))
                segment = []
            else:
                result.extend(segment)
                segment = []
            result.append(line)
            fenced = not fenced
        else:
            segment.append(line)
    if fenced:
        result.extend(segment)
    else:
        result.append(transform("".join(segment)))
    return "".join(result)


def extract_skill_references(text: str, sigil: str) -> set[str]:
    if sigil == "$":
        pattern = _CODEX_SKILL_RE
    elif sigil == "/":
        pattern = _CLAUDE_SKILL_RE
    else:
        raise ValueError(f"Unsupported skill reference sigil: {sigil}")

    references: set[str] = set()

    def collect(segment: str) -> str:
        references.update(match.group(1) for match in pattern.finditer(segment))
        return segment

    map_outside_fences(text, collect)
    return references
