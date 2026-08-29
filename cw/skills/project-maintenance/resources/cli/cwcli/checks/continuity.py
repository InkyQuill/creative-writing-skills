"""Deterministic checks for explicit structured continuity records."""

from __future__ import annotations

import re
import stat
import unicodedata
from pathlib import Path

from ..findings import Finding, Severity
from ..markdown_tables import (
    MarkdownTable,
    TableRow,
    malformed_table_lines,
    parse_tables,
    table_header_lines,
)
from ..project import Project


RECORD_NAMES = ("timeline.md", "state.md", "promises.md", "questions.md")
PROMISE_STATUSES = {"planned", "planted", "paid-off", "dropped"}
QUESTION_STATUSES = {"open", "answered", "partially-answered", "dropped"}
CHEKHOV_GAP = 3

RECORD = "CW-CONT-001"
STATE = "CW-CONT-010"
DEATH = "CW-CONT-020"
SCENE = "CW-CONT-021"
PROMISE = "CW-CONT-030"
QUESTION = "CW-CONT-040"
TIMELINE = "CW-CONT-050"
UNKNOWN_CHARACTER = "CW-CONT-060"
MALFORMED = "CW-CONT-090"

_CHAPTER_RE = re.compile(r"(?:Chapter|Ch)[-\s]*(\d+)(?:\.(\d+))?", re.IGNORECASE)
_DECEASED_RE = re.compile(
    r"(?:dead|deceased)(?:\s*\(ch(?:apter)?[-\s]*(\d+)\))?",
    re.IGNORECASE,
)
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)


