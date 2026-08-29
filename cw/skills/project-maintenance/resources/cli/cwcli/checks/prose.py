"""Bilingual prose metrics and mechanical Markdown integrity checks."""

from __future__ import annotations

import os
import re
import stat
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ..findings import Finding
from ..project import Project


UNREADABLE_DOCUMENT = "CW-PROSE-001"
SOURCE_TAG = "CW-PROSE-010"
SOURCE_TAG_POLICY = "CW-PROSE-011"
MARKDOWN_FENCE = "CW-PROSE-020"
EMPTY_DOCUMENT = "CW-PROSE-030"
REPEATED_OPENING = "CW-PROSE-040"
METRICS = "CW-PROSE-090"

_QUOTE_RE = re.compile(r'".+?"|«.+?»|„.+?“|“.+?”')
_FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$")
_TAG_RE = re.compile(r"</?(?:AI|hidden)>")
_INLINE_CODE_RE = re.compile(r"(`+)(.*?)\1")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
_WORD_JOINERS = frozenset(("'", "’", "-", "‐", "‑"))


@dataclass(frozen=True)
class ProseMetrics:
    """Immutable, deterministic counts for one prose document."""

    word_count: int
    paragraph_count: int
    sentence_count: int
    dialogue_ratio: float
    repeated_openings: tuple[tuple[str, int], ...]
    language: str


@dataclass(frozen=True)
class _VisibleDocument:
    lines: tuple[tuple[int, str], ...]
    fence_findings: tuple[tuple[int, str], ...]


def analyze_prose(text: str, *, language: str) -> ProseMetrics:
    """Measure prose with legacy preprocessing and Unicode-aware tokenization."""

    prose_text = _strip_markdown(_strip_frontmatter_and_fences(text))
    word_list = _words(prose_text)
    paragraph_list = _paragraphs(prose_text)
    dense_lines = [line.strip() for line in prose_text.splitlines() if line.strip()]
    sentence_list = _sentences(" ".join(dense_lines))
    dialogue_lines = sum(1 for line in dense_lines if _is_dialogue(line))
    dialogue_ratio = dialogue_lines / len(dense_lines) if dense_lines else 0.0
    repeated = Counter(
        opener
        for paragraph in paragraph_list
        if (opener := _first_word(paragraph)) is not None
    )

    return ProseMetrics(
        word_count=len(word_list),
        paragraph_count=len(paragraph_list),
        sentence_count=len(sentence_list),
        dialogue_ratio=dialogue_ratio,
        repeated_openings=tuple(
            sorted(
                ((opening, count) for opening, count in repeated.items() if count >= 2),
                key=lambda item: (-item[1], item[0]),
            )
        ),
        language=_normalize_language(language, prose_text),
    )


def check_prose(project: Project) -> list[Finding]:
    """Inspect managed Markdown independently without changing the project."""

    configured_language = project.manifest.metadata.get("language")
    language = configured_language if isinstance(configured_language, str) else ""
    findings: list[Finding] = []

    for path in project.iter_managed_markdown():
        relative_id = project.relative_id(path)
        try:
            source = _read_regular(path)
            text = source.decode("utf-8-sig")
        except (OSError, UnicodeError, ValueError) as error:
            findings.append(
                Finding(
                    code=UNREADABLE_DOCUMENT,
                    severity="warning",
                    message=f"managed Markdown cannot be read as a regular UTF-8 file: {error}",
                    path=relative_id,
                    next_action="Preserve the file bytes and repair its path kind or UTF-8 encoding.",
                )
            )
            continue

        visible = _visible_document(text)
        for line_number, message in visible.fence_findings:
            findings.append(
                Finding(
                    code=MARKDOWN_FENCE,
                    severity="warning",
                    message=message,
                    path=relative_id,
                    line=line_number,
                    next_action="Close or repair the Markdown fence without changing its content.",
                )
            )
        findings.extend(_tag_findings(relative_id, visible.lines))
        findings.extend(_tag_policy_findings(relative_id, visible.lines))

        if not _is_prose_path(relative_id):
            continue

        metrics = analyze_prose(text, language=language)
        if metrics.word_count == 0:
            findings.append(
                Finding(
                    code=EMPTY_DOCUMENT,
                    severity="warning",
                    message="prose document contains no words outside frontmatter and code fences",
                    path=relative_id,
                    next_action="Confirm that this prose document is intentionally empty or add its content.",
                )
            )
        for opening, count in metrics.repeated_openings:
            findings.append(
                Finding(
                    code=REPEATED_OPENING,
                    severity="info",
                    message=f"paragraph opening '{opening}' occurs {count} times",
                    path=relative_id,
                    line=_opening_line(visible.lines, opening),
                    next_action="Review the repeated structural signal only if it matters for this passage.",
                )
            )
        findings.append(
            Finding(
                code=METRICS,
                severity="info",
                message=(
                    f"words={metrics.word_count}; paragraphs={metrics.paragraph_count}; "
                    f"sentences={metrics.sentence_count}; dialogue-ratio={metrics.dialogue_ratio:.3f}; "
                    f"language={metrics.language}"
                ),
                path=relative_id,
                next_action="Use these counts as mechanical context, not as a literary conclusion.",
            )
        )

    return sorted(findings, key=_finding_key)


