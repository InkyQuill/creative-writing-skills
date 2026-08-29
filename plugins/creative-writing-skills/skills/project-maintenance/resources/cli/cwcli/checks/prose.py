"""Capability-based prose metrics and mechanical Markdown integrity checks."""

from __future__ import annotations

import os
import re
import stat
import statistics
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Pattern

from .prose_typography import scan_lines
from ..documents import parse_document
from ..findings import Finding
from ..markdown_links import closes_markdown_fence, markdown_fence_marker
from ..project import Project


UNREADABLE_DOCUMENT = "CW-PROSE-001"
SOURCE_TAG = "CW-PROSE-010"
SOURCE_TAG_POLICY = "CW-PROSE-011"
MARKDOWN_FENCE = "CW-PROSE-020"
EMPTY_DOCUMENT = "CW-PROSE-030"
REPEATED_OPENING = "CW-PROSE-040"
METRICS = "CW-PROSE-090"
WINDOWED_REPETITION = "CW-PROSE-041"

_TAG_RE = re.compile(r"</?(?:AI|hidden)>")
_INLINE_CODE_RE = re.compile(r"(`+)(.*?)\1")
_LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
_WORD_JOINERS = frozenset(("'", "’", "-", "‐", "‑"))
_LANGUAGE_TAG_RE = re.compile(r"^[a-z]{2,8}(?:-[a-z0-9]{1,8})*$", re.ASCII)

UNIVERSAL_METRICS = (
    "word-count",
    "paragraph-count",
    "sentence-count",
    "sentence-length-distribution",
    "repeated-openings",
    "windowed-repetition",
    "markdown-source-integrity",
)
LANGUAGE_SENSITIVE_METRICS = (
    "dialogue-ratio",
    "opener-categories",
    "pronoun-distribution",
)


@dataclass(frozen=True)
class LanguageCapability:
    """Language-specific dictionaries and punctuation conventions."""

    language: str
    pronoun_starts: frozenset[str]
    article_starts: frozenset[str]
    conjunction_starts: frozenset[str]
    pronoun_groups: tuple[tuple[str, frozenset[str]], ...]
    dialogue_quotes: Pattern[str]
    dash_dialogue: bool = False


_ENGLISH_CAPABILITY = LanguageCapability(
    language="en",
    pronoun_starts=frozenset(
        "i me my we our you your he his him she her they their them it its".split()
    ),
    article_starts=frozenset("the a an this that these those".split()),
    conjunction_starts=frozenset(
        "and but or so yet for nor because although though while when if after before since until as once".split()
    ),
    pronoun_groups=(
        ("first-singular", frozenset("i me my mine myself".split())),
        ("first-plural", frozenset("we us our ours ourselves".split())),
        ("second", frozenset("you your yours yourself yourselves".split())),
        ("third-masculine", frozenset("he him his himself".split())),
        ("third-feminine", frozenset("she her hers herself".split())),
        ("third-plural", frozenset("they them their theirs themselves".split())),
        ("third-neuter", frozenset("it its itself".split())),
    ),
    dialogue_quotes=re.compile(r'".+?"|“.+?”'),
)

_RUSSIAN_CAPABILITY = LanguageCapability(
    language="ru",
    pronoun_starts=frozenset(
        "я мы ты вы он она они оно мой моя моё мое наш наша наше твой твоя твоё твое ваш ваша ваше его её ее их".split()
    ),
    article_starts=frozenset(),
    conjunction_starts=frozenset(
        "и но а или да зато однако чтобы когда если хотя пока как что потому".split()
    ),
    pronoun_groups=(
        ("first-singular", frozenset("я меня мне мной мой моя моё мое моего моей моём моем мою моим моими моих".split())),
        ("first-plural", frozenset("мы нас нам нами наш наша наше нашего нашей нашем наши нашим нашими наших".split())),
        ("second", frozenset("ты тебя тебе тобой твой твоя твоё твое твоего твоей твоём твоем твою твоим твоими твоих вы вас вам вами ваш ваша ваше вашего вашей вашем ваши вашим вашими ваших".split())),
        ("third-masculine", frozenset("он его него ему нему им ним".split())),
        ("third-feminine", frozenset("она её ее нее ей ней ею нею".split())),
        ("third-plural", frozenset("они их них им ним ими ними".split())),
        ("third-neuter", frozenset("оно".split())),
    ),
    dialogue_quotes=re.compile(r"«.+?»|„.+?“"),
    dash_dialogue=True,
)

_LANGUAGE_CAPABILITIES = {
    "en": _ENGLISH_CAPABILITY,
    "ru": _RUSSIAN_CAPABILITY,
}


@dataclass(frozen=True)
class ProseMetrics:
    """Immutable, deterministic counts for one prose document."""

    word_count: int
    paragraph_count: int
    sentence_count: int
    dialogue_ratio: float | None
    repeated_openings: tuple[tuple[str, int], ...]
    language: str
    language_capability: str | None
    sentence_lengths: tuple[int, ...]
    sentence_length_mean: float
    sentence_length_median: float
    sentence_length_stdev: float
    opener_categories: tuple[tuple[str, int], ...] | None
    windowed_repetitions: tuple[tuple[str, int, int, int], ...]
    pronoun_distribution: tuple[tuple[str, int], ...] | None
    skipped_metrics: tuple[str, ...]