def check_continuity(project: Project) -> list[Finding]:
    """Check structured records independently and never infer facts from prose."""

    root = project.root / "kb" / "continuity"
    if _contains_symlink(project.root, root):
        return [_finding(RECORD, "warning", "kb/continuity is a symlink and was not inspected", "kb/continuity", None,
                         "Replace the link with explicit continuity records inside this project.")]
    if not root.is_dir():
        return [_finding(RECORD, "warning", "continuity record directory is missing", "kb/continuity", None,
                         "Restore kb/continuity and its canonical record files when continuity tracking is needed.")]
    if _nested_project_boundary(project.root, root) is not None:
        return [_finding(RECORD, "warning", "kb/continuity belongs to a nested project and was not inspected",
                         "kb/continuity", None, "Run the continuity check from the nested project's own root.")]

    findings: list[Finding] = []
    loaded: dict[str, tuple[str, tuple[MarkdownTable, ...]]] = {}
    for name in RECORD_NAMES:
        relative = f"kb/continuity/{name}"
        result = _read_record(root / name, relative, findings)
        if result is not None:
            loaded[name] = result

    character_ids = _character_ids(project, findings)
    state_current: int | None = None
    story_status = "draft"
    deceased: dict[str, tuple[str, int, int]] = {}

    if "state.md" in loaded:
        text, tables = loaded["state.md"]
        state_current = _last_int_field(text, "current-chapter")
        story_status = _last_word_field(text, "story-status") or "draft"
        recognized: set[int] = set()
        legacy_state_shape = False
        for table_index, table in enumerate(tables):
            headers = _headers(table)
            if _has_columns(headers, ("character", "location", "status", "injuries", "relationships")):
                recognized.add(table_index)
                legacy_state_shape = True
                for row in table.rows:
                    values = _row(table, row)
                    character = values["character"]
                    _check_character(character, "kb/continuity/state.md", row.line, character_ids, findings)
                    death = _death_chapter(values.get("status", ""), "")
                    if death is not None:
                        deceased[_identity(character)] = (character, death, row.line)
            elif _has_columns(headers, ("character", "state", "since")):
                recognized.add(table_index)
                for row in table.rows:
                    values = _row(table, row)
                    character = values["character"]
                    _check_character(character, "kb/continuity/state.md", row.line, character_ids, findings)
                    death = _death_chapter(values.get("state", ""), values.get("since", ""))
                    if death is not None:
                        deceased[_identity(character)] = (character, death, row.line)
            elif _has_columns(headers, ("character", "fact", "learned in")):
                recognized.add(table_index)
                legacy_state_shape = True
                for row in table.rows:
                    values = _row(table, row)
                    _check_character(values["character"], "kb/continuity/state.md", row.line, character_ids, findings)
                    learned = _parse_chapter(values.get("learned in", ""))
                    if learned is not None and state_current is not None and learned > state_current:
                        findings.append(_finding(STATE, "error",
                            f"{values['character']!r} learned a fact in chapter {learned} beyond current-chapter {state_current}",
                            "kb/continuity/state.md", row.line,
                            "Correct the explicit learned-in or current-chapter record after confirming chronology."))
        if state_current is None and (legacy_state_shape or "current-chapter:" in text.casefold()):
            findings.append(_finding(STATE, "error", "current-chapter is missing or is not a positive integer",
                                     "kb/continuity/state.md", _field_line(text, "current-chapter"),
                                     "Repair current-chapter without changing unrelated state records."))
        _warn_partial("state.md", text, tables, recognized, findings)

    scenes = _load_scenes(project.root, root / "scenes", character_ids, findings)
    scene_records = [record for _path, record in scenes]
    if _path_kind(root / "scenes") == "missing":
        findings.append(_finding(RECORD, "warning", "canonical scenes directory is missing",
                                 "kb/continuity/scenes", None,
                                 "Restore the scenes directory before recording structured scene continuity."))
    max_scene = max((item[0] for item in scene_records if item[0] is not None), default=None)
    if state_current is not None and max_scene is not None and state_current != max_scene:
        if state_current > max_scene:
            message = f"current-chapter {state_current} is ahead of latest scene record chapter {max_scene}"
        else:
            message = f"scene records reach chapter {max_scene} beyond current-chapter {state_current}"
        findings.append(_finding(STATE, "warning", message, "kb/continuity/state.md",
                                 _field_line(loaded.get("state.md", ("", ()))[0], "current-chapter"),
                                 "Refresh the stale explicit state or scene records after confirming the writing front."))

    for relative, (chapter, present, pov, anchor, line) in scenes:
        if pov and _identity(pov) not in {_identity(name) for name in present}:
            findings.append(_finding(SCENE, "warning", f"POV {pov!r} is not in the explicit scene cast",
                                     relative, line, "Add the POV to the cast or correct the POV field."))
        if chapter is not None:
            for name in present:
                death = deceased.get(_identity(name))
                if death is not None and chapter > death[1]:
                    findings.append(_finding(DEATH, "error",
                        f"{name!r} is in the scene cast after the recorded death in chapter {death[1]}",
                        relative, line, "Move the character to mentions or correct the explicit death/scene chronology."))

    timeline_anchors: dict[str, tuple[set[str], set[int]]] = {}
    if "timeline.md" in loaded:
        text, tables = loaded["timeline.md"]
        recognized: set[int] = set()
        last_story_chapter: int | None = None
        for table_index, table in enumerate(tables):
            if not _has_columns(_headers(table), ("when", "event", "threads", "anchor")):
                continue
            recognized.add(table_index)
            for row in table.rows:
                values = _row(table, row)
                section = _section_before(text, row.line)
                if section != "story":
                    continue
                chapter = _parse_chapter(values.get("chapter", ""))
                _add_anchor(timeline_anchors, values.get("anchor", ""), values.get("when", ""), chapter)
                if chapter is not None and last_story_chapter is not None and chapter < last_story_chapter:
                    findings.append(_finding(TIMELINE, "warning",
                        f"story event {values.get('event', '')!r} in chapter {chapter} is out of order after chapter {last_story_chapter}",
                        "kb/continuity/timeline.md", row.line,
                        "Reorder the explicit timeline row or correct its chapter anchor."))
                if chapter is not None:
                    last_story_chapter = max(last_story_chapter or 0, chapter)
        _warn_partial("timeline.md", text, tables, recognized, findings)
        for relative, text, tables in _character_timeline_documents(project, findings):
            for table in tables:
                if not _has_columns(_headers(table), ("when", "event", "threads", "anchor")):
                    continue
                for row in table.rows:
                    values = _row(table, row)
                    _add_anchor(timeline_anchors, values.get("anchor", ""), values.get("when", ""),
                                _parse_chapter(values.get("chapter", "")))

        for anchor, (whens, chapters) in sorted(timeline_anchors.items()):
            if len(whens) > 1:
                findings.append(_finding(TIMELINE, "warning",
                    f"anchor {anchor!r} mixes When values {sorted(whens)!r}",
                    "kb/continuity/timeline.md", None,
                    "Choose one explicit When value for this shared anchor."))
            if len(chapters) > 1:
                findings.append(_finding(TIMELINE, "error",
                    f"anchor {anchor!r} spans chapters {sorted(chapters)!r}",
                    "kb/continuity/timeline.md", None,
                    "Correct the explicit chapter references for this shared anchor."))
        for relative, (_chapter, _present, _pov, anchor, line) in scenes:
            if anchor and _identity(anchor) not in timeline_anchors:
                findings.append(_finding(TIMELINE, "warning",
                    f"scene anchor {anchor!r} is not present in timeline.md", relative, line,
                    "Add the explicit anchor to the timeline or correct the scene record."))

    horizon = state_current if state_current is not None else (max_scene or 0)
    if "promises.md" in loaded:
        text, tables = loaded["promises.md"]
        recognized: set[int] = set()
        for table_index, table in enumerate(tables):
            if not _has_columns(_headers(table), ("promise", "status", "planted", "payoff", "pov knows", "evidence")):
                continue
            recognized.add(table_index)
            for row in table.rows:
                _check_promise(_row(table, row), row.line, state_current, horizon, story_status, findings)
        _warn_partial("promises.md", text, tables, recognized, findings)

    if "questions.md" in loaded:
        text, tables = loaded["questions.md"]
        recognized: set[int] = set()
        for table_index, table in enumerate(tables):
            if not _has_columns(_headers(table), ("question", "status", "introduced", "answered", "evidence")):
                continue
            recognized.add(table_index)
            for row in table.rows:
                _check_question(_row(table, row), row.line, state_current, story_status, findings)
        _warn_partial("questions.md", text, tables, recognized, findings)

    return sorted(findings, key=lambda item: (item.path or "", item.line or 0, item.code, item.message))