def _visible_document(text: str) -> _VisibleDocument:
    numbered_lines = list(enumerate(text.splitlines(), start=1))
    body_start = _frontmatter_end(numbered_lines)
    visible: list[tuple[int, str]] = []
    fence_findings: list[tuple[int, str]] = []
    fence_character: str | None = None
    fence_length = 0
    fence_line = 0

    for line_number, line in numbered_lines[body_start:]:
        match = _FENCE_RE.match(line)
        if fence_character is None:
            if match is not None:
                marker = match.group(1)
                fence_character = marker[0]
                fence_length = len(marker)
                fence_line = line_number
                visible.append((line_number, ""))
            else:
                visible.append((line_number, _strip_inline_code(line)))
            continue

        if match is not None:
            marker = match.group(1)
            suffix = match.group(2).strip()
            if marker[0] == fence_character and len(marker) >= fence_length and not suffix:
                fence_character = None
                fence_length = 0
                fence_line = 0
        visible.append((line_number, ""))

    if fence_character is not None:
        fence_findings.append((fence_line, "Markdown code fence is not closed"))

    return _VisibleDocument(
        lines=tuple(visible),
        fence_findings=tuple(fence_findings),
    )


def _frontmatter_end(lines: list[tuple[int, str]]) -> int:
    if not lines or lines[0][1] != "---":
        return 0
    for index, (_, line) in enumerate(lines[1:], start=1):
        if line == "---":
            return index + 1
    return 0


def _tag_findings(relative_id: str, lines: tuple[tuple[int, str], ...]) -> list[Finding]:
    stack: list[tuple[str, int]] = []
    findings: list[Finding] = []
    for line_number, line in lines:
        for match in _TAG_RE.finditer(line):
            token = match.group(0)
            name = "AI" if "AI" in token else "hidden"
            if not token.startswith("</"):
                stack.append((name, line_number))
                continue
            if not stack:
                findings.append(_tag_finding(relative_id, line_number, f"closing <{name}> tag has no opener"))
                continue
            if stack[-1][0] == name:
                stack.pop()
                continue
            open_name, _ = stack[-1]
            findings.append(
                _tag_finding(
                    relative_id,
                    line_number,
                    f"closing <{name}> tag crosses an open <{open_name}> tag",
                )
            )
            matching = next(
                (index for index in range(len(stack) - 1, -1, -1) if stack[index][0] == name),
                None,
            )
            if matching is not None:
                del stack[matching:]

    for name, line_number in stack:
        findings.append(_tag_finding(relative_id, line_number, f"opening <{name}> tag is not closed"))
    return findings


def _tag_finding(relative_id: str, line_number: int, message: str) -> Finding:
    return Finding(
        code=SOURCE_TAG,
        severity="warning",
        message=message,
        path=relative_id,
        line=line_number,
        next_action="Balance and properly nest the explicit source tags.",
    )


