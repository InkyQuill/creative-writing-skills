"""Measure dialogue mechanics in a prose file.

This script is a deterministic port of the core measurements of the upstream
"dialogue" skill's TypeScript scripts. It counts dialogue lines, attribution
tags, same-speaker runs, and speaker vocabulary overlap. It measures dialogue
mechanics and renders no verdicts: every number it prints is an observation
about the text, never a judgment about quality or craft.

Language handling is limited to Russian (em-dash or guillemet dialogue with a
Russian attribution verb list) and English (double-quoted dialogue with an
English attribution verb list). Detection is heuristic and deterministic.

Usage: python3 dialogue_audit.py <file> [--format json]
"""

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Dialogue = Russian em-dash lead-in or guillemet quote anywhere in the line.
_RU_DIALOGUE_LINE_RE = re.compile(r"^\s*[—–]\s*\S|«[^»]+»")
# Dialogue = English double-quoted span opening the line.
_EN_DIALOGUE_LINE_RE = re.compile(r'^\s*"[^"]+"')

# Attribution = verb + capitalized name at end of line; apply per line.
_RU_ATTRIBUTION_RE = re.compile(
    r"(?:сказал[а]?|спросил[а]?|ответил[а]?|произнёс|произнесла|"
    r"прошептал[а]?|добавил[а]?|заметил[а]?|выдохнул[а]?|"
    r"пробормотал[а]?)\s+([А-ЯЁ][А-Яа-яЁё-]+)\s*\.?\s*$")
_EN_ATTRIBUTION_RE = re.compile(
    r"(?:said|asked|replied|whispered|added|remarked|muttered)\s+"
    r"([A-Z][A-Za-z-]+)\s*\.?\s*$")

# Words of the attributed line body, used for speaker vocabulary overlap.
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

_DIALOGUE_PATTERNS = {
    "ru": (_RU_DIALOGUE_LINE_RE, _RU_ATTRIBUTION_RE),
    "en": (_EN_DIALOGUE_LINE_RE, _EN_ATTRIBUTION_RE),
}

_CYRILLIC_RANGE = ("\u0400", "\u04FF")
_LANGUAGE_SHARE_THRESHOLD = 0.3
_MIN_LINES_PER_SPEAKER = 3
_MAX_OVERLAP_PAIRS = 5
_MIN_WORD_LENGTH = 3  # words longer than this feed the vocabulary


@dataclass(frozen=True)
class DialogueStats:
    """Deterministic dialogue-mechanics measurements for one text."""

    total_lines: int              # non-empty prose lines
    dialogue_lines: int           # lines detected as dialogue (ru dash or quotes)
    dialogue_ratio: float
    attribution_lines: int        # dialogue lines carrying an attribution tag
    attribution_ratio: float      # attribution_lines / dialogue_lines (0.0 if none)
    max_same_speaker_run: int     # longest run of consecutive attributed lines with one name
    speaker_overlap: tuple[tuple[str, str, float], ...]  # top Jaccard pairs, desc, max 5