def _check_promise(values: dict[str, str], line: int, current: int | None, horizon: int,
                   story_status: str, findings: list[Finding]) -> None:
    name = values.get("promise", "")
    status = values.get("status", "").strip().casefold()
    planted = _parse_chapter(values.get("planted", ""))
    payoff = _parse_chapter(values.get("payoff", ""))
    messages: list[tuple[str, str]] = []
    if status not in PROMISE_STATUSES:
        messages.append(("error", f"promise {name!r} has unknown status {status!r}"))
    else:
        if status in {"planted", "paid-off"} and planted is None:
            messages.append(("error", f"promise {name!r} is {status} but has no planted chapter"))
        if status == "paid-off" and payoff is None:
            messages.append(("error", f"promise {name!r} is paid-off but has no payoff chapter"))
        if planted is not None and payoff is not None and payoff < planted:
            messages.append(("error", f"promise {name!r} payoff chapter {payoff} precedes planted chapter {planted}"))
        if payoff is not None and current is not None and payoff > current:
            messages.append(("error", f"promise {name!r} payoff chapter {payoff} is beyond current-chapter {current}"))
        if status == "planned" and planted is not None:
            messages.append(("warning", f"promise {name!r} is still planned but planted in chapter {planted}"))
        if status == "planted" and planted is not None and payoff is None and horizon - planted >= CHEKHOV_GAP:
            messages.append(("warning", f"promise {name!r} has no payoff for {horizon - planted} chapters"))
        if story_status == "complete" and status in {"planned", "planted"}:
            messages.append(("error", f"promise {name!r} is {status} but the story is complete"))
    for severity, message in messages:
        findings.append(_finding(PROMISE, severity, message, "kb/continuity/promises.md", line,
                                 "Correct the explicit promise lifecycle fields after confirming intent."))


def _check_question(values: dict[str, str], line: int, current: int | None,
                    story_status: str, findings: list[Finding]) -> None:
    name = values.get("question", "")
    status = values.get("status", "").strip().casefold()
    introduced = _parse_chapter(values.get("introduced", ""))
    answered = _parse_chapter(values.get("answered", ""))
    messages: list[tuple[str, str]] = []
    if status not in QUESTION_STATUSES:
        messages.append(("error", f"question {name!r} has unknown status {status!r}"))
    else:
        if status in {"answered", "partially-answered"} and answered is None:
            messages.append(("error", f"question {name!r} is {status} but has no answered chapter"))
        if status in {"answered", "partially-answered"} and introduced is None:
            messages.append(("error", f"question {name!r} is {status} but has no introduced chapter"))
        if introduced is not None and answered is not None and answered < introduced:
            messages.append(("error", f"question {name!r} answer chapter {answered} precedes introduction chapter {introduced}"))
        if answered is not None and current is not None and answered > current:
            messages.append(("error", f"question {name!r} answer chapter {answered} is beyond current-chapter {current}"))
        if status == "open" and answered is not None:
            messages.append(("warning", f"question {name!r} is open but has an answer in chapter {answered}"))
        if introduced is not None and current is not None and introduced > current:
            messages.append(("error", f"question {name!r} introduction chapter {introduced} is beyond current-chapter {current}"))
        if story_status == "complete" and status in {"open", "partially-answered"}:
            messages.append(("error", f"question {name!r} is {status} but the story is complete"))
    for severity, message in messages:
        findings.append(_finding(QUESTION, severity, message, "kb/continuity/questions.md", line,
                                 "Correct the explicit question lifecycle fields after confirming intent."))