def _tag_policy_findings(relative_id: str, lines: tuple[tuple[int, str], ...]) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in lines:
        for match in _TAG_RE.finditer(line):
            token = match.group(0)
            if token.startswith("</"):
                continue
            name = "AI" if "AI" in token else "hidden"
            message = _policy_message(relative_id, name)
            if message is not None:
                findings.append(
                    Finding(
                        code=SOURCE_TAG_POLICY,
                        severity="warning",
                        message=message,
                        path=relative_id,
                        line=line_number,
                        next_action="Resolve the source boundary before moving this material between layers.",
                    )
                )
    return findings


def _policy_message(relative_id: str, name: str) -> str | None:
    parts = Path(relative_id).parts
    if parts and parts[0] == "story":
        return f"<{name}> source tags are not allowed in accepted story documents"
    if len(parts) >= 2 and parts[:2] == ("work", "drafts"):
        if name == "AI":
            return "<AI> source tags are not allowed in working draft prose"
        return "<hidden> source tags require resolution before draft acceptance"
    if parts and parts[0] == "kb" and name == "AI":
        return "<AI> source tags are not allowed in durable KB documents"
    return None


def _strip_frontmatter_and_fences(text: str) -> str:
    """Preserve the standalone analyzer's preprocessing semantics exactly."""

    lines = text.splitlines()
    start = 0
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                start = index + 1
                break

    cleaned: list[str] = []
    in_fence = False
    for line in lines[start:]:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            cleaned.append(line)
    return "\n".join(cleaned)


def _strip_markdown(text: str) -> str:
    """Preserve the standalone analyzer's limited Markdown stripping."""

    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    return text


def _strip_inline_code(line: str) -> str:
    return _INLINE_CODE_RE.sub("", line)


def _words(text: str) -> list[str]:
    words: list[str] = []
    current: list[str] = []
    for index, character in enumerate(text):
        if _is_letter(character):
            current.append(character)
            continue
        if _is_mark(character) and current:
            current.append(character)
            continue
        if (
            character in _WORD_JOINERS
            and current
            and index + 1 < len(text)
            and _is_letter(text[index + 1])
        ):
            current.append(character)
            continue
        if current:
            words.append(_identity("".join(current)))
            current = []
    if current:
        words.append(_identity("".join(current)))
    return words


def _paragraphs(text: str) -> list[str]:
    return [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if _words(chunk)]


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(text) if part.strip()]


def _first_word(text: str) -> str | None:
    word_list = _words(text)
    return word_list[0] if word_list else None


def _is_dialogue(line: str) -> bool:
    return bool(_QUOTE_RE.search(line)) or line.lstrip().startswith("—")


def _normalize_language(language: str, text: str) -> str:
    normalized = language.strip().replace("_", "-").casefold()
    if normalized == "ru" or normalized.startswith("ru-"):
        return "ru"
    if normalized == "en" or normalized.startswith("en-"):
        return "en"
    return "ru" if any(_is_cyrillic_letter(character) for character in text) else "en"


def _opening_line(lines: tuple[tuple[int, str], ...], opening: str) -> int | None:
    for line_number, line in lines:
        if _first_word(_strip_markdown(line)) == opening:
            return line_number
    return None


def _is_prose_path(relative_id: str) -> bool:
    path = Path(relative_id)
    if path.name == "_index.md" or path.suffix.casefold() != ".md":
        return False
    parent = path.parent.as_posix()
    return parent in {"story/chapters", "work/drafts", "kb/samples"}


def _read_regular(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("not a regular file")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            return stream.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _identity(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _is_letter(character: str) -> bool:
    return unicodedata.category(character).startswith("L")


def _is_mark(character: str) -> bool:
    return unicodedata.category(character).startswith("M")


def _is_cyrillic_letter(character: str) -> bool:
    return _is_letter(character) and "CYRILLIC" in unicodedata.name(character, "")


def _finding_key(item: Finding) -> tuple[str, str, int, str]:
    return (item.path or "", item.code, item.line or 0, item.message)


__all__ = [
    "EMPTY_DOCUMENT",
    "MARKDOWN_FENCE",
    "METRICS",
    "ProseMetrics",
    "REPEATED_OPENING",
    "SOURCE_TAG",
    "SOURCE_TAG_POLICY",
    "UNREADABLE_DOCUMENT",
    "analyze_prose",
    "check_prose",
]
