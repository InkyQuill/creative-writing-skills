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
MARKDOWN_FENCE = "CW-PROSE-020"
EMPTY_DOCUMENT = "CW-PROSE-030"
REPEATED_OPENING = "CW-PROSE-040"
METRICS = "CW-PROSE-090"

_WORD_RE = re.compile(r"[A-Za-zÀ-ɏЀ-ԯ]+(?:['’][A-Za-zÀ-ɏЀ-ԯ]+)?")
_QUOTE_RE = re.compile(r'".+?"|«.+?»|„.+?“|“.+?”')
_FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$")
_TAG_RE = re.compile(r"</?(?:AI|hidden)>")
_INLINE_CODE_RE = re.compile(r"(`+)(.*?)\1")
_MARKDOWN_LINK_RE = re.compile(r"!?\[([^\]]+)\]\([^)]+\)")
_CYRILLIC_RE = re.compile(r"[Ѐ-ԯ]")


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
    text: str
    lines: tuple[tuple[int, str], ...]
    fence_findings: tuple[tuple[int, str], ...]


def analyze_prose(text: str, *, language: str) -> ProseMetrics:
    """Measure prose using Latin/Cyrillic-aware, standard-library tokenization."""

    visible = _visible_document(text)
    prose_text = _strip_markdown(visible.text)
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
    """Inspect each managed prose file independently without changing the project."""

    configured_language = project.manifest.metadata.get("language")
    language = configured_language if isinstance(configured_language, str) else ""
    findings: list[Finding] = []

    for path in project.iter_managed_markdown():
        relative_id = project.relative_id(path)
        if not _is_prose_path(relative_id):
            continue
        try:
            source = _read_regular(path)
            text = source.decode("utf-8-sig")
        except (OSError, UnicodeError, ValueError) as error:
            findings.append(
                Finding(
                    code=UNREADABLE_DOCUMENT,
                    severity="warning",
                    message=f"prose document cannot be read as a regular UTF-8 file: {error}",
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
        text="\n".join(line for _, line in visible),
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


def _strip_markdown(text: str) -> str:
    text = re.sub(r"^#{1,6}[ \t]+", "", text, flags=re.MULTILINE)
    text = _MARKDOWN_LINK_RE.sub(r"\1", text)
    text = re.sub(r"<\/?(?:AI|hidden)>", "", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    return text


def _strip_inline_code(line: str) -> str:
    return _INLINE_CODE_RE.sub("", line)


def _words(text: str) -> list[str]:
    return [_identity(match.group(0)) for match in _WORD_RE.finditer(text)]


def _paragraphs(text: str) -> list[str]:
    return [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if _words(chunk)]


def _sentences(text: str) -> list[str]:
    return [
        match.group(0).strip()
        for match in re.finditer(r"[^.!?…]+(?:[.!?…]+[\"'»”’)]*|$)", text)
        if _words(match.group(0))
    ]


def _first_word(text: str) -> str | None:
    match = _WORD_RE.search(text)
    return _identity(match.group(0)) if match is not None else None


def _is_dialogue(line: str) -> bool:
    return bool(_QUOTE_RE.search(line)) or line.lstrip().startswith("—")


def _normalize_language(language: str, text: str) -> str:
    normalized = language.strip().replace("_", "-").casefold()
    if normalized == "ru" or normalized.startswith("ru-"):
        return "ru"
    if normalized == "en" or normalized.startswith("en-"):
        return "en"
    return "ru" if _CYRILLIC_RE.search(text) else "en"


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


def _finding_key(item: Finding) -> tuple[str, str, int, str]:
    return (item.path or "", item.code, item.line or 0, item.message)


__all__ = [
    "EMPTY_DOCUMENT",
    "MARKDOWN_FENCE",
    "METRICS",
    "ProseMetrics",
    "REPEATED_OPENING",
    "SOURCE_TAG",
    "UNREADABLE_DOCUMENT",
    "analyze_prose",
    "check_prose",
]
