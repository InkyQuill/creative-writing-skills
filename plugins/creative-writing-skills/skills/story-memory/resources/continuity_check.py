#!/usr/bin/env python3
"""
Deterministic continuity checks for story continuity records.

Usage (from the installed story-memory skill directory):
    python3 resources/continuity_check.py <project-root>

Discovers timeline.md, promises.md, questions.md, state.md, and scenes/
under the project's plot/ or kb/ continuity root and reports ambiguous or
incomplete record sets, ordering violations, lifecycle mismatches, stale
state, and anchor conflicts across the master timeline and embedded
sub-timelines.
Exit status is 1 when errors are found, 0 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RECORD_NAMES = ("timeline.md", "promises.md", "questions.md", "state.md")
CHEKHOV_GAP = 3
PROMISE_STATUSES = {"planned", "planted", "paid-off", "dropped"}
QUESTION_STATUSES = {"open", "answered", "partially-answered", "dropped"}
CHAPTER_RE = re.compile(r"(?:Chapter|Ch)\s*(\d+)(?:\.(\d+))?", re.IGNORECASE)
DECEASED_RE = re.compile(r"deceased\s*\(Ch\s*(\d+)\)", re.IGNORECASE)
AMBIGUOUS_ROOT_FINDING = (
    "- [error] records: both plot/ and kb/ contain continuity records; "
    + "configure exactly one continuity root in the project instructions"
)


class AmbiguousContinuityRootError(ValueError):
    """Raised when both supported layout roots contain continuity records."""


def parse_chapter(value: str) -> int | None:
    if not value or value.strip() in {"—", "-", ""}:
        return None
    match = CHAPTER_RE.search(value)
    if not match:
        return None
    return int(match.group(1))


def split_tables(text: str, columns: list[str]) -> list[dict[str, str]]:
    """Yield one dict per table row whose header matches ``columns`` in order."""
    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            header = None
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if set("".join(cells)) <= {"-", ":", " "}:
            continue
        lowered = [cell.lower() for cell in cells]
        if lowered == [column.lower() for column in columns]:
            header = lowered
            continue
        if header is not None and len(cells) == len(columns):
            rows.append(dict(zip(header, cells)))
    return rows


def find_continuity_root(project_root: Path) -> tuple[Path, dict[str, Path]]:
    """Locate the record files under the project's single populated layout root."""
    populated: list[Path] = []
    for candidate in (project_root / "plot", project_root / "kb"):
        if not candidate.is_dir():
            continue
        hits = sum(
            1
            for name in RECORD_NAMES
            if (candidate / name).is_file()
        ) + (1 if (candidate / "scenes").is_dir() else 0)
        if hits:
            populated.append(candidate)
    if len(populated) > 1:
        raise AmbiguousContinuityRootError
    if not populated:
        return project_root, {}
    root = populated[0]
    paths = {
        name: root / name
        for name in RECORD_NAMES
        if (root / name).is_file()
    }
    scenes = root / "scenes"
    if scenes.is_dir():
        paths["scenes"] = scenes
    return root, paths


def load_scene_records(scenes_dir: Path) -> list[tuple[int, dict[str, str]]]:
    records: list[tuple[int, dict[str, str]]] = []
    for path in sorted(scenes_dir.glob("*.md")):
        match = re.search(r"(\d+)", path.stem)
        chapter = int(match.group(1)) if match else None
        for row in split_tables(
            path.read_text(encoding="utf-8"),
            ["Scene", "POV", "Location", "Present", "Mentions", "Anchor", "State changes"],
        ):
            records.append((chapter or 0, row))
    return records


def parse_state(text: str) -> tuple[int | None, str, list[dict[str, str]], list[dict[str, str]]]:
    current = None
    for match in re.finditer(r"^current-chapter:\s*(\d+)", text, re.MULTILINE):
        current = int(match.group(1))
    status_match = re.search(r"^story-status:\s*(\S+)", text, re.MULTILINE)
    story_status = status_match.group(1).lower() if status_match else "draft"
    characters = split_tables(
        text, ["Character", "Location", "Status", "Injuries", "Relationships"]
    )
    knowledge = split_tables(text, ["Character", "Fact", "Learned in"])
    return current, story_status, characters, knowledge


def timeline_sections(text: str) -> dict[str, list[dict[str, str]]]:
    """Parse `## Section` blocks with timeline-shaped tables."""
    sections: dict[str, list[dict[str, str]]] = {}
    current = ""
    prefix = ["when", "event", "threads", "anchor"]
    header: list[str] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current = stripped[3:].strip().lower()
            header = None
            continue
        if not stripped.startswith("|"):
            header = None
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if set("".join(cells)) <= {"-", ":", " "}:
            continue
        lowered = [cell.lower() for cell in cells]
        if len(lowered) >= 4 and lowered[:4] == prefix:
            header = lowered
            continue
        if header is not None and current and len(cells) == len(header):
            sections.setdefault(current, []).append(dict(zip(header, cells)))
    return sections