@dataclass(frozen=True)
class _VisibleDocument:
    lines: tuple[tuple[int, str], ...]
    fence_findings: tuple[tuple[int, str], ...]


def analyze_prose(text: str, *, language: str) -> ProseMetrics:
    """Measure prose with legacy preprocessing and Unicode-aware tokenization."""

    prose_text = _strip_markdown(
        _strip_inline_code(_strip_frontmatter_and_fences(text))
    )
    word_list = _words(prose_text)
    paragraph_list = _paragraphs(prose_text)
    dense_lines = [line.strip() for line in prose_text.splitlines() if line.strip()]
    sentence_list = _sentences(" ".join(dense_lines))
    normalized_language = _normalize_language(language)
    capability = _LANGUAGE_CAPABILITIES.get(normalized_language)
    dialogue_ratio: float | None = None
    if capability is not None:
        dialogue_lines = sum(1 for line in dense_lines if _is_dialogue(line, capability))
        dialogue_ratio = dialogue_lines / len(dense_lines) if dense_lines else 0.0
    repeated = Counter(
        opener
        for paragraph in paragraph_list
        if (opener := _first_word(paragraph)) is not None
    )
    sentence_lengths = tuple(len(_words(sentence)) for sentence in sentence_list if _words(sentence))
    openers = [_first_word(sentence) for sentence in sentence_list]
    word_counts = Counter(word_list)
    categories = (
        Counter(
            _opener_category(opener, capability)
            for opener in openers
            if opener is not None
        )
        if capability is not None
        else None
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
        language=normalized_language,
        language_capability=capability.language if capability is not None else None,
        sentence_lengths=sentence_lengths,
        sentence_length_mean=statistics.fmean(sentence_lengths) if sentence_lengths else 0.0,
        sentence_length_median=float(statistics.median(sentence_lengths)) if sentence_lengths else 0.0,
        sentence_length_stdev=statistics.pstdev(sentence_lengths) if len(sentence_lengths) > 1 else 0.0,
        opener_categories=(
            tuple(
                (name, categories[name])
                for name in ("pronouns", "articles", "conjunctions", "other")
            )
            if categories is not None
            else None
        ),
        windowed_repetitions=_windowed_repetitions(paragraph_list),
        pronoun_distribution=(
            tuple(
                (name, sum(word_counts[word] for word in variants))
                for name, variants in capability.pronoun_groups
            )
            if capability is not None
            else None
        ),
        skipped_metrics=() if capability is not None else LANGUAGE_SENSITIVE_METRICS,
    )