def detect_language(text: str) -> str:
    """Return "ru" when Cyrillic letters make up more than 30% of letters."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return "en"
    low, high = _CYRILLIC_RANGE
    cyrillic = sum(1 for ch in letters if low <= ch <= high)
    share = cyrillic / len(letters)
    return "ru" if share > _LANGUAGE_SHARE_THRESHOLD else "en"


def _speaker_vocabulary(line: str) -> set[str]:
    """Return lowercase words longer than 3 characters from one line."""
    return {
        word.lower()
        for word in _WORD_RE.findall(line)
        if len(word) > _MIN_WORD_LENGTH
    }


def _overlap_pairs(
    counts: dict[str, int], vocab: dict[str, set[str]]
) -> tuple[tuple[str, str, float], ...]:
    """Return the top Jaccard vocabulary-overlap pairs between speakers.

    Only pairs where both speakers have at least the minimum number of
    attributed lines are reported. Pairs sort by score descending, capped,
    with ties broken by the alphabetical order of the name pair.
    """
    scored: list[tuple[str, str, float]] = []
    names = sorted(counts)
    for i, first in enumerate(names):
        if counts[first] < _MIN_LINES_PER_SPEAKER:
            continue
        for second in names[i + 1:]:
            if counts[second] < _MIN_LINES_PER_SPEAKER:
                continue
            first_words, second_words = vocab[first], vocab[second]
            union = first_words | second_words
            if not union:
                score = 0.0
            else:
                score = len(first_words & second_words) / len(union)
            scored.append((first, second, score))
    scored.sort(key=lambda item: (-item[2], item[0], item[1]))
    return tuple(scored[:_MAX_OVERLAP_PAIRS])


def audit_dialogue(text: str, *, language: str) -> DialogueStats:
    """Measure dialogue mechanics for one text in one language."""
    try:
        dialogue_re, attribution_re = _DIALOGUE_PATTERNS[language]
    except KeyError:
        raise ValueError(f"unsupported language: {language!r}") from None

    lines = [line for line in text.splitlines() if line.strip()]
    dialogue_lines = 0
    attribution_lines = 0
    current_speaker: str | None = None
    current_run = 0
    max_run = 0
    speaker_counts: dict[str, int] = {}
    speaker_vocab: dict[str, set[str]] = {}

    for line in lines:
        if not dialogue_re.search(line):
            # A non-dialogue line interrupts any running speaker streak.
            current_speaker = None
            current_run = 0
            continue
        dialogue_lines += 1
        match = attribution_re.search(line)
        if match is None:
            # Unattributed dialogue also interrupts a running speaker streak.
            current_speaker = None
            current_run = 0
            continue
        attribution_lines += 1
        speaker = match.group(1)
        speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
        speaker_vocab.setdefault(speaker, set()).update(_speaker_vocabulary(line))
        if speaker == current_speaker:
            current_run += 1
        else:
            current_speaker = speaker
            current_run = 1
        if current_run > max_run:
            max_run = current_run

    total_lines = len(lines)
    dialogue_ratio = dialogue_lines / total_lines if total_lines else 0.0
    attribution_ratio = (
        attribution_lines / dialogue_lines if dialogue_lines else 0.0
    )
    return DialogueStats(
        total_lines=total_lines,
        dialogue_lines=dialogue_lines,
        dialogue_ratio=dialogue_ratio,
        attribution_lines=attribution_lines,
        attribution_ratio=attribution_ratio,
        max_same_speaker_run=max_run,
        speaker_overlap=_overlap_pairs(speaker_counts, speaker_vocab),
    )


def _render_text_summary(stats: DialogueStats, language: str) -> str:
    """Return a compact multi-line human summary of the measurements."""
    lines = [
        f"language: {language}",
        f"total lines: {stats.total_lines}",
        f"dialogue lines: {stats.dialogue_lines} ({stats.dialogue_ratio:.0%})",
        f"attribution lines: {stats.attribution_lines} "
        f"({stats.attribution_ratio:.0%} of dialogue)",
        f"max same-speaker run: {stats.max_same_speaker_run}",
    ]
    if stats.speaker_overlap:
        pairs = ", ".join(
            f"{first}/{second} {score:.2f}"
            for first, second, score in stats.speaker_overlap
        )
        lines.append(f"speaker overlap: {pairs}")
    else:
        lines.append("speaker overlap: none")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns 0 on success and 2 on usage or IO errors."""
    parser = argparse.ArgumentParser(
        prog="dialogue_audit.py",
        description=(
            "Measure dialogue mechanics of a prose file. "
            "Measurement only: renders no verdicts."
        ),
    )
    parser.add_argument("file", type=Path, help="path to a UTF-8 prose file")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format: compact text summary (default) or JSON",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse usage errors exit with code 2; --help exits with 0.
        return exc.code if isinstance(exc.code, int) else 2

    try:
        text = args.file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"dialogue_audit: cannot read {args.file}: {exc}", file=sys.stderr)
        return 2

    language = detect_language(text)
    stats = audit_dialogue(text, language=language)
    if args.format == "json":
        print(json.dumps(asdict(stats), ensure_ascii=False))
    else:
        print(_render_text_summary(stats, language))
    return 0


if __name__ == "__main__":
    sys.exit(main())