def check(project_root: Path) -> list[str]:
    findings: list[str] = []
    try:
        continuity_root, paths = find_continuity_root(project_root)
    except AmbiguousContinuityRootError:
        return [AMBIGUOUS_ROOT_FINDING]
    if not paths:
        return ["- [warning] records: no continuity records found under plot/ or kb/"]

    for name in RECORD_NAMES:
        if name not in paths:
            findings.append(f"- [error] records: missing {name}")
    if "scenes" not in paths:
        findings.append("- [error] records: missing scenes/")

    state_current: int | None = None
    story_status = "draft"
    deceased: dict[str, int] = {}
    if "state.md" in paths:
        current, story_status, characters, knowledge = parse_state(
            paths["state.md"].read_text(encoding="utf-8")
        )
        state_current = current
        if current is None:
            findings.append("- [error] state: current-chapter missing in state.md")
        for row in characters:
            match = DECEASED_RE.search(row.get("status", ""))
            if match:
                deceased[row.get("character", "").lower()] = int(match.group(1))
        for row in knowledge:
            learned = parse_chapter(row.get("learned in", ""))
            if learned is not None and state_current is not None and learned > state_current:
                findings.append(
                    f"- [error] state: \"{row.get('character')}\" learned a fact in Ch {learned} "
                    f"beyond current-chapter {state_current}"
                )

    scene_records: list[tuple[int, dict[str, str]]] = []
    if "scenes" in paths:
        scene_records = load_scene_records(paths["scenes"])
        max_scene = max((chapter for chapter, _ in scene_records), default=None)
        if state_current is not None and max_scene is not None:
            if state_current > max_scene:
                findings.append(
                    f"- [warning] state: current-chapter {state_current} is ahead of "
                    f"latest scene record ch-{max_scene:02d}; scene records are stale"
                )
            elif state_current < max_scene:
                findings.append(
                    f"- [warning] state: scene records reach ch-{max_scene:02d} beyond "
                    f"current-chapter {state_current}; state.md is stale"
                )
        for chapter, row in scene_records:
            present = [name.strip().lower() for name in row.get("present", "").split(",") if name.strip()]
            if row.get("pov", "").strip() and row["pov"].strip().lower() not in present:
                findings.append(
                    f"- [warning] scenes ch{chapter}: POV \"{row['pov']}\" is not in Present"
                )
            for name in present:
                if name in deceased and chapter > deceased[name]:
                    findings.append(
                        f"- [error] scenes ch{chapter}: \"{name}\" is Present after death in "
                        f"Ch {deceased[name]}; move the appearance to Mentions"
                    )

    timeline_anchors: dict[str, tuple[set[str], set[str]]] = {}
    if "timeline.md" in paths:
        sections = timeline_sections(paths["timeline.md"].read_text(encoding="utf-8"))
        story_rows = sections.get("story", [])
        subtimeline_rows: list[dict[str, str]] = []
        excluded = set(paths.values())
        scenes_dir = paths.get("scenes")
        for path in sorted(continuity_root.rglob("*.md")):
            if path in excluded or (scenes_dir is not None and scenes_dir in path.parents):
                continue
            subtimeline_sections = timeline_sections(path.read_text(encoding="utf-8"))
            subtimeline_rows.extend(
                row
                for rows in subtimeline_sections.values()
                for row in rows
            )
        last_chapter: int | None = None
        for row in story_rows:
            anchor = row.get("anchor", "").strip().lower()
            when = row.get("when", "").strip()
            chapter = parse_chapter(row.get("chapter", ""))
            if anchor:
                seen_when, seen_chapter = timeline_anchors.setdefault(anchor, (set(), set()))
                seen_when.add(when)
                if chapter is not None:
                    seen_chapter.add(str(chapter))
            if chapter is not None:
                if last_chapter is not None and chapter < last_chapter:
                    findings.append(
                        f"- [warning] timeline: Story row \"{row.get('event')}\" (Ch {chapter}) "
                        f"is out of order after Ch {last_chapter}"
                    )
                last_chapter = max(last_chapter or 0, chapter)
        for row in subtimeline_rows:
            anchor = row.get("anchor", "").strip().lower()
            if not anchor:
                continue
            seen_when, seen_chapter = timeline_anchors.setdefault(anchor, (set(), set()))
            seen_when.add(row.get("when", "").strip())
            chapter = parse_chapter(row.get("chapter", ""))
            if chapter is not None:
                seen_chapter.add(str(chapter))
        for anchor, (whens, chapters) in sorted(timeline_anchors.items()):
            if len(whens) > 1:
                findings.append(
                    f"- [warning] timeline: anchor \"{anchor}\" mixes When values {sorted(whens)}"
                )
            if len(chapters) > 1:
                findings.append(
                    f"- [error] timeline: anchor \"{anchor}\" spans chapters {sorted(chapters)}"
                )
        for chapter, row in scene_records:
            anchor = row.get("anchor", "").strip().lower()
            if anchor and anchor not in timeline_anchors:
                findings.append(
                    f"- [warning] scenes ch{chapter}: anchor \"{anchor}\" is not in timeline.md"
                )

    horizon = state_current
    if horizon is None:
        horizon = max((chapter for chapter, _ in scene_records), default=0)

    if "promises.md" in paths:
        for row in split_tables(
            paths["promises.md"].read_text(encoding="utf-8"),
            ["Promise", "Status", "Planted", "Payoff", "POV knows", "Evidence"],
        ):
            name = row.get("promise", "")
            status = row.get("status", "").strip().lower()
            planted = parse_chapter(row.get("planted", ""))
            payoff = parse_chapter(row.get("payoff", ""))
            if status not in PROMISE_STATUSES:
                findings.append(f"- [error] promises: \"{name}\" has unknown status \"{status}\"")
                continue
            if status in {"planted", "paid-off"} and planted is None:
                findings.append(
                    f"- [error] promises: \"{name}\" is {status} "
                    "but has no planted chapter"
                )
            if status == "paid-off" and payoff is None:
                findings.append(f"- [error] promises: \"{name}\" is paid-off but has no payoff chapter")
            if planted is not None and payoff is not None and payoff < planted:
                findings.append(
                    f"- [error] promises: \"{name}\" payoff Ch {payoff} precedes planted Ch {planted}"
                )
            if status == "planned" and planted is not None:
                findings.append(
                    f"- [warning] promises: \"{name}\" is still planned but planted in Ch {planted}"
                )
            if (
                status == "planted"
                and planted is not None
                and payoff is None
                and horizon - planted >= CHEKHOV_GAP
            ):
                findings.append(
                    f"- [warning] promises: \"{name}\" planted in Ch {planted} with no payoff "
                    f"for {horizon - planted} chapters"
                )
            if story_status == "complete" and status in {"planned", "planted"}:
                findings.append(
                    f"- [error] promises: \"{name}\" is {status} but the story is complete"
                )

    if "questions.md" in paths:
        for row in split_tables(
            paths["questions.md"].read_text(encoding="utf-8"),
            ["Question", "Status", "Introduced", "Answered", "Evidence"],
        ):
            name = row.get("question", "")
            status = row.get("status", "").strip().lower()
            introduced = parse_chapter(row.get("introduced", ""))
            answered = parse_chapter(row.get("answered", ""))
            if status not in QUESTION_STATUSES:
                findings.append(f"- [error] questions: \"{name}\" has unknown status \"{status}\"")
                continue
            if status in {"answered", "partially-answered"} and answered is None:
                findings.append(f"- [error] questions: \"{name}\" is {status} but has no answered chapter")
            if status in {"answered", "partially-answered"} and introduced is None:
                findings.append(
                    f"- [error] questions: \"{name}\" is {status} "
                    "but has no introduced chapter"
                )
            if introduced is not None and answered is not None and answered < introduced:
                findings.append(
                    f"- [error] questions: \"{name}\" answered Ch {answered} precedes introduced Ch {introduced}"
                )
            if status == "open" and answered is not None:
                findings.append(
                    f"- [warning] questions: \"{name}\" is open but answered in Ch {answered}"
                )
            if introduced is not None and state_current is not None and introduced > state_current:
                findings.append(
                    f"- [error] questions: \"{name}\" introduced in Ch {introduced} "
                    f"beyond current-chapter {state_current}"
                )
            if story_status == "complete" and status in {"open", "partially-answered"}:
                findings.append(
                    f"- [error] questions: \"{name}\" is {status} but the story is complete"
                )

    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check story continuity records")
    parser.add_argument("project_root", type=Path, help="story project root")
    args = parser.parse_args(argv)

    findings = check(args.project_root)
    errors = sum(1 for line in findings if "[error]" in line)
    warnings = sum(1 for line in findings if "[warning]" in line)
    for line in findings:
        print(line)
    print(f"{errors} error(s), {warnings} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