def _load_scenes(project_root: Path, directory: Path, character_ids: set[str], findings: list[Finding]) -> list[tuple[str, tuple[int | None, list[str], str, str, int]]]:
    records: list[tuple[str, tuple[int | None, list[str], str, str, int]]] = []
    if _path_kind(directory) != "directory":
        if _path_kind(directory) not in {"missing", "directory"}:
            findings.append(_finding(RECORD, "warning", "scenes path is not an ordinary directory",
                                     "kb/continuity/scenes", None,
                                     "Replace it with an ordinary in-project directory before checking scenes."))
        return records
    if _nested_project_boundary(project_root, directory) is not None:
        findings.append(_finding(RECORD, "warning", "scenes belongs to a nested project and was not inspected",
                                 "kb/continuity/scenes", None,
                                 "Run the continuity check from the nested project's own root."))
        return records
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if path.suffix.casefold() != ".md" or path.name == "_index.md":
            continue
        relative = f"kb/continuity/scenes/{path.name}"
        result = _read_record(path, relative, findings, required=False)
        if result is None:
            continue
        text, tables = result
        recognized: set[int] = set()
        filename_chapter = _parse_scene_chapter(path.stem)
        for table_index, table in enumerate(tables):
            headers = _headers(table)
            legacy = _has_columns(headers, ("scene", "pov", "location", "present", "mentions", "anchor", "state changes"))
            compact = _has_columns(headers, ("chapter", "cast"))
            if not legacy and not compact:
                continue
            recognized.add(table_index)
            for row in table.rows:
                values = _row(table, row)
                chapter = _parse_chapter(values.get("chapter", "")) if compact else filename_chapter
                cast_value = values.get("cast", values.get("present", ""))
                present = [item.strip() for item in cast_value.split(",") if item.strip()]
                mentions = [item.strip() for item in values.get("mentions", "").split(",") if item.strip()]
                pov = values.get("pov", "").strip()
                for character in present + mentions + ([pov] if pov else []):
                    _check_character(character, relative, row.line, character_ids, findings)
                records.append((relative, (chapter, present, pov, values.get("anchor", "").strip(), row.line)))
        _warn_partial(path.name, text, tables, recognized, findings, path=relative)
    return records


def _character_ids(project: Project, findings: list[Finding]) -> set[str]:
    directory = project.root / "kb" / "characters"
    if _path_kind(directory) != "directory" or _nested_project_boundary(project.root, directory) is not None:
        return set()
    identities: set[str] = set()
    for path in directory.iterdir():
        if path.name == "_index.md" or path.suffix.casefold() != ".md" or _path_kind(path) != "file":
            continue
        identities.add(_identity(path.stem))
    return identities


def _character_timeline_documents(project: Project, findings: list[Finding]):
    directory = project.root / "kb" / "characters"
    if _path_kind(directory) != "directory" or _nested_project_boundary(project.root, directory) is not None:
        return []
    documents = []
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if path.name == "_index.md" or path.suffix.casefold() != ".md" or _path_kind(path) != "file":
            continue
        relative = f"kb/characters/{path.name}"
        result = _read_record(path, relative, findings, required=False)
        if result is not None:
            documents.append((relative, result[0], result[1]))
    return documents


def _read_record(path: Path, relative: str, findings: list[Finding], *, required: bool = True):
    kind = _path_kind(path)
    if kind == "missing":
        if required:
            findings.append(_finding(RECORD, "warning", "canonical continuity record is missing", relative, None,
                                     f"Restore {relative} when this record is available."))
        return None
    if kind != "file":
        findings.append(_finding(RECORD, "warning", f"record is a {kind}, not an ordinary file", relative, None,
                                 "Replace this entry with an ordinary in-project Markdown file."))
        return None
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        findings.append(_finding(MALFORMED, "warning", f"record could not be read as UTF-8: {error}", relative, None,
                                 "Repair this file's encoding while preserving its content."))
        return None
    return text, parse_tables(text)


def _warn_partial(name: str, text: str, tables: tuple[MarkdownTable, ...], recognized: set[int],
                  findings: list[Finding], *, path: str | None = None) -> None:
    relative = path or f"kb/continuity/{name}"
    headers = table_header_lines(text)
    for table_index, line in enumerate(headers):
        if table_index in recognized:
            continue
        findings.append(_finding(MALFORMED, "warning", f"{name} contains a table with unrecognized columns",
                                 relative, line,
                                 "Use an explicitly supported header without assigning column roles by guesswork."))
    for line in malformed_table_lines(text):
        findings.append(_finding(MALFORMED, "warning", f"{name} contains a malformed or incomplete table",
                                 relative, line,
                                 "Repair the delimiter/header without assigning semantic column roles by guesswork."))