def check_prose(project: Project) -> list[Finding]:
    """Inspect managed Markdown independently without changing the project."""

    configured_language = project.manifest.metadata.get("language")
    language = configured_language if isinstance(configured_language, str) else ""
    findings: list[Finding] = []

    paths = [project.root / "project.md", *project.iter_managed_markdown()]
    seen: set[str] = set()
    for path in paths:
        relative_id = project.relative_id(path)
        if relative_id in seen:
            continue
        seen.add(relative_id)
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
        integrity = _integrity_lines(text)
        findings.extend(_tag_findings(relative_id, integrity))
        findings.extend(_tag_policy_findings(relative_id, integrity))

        if not _is_prose_path(relative_id):
            continue

        document_language = _prose_language(relative_id, source, language)
        if _normalize_language(document_language) == "ru":
            for hit in scan_lines(_typography_lines(visible.lines)):
                findings.append(
                    Finding(
                        code=hit.code,
                        severity=hit.severity,
                        message=hit.message,
                        path=relative_id,
                        line=hit.line,
                        next_action=hit.next_action,
                    )
                )
        metrics = analyze_prose(text, language=document_language)
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
        for word, start, end, count in metrics.windowed_repetitions:
            findings.append(
                Finding(
                    code=WINDOWED_REPETITION,
                    severity="info",
                    message=f"word '{word}' occurs {count} times in paragraphs {start}-{end}",
                    path=relative_id,
                    next_action="Use this windowed repetition count as a mechanical signal only.",
                )
            )
        message_parts = [
            f"words={metrics.word_count}",
            f"paragraphs={metrics.paragraph_count}",
            f"sentences={metrics.sentence_count}",
        ]
        if metrics.dialogue_ratio is not None:
            message_parts.append(f"dialogue-ratio={metrics.dialogue_ratio:.3f}")
        message_parts.extend(
            [
                f"sentence-mean={metrics.sentence_length_mean:.3f}",
                f"sentence-median={metrics.sentence_length_median:.3f}",
                f"sentence-min={min(metrics.sentence_lengths, default=0)}",
                f"sentence-max={max(metrics.sentence_lengths, default=0)}",
                f"sentence-stdev={metrics.sentence_length_stdev:.3f}",
                f"language={metrics.language}",
            ]
        )
        if metrics.opener_categories is not None:
            message_parts.append(f"openers={dict(metrics.opener_categories)}")
        if metrics.pronoun_distribution is not None:
            message_parts.append(f"pronouns={dict(metrics.pronoun_distribution)}")
        if metrics.skipped_metrics:
            message_parts.append(f"skipped={','.join(metrics.skipped_metrics)}")
        measured_metrics = list(UNIVERSAL_METRICS)
        if metrics.language_capability is not None:
            measured_metrics.extend(LANGUAGE_SENSITIVE_METRICS)

        findings.append(
            Finding(
                code=METRICS,
                severity="info",
                message="; ".join(message_parts),
                path=relative_id,
                next_action="Use these counts as mechanical context, not as a literary conclusion.",
                details={
                    "language": metrics.language,
                    "language_capability": metrics.language_capability,
                    "measured_metrics": measured_metrics,
                    "skipped_metrics": list(metrics.skipped_metrics),
                },
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
        marker = markdown_fence_marker(line)
        if fence_character is None:
            if marker is not None:
                fence_character = marker[0]
                fence_length = marker[1]
                fence_line = line_number
                visible.append((line_number, ""))
            else:
                visible.append((line_number, _strip_inline_code(line)))
            continue

        if marker is not None:
            if closes_markdown_fence(marker, (fence_character, fence_length)):
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


def _integrity_lines(text: str) -> tuple[tuple[int, str], ...]:
    """Return all raw document lines except fenced code, preserving frontmatter lines."""

    lines: list[tuple[int, str]] = []
    fence: tuple[str, int] | None = None
    for line_number, line in enumerate(text.splitlines(), 1):
        marker = markdown_fence_marker(line)
        if fence is None:
            if marker is not None:
                fence = marker[:2]
                lines.append((line_number, ""))
            else:
                lines.append((line_number, _strip_inline_code(line)))
        else:
            if marker is not None:
                if closes_markdown_fence(marker, fence):
                    fence = None
            lines.append((line_number, ""))
    return tuple(lines)


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
    fence: tuple[str, int] | None = None
    for line in lines[start:]:
        marker = markdown_fence_marker(line)
        if fence is None and marker is not None:
            fence = marker[:2]
            continue
        if fence is not None and marker is not None:
            if closes_markdown_fence(marker, fence):
                fence = None
            continue
        if fence is None:
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


def _typography_lines(lines: tuple[tuple[int, str], ...]) -> list[tuple[int, str]]:
    """Prepare visible lines for the typography scanner: no code, no link targets."""

    return [
        (line_number, _LINK_TARGET_RE.sub("", _strip_inline_code(line)))
        for line_number, line in lines
    ]


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
    return [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(text) if part.strip()]


def _first_word(text: str) -> str | None:
    word_list = _words(text)
    return word_list[0] if word_list else None


def _opener_category(opener: str, capability: LanguageCapability) -> str:
    if opener in capability.pronoun_starts:
        return "pronouns"
    if opener in capability.article_starts:
        return "articles"
    if opener in capability.conjunction_starts:
        return "conjunctions"
    return "other"


def _windowed_repetitions(paragraphs: list[str], window_size: int = 5) -> tuple[tuple[str, int, int, int], ...]:
    found: dict[tuple[str, int, int], int] = {}
    if len(paragraphs) < 2:
        return ()
    for start in range(0, max(len(paragraphs) - window_size + 1, 1)):
        window = paragraphs[start : start + window_size]
        counts = Counter(word for paragraph in window for word in _words(paragraph) if len(word) >= 5)
        for word, count in counts.items():
            if count >= 3:
                found[(word, start + 1, start + len(window))] = count
    return tuple((word, start, end, count) for (word, start, end), count in sorted(found.items(), key=lambda item: (-item[1], item[0])))


def _is_dialogue(line: str, capability: LanguageCapability) -> bool:
    return bool(capability.dialogue_quotes.search(line)) or (
        capability.dash_dialogue and line.lstrip().startswith("—")
    )


def _normalize_language(language: str) -> str:
    if not isinstance(language, str):
        return "und"
    normalized = unicodedata.normalize("NFKC", language).strip().replace("_", "-").casefold()
    if _LANGUAGE_TAG_RE.fullmatch(normalized) is None:
        return "und"
    return normalized.split("-", 1)[0]


def _prose_language(relative_id: str, source: bytes, project_language: str) -> str:
    if Path(relative_id).parent.as_posix() != "kb/samples":
        return project_language
    try:
        value = parse_document(source).metadata.get("language")
    except (UnicodeError, ValueError):
        return project_language
    return value if isinstance(value, str) and value.strip() else project_language


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


def _finding_key(item: Finding) -> tuple[str, str, int, str]:
    return (item.path or "", item.code, item.line or 0, item.message)


__all__ = [
    "EMPTY_DOCUMENT",
    "MARKDOWN_FENCE",
    "LANGUAGE_SENSITIVE_METRICS",
    "METRICS",
    "ProseMetrics",
    "REPEATED_OPENING",
    "SOURCE_TAG",
    "SOURCE_TAG_POLICY",
    "UNREADABLE_DOCUMENT",
    "UNIVERSAL_METRICS",
    "WINDOWED_REPETITION",
    "analyze_prose",
    "check_prose",
]