def _headers(table: MarkdownTable) -> tuple[str, ...]:
    return tuple(cell.strip().casefold() for cell in table.headers)


def _has_columns(headers: tuple[str, ...], required: tuple[str, ...]) -> bool:
    return all(column in headers for column in required)


def _row(table: MarkdownTable, row: TableRow) -> dict[str, str]:
    return dict(zip(_headers(table), row.cells))


def _parse_chapter(value: str) -> int | None:
    if not value or value.strip() in {"—", "-"}:
        return None
    match = _CHAPTER_RE.search(value)
    if match:
        return int(match.group(1))
    return None


def _parse_scene_chapter(value: str) -> int | None:
    chapter = _parse_chapter(value)
    if chapter is not None:
        return chapter
    match = re.search(r"\d+", value)
    return int(match.group()) if match else None


def _death_chapter(state: str, since: str) -> int | None:
    match = _DECEASED_RE.fullmatch(state.strip())
    if not match:
        return None
    explicit = match.group(1)
    return int(explicit) if explicit else _parse_chapter(since)


def _identity(value: str) -> str:
    return unicodedata.normalize("NFC", value.strip()).casefold()


def _check_character(value: str, path: str, line: int, known: set[str], findings: list[Finding]) -> None:
    identity = _identity(value)
    if not identity or identity in known:
        return
    if _safe_character_stem(value):
        action = f"Create kb/characters/{value.strip()}.md or correct the explicit character ID."
    else:
        action = "Correct the explicit character ID to one safe portable file stem."
    findings.append(_finding(UNKNOWN_CHARACTER, "warning", f"unknown character ID {value!r}", path, line, action))


def _safe_character_stem(value: str) -> bool:
    if not value or value != value.strip() or value in {".", ".."}:
        return False
    if unicodedata.normalize("NFC", value) != value:
        return False
    if value.endswith((".", " ")) or any(character in '<>:"/\\|?*' for character in value):
        return False
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return False
    return value.rstrip(". ").split(".", 1)[0].upper() not in _WINDOWS_RESERVED


def _add_anchor(anchors: dict[str, tuple[set[str], set[int]]], anchor: str, when: str, chapter: int | None) -> None:
    identity = _identity(anchor)
    if not identity:
        return
    whens, chapters = anchors.setdefault(identity, (set(), set()))
    whens.add(when.strip())
    if chapter is not None:
        chapters.add(chapter)


def _section_before(text: str, line: int) -> str:
    section = ""
    for value in text.splitlines()[:line]:
        if value.strip().startswith("## "):
            section = value.strip()[3:].strip().casefold()
    return section


def _last_int_field(text: str, name: str) -> int | None:
    matches = re.findall(rf"^{re.escape(name)}:\s*(\d+)\s*$", text, re.MULTILINE | re.IGNORECASE)
    return int(matches[-1]) if matches else None


def _last_word_field(text: str, name: str) -> str | None:
    matches = re.findall(rf"^{re.escape(name)}:\s*(\S+)\s*$", text, re.MULTILINE | re.IGNORECASE)
    return matches[-1].casefold() if matches else None


def _field_line(text: str, name: str) -> int | None:
    for index, line in enumerate(text.splitlines(), 1):
        if re.match(rf"^{re.escape(name)}:", line, re.IGNORECASE):
            return index
    return None


def _path_kind(path: Path) -> str:
    try:
        mode = path.lstat().st_mode
    except (FileNotFoundError, NotADirectoryError):
        return "missing"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    return "other filesystem entry"


def _contains_symlink(root: Path, target: Path) -> bool:
    current = root
    for part in target.relative_to(root).parts:
        current /= part
        if _path_kind(current) == "symlink":
            return True
    return False


def _nested_project_boundary(project_root: Path, target: Path) -> Path | None:
    current = project_root
    relative = target.relative_to(project_root)
    for part in relative.parts:
        current /= part
        manifest = current / "project.md"
        if _path_kind(manifest) == "file":
            return current
    return None


def _finding(code: str, severity: Severity, message: str, path: str, line: int | None, next_action: str) -> Finding:
    return Finding(code=code, severity=severity, message=message, path=path, line=line, next_action=next_action)


__all__ = [
    "DEATH", "MALFORMED", "PROMISE", "QUESTION", "RECORD", "SCENE", "STATE",
    "TIMELINE", "UNKNOWN_CHARACTER", "check_continuity",
]
