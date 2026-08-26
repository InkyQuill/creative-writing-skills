import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = (
    REPO_ROOT
    / "plugins/creative-writing-skills/skills/story-memory/resources/continuity_check.py"
)


def load_checker():
    spec = importlib.util.spec_from_file_location("continuity_check", CHECKER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CHECKER = load_checker()

GOOD_TIMELINE = """# Timeline

## Backstory

| When | Event | Threads | Anchor | Evidence |
|---|---|---|---|---|
| ~12 years ago | Ember Rite | sera-arc | ember-rite | `sera.md` |

## Story

| When | Event | Threads | Anchor | Chapter |
|---|---|---|---|---|
| Day 1 | The letter is sealed | main | letter-sealed | Ch 3 |
| Day 3, morning | The crew crosses the strait | main | strait-crossing | Ch 7 |
| Day 3, morning | Kell signals the harbor | kell-thread | strait-crossing | Ch 7 |
"""

GOOD_PROMISES = """# Promises

| Promise | Status | Planted | Payoff | POV knows | Evidence |
|---|---|---|---|---|---|
| The sealed letter gets opened | paid-off | Ch 3 | Ch 9 | reader only | Chapter 3: Scene where the letter is sealed |
| The harbor signal is answered | planted | Ch 5 | — | Kell | Chapter 5: Scene where the signal is sent |
"""

GOOD_QUESTIONS = """# Questions

| Question | Status | Introduced | Answered | Evidence |
|---|---|---|---|---|
| Who paid the smugglers? | open | Ch 4 | — | Chapter 4: Scene where payment surfaces |
"""

GOOD_STATE = """# State at the Writing Front

current-chapter: 7
story-status: draft

## Characters

| Character | Location | Status | Injuries | Relationships |
|---|---|---|---|---|
| Sera | harbor | alive | healing ribs | trusts Kell |
| Mentor | capital | deceased (Ch 6) | — | — |

## Knowledge

| Character | Fact | Learned in |
|---|---|---|
| Kell | the crossing route | Ch 7 |

## Objects

| Object | Holder | Location | Status | Since |
|---|---|---|---|---|
| Sealed letter | Sera | satchel | opened | Ch 9 |

## Open Threads

- The blockade continues.
"""

GOOD_SCENES = """# Chapter 7 Scenes

| Scene | POV | Location | Present | Mentions | Anchor | State changes |
|---|---|---|---|---|---|---|
| 1 | Sera | strait | Sera, Kell | Mentor | strait-crossing | Kell learns the route |
"""


class ContinuityCheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.records = self.root / "kb"

    def write(self, name: str, text: str):
        path = self.records / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_scene(self, stem: str, text: str):
        scenes = self.records / "scenes"
        scenes.mkdir(parents=True, exist_ok=True)
        (scenes / f"{stem}.md").write_text(text, encoding="utf-8")

    def test_clean_project_passes(self):
        self.write("timeline.md", GOOD_TIMELINE)
        self.write("promises.md", GOOD_PROMISES)
        self.write("questions.md", GOOD_QUESTIONS)
        self.write("state.md", GOOD_STATE)
        self.write_scene("ch-07", GOOD_SCENES)
        findings = CHECKER.check(self.root)
        self.assertEqual(
            [line for line in findings if "[error]" in line], [], str(findings)
        )
        self.assertEqual(CHECKER.main([str(self.root)]), 0)

    def test_full_chapter_scene_citation_is_parsed(self):
        self.assertEqual(
            CHECKER.parse_chapter("Chapter 12: Scene where Sera opens the letter"),
            12,
        )

    def test_dead_character_in_present_is_an_error_but_mentions_pass(self):
        self.write("state.md", GOOD_STATE)
        self.write_scene(
            "ch-07",
            GOOD_SCENES.replace("Sera, Kell | Mentor", "Sera, Kell, Mentor | —"),
        )
        findings = CHECKER.check(self.root)
        self.assertIn(
            "- [error] scenes ch7: \"mentor\" is Present after death in Ch 6; "
            "move the appearance to Mentions",
            findings,
        )
        self.assertNotIn(
            "- [error] scenes ch7: \"sera\" is Present after death",
            findings,
        )

    def test_promise_lifecycle_violations(self):
        self.write("state.md", GOOD_STATE)
        self.write(
            "promises.md",
            "| Promise | Status | Planted | Payoff | POV knows | Evidence |\n"
            "|---|---|---|---|---|---|\n"
            "| Early payoff | paid-off | Ch 5 | Ch 4 | reader | broken |\n"
            "| No plant | planted | — | — | reader | broken |\n"
            "| Paid off without plant | paid-off | — | Ch 6 | reader | broken |\n"
            "| No payoff | paid-off | Ch 2 | — | reader | broken |\n"
            "| Odd status | forgotten | Ch 2 | Ch 3 | reader | broken |\n"
            "| planned drift | planned | Ch 2 | — | reader | broken |\n"
            "| Chekhov | planted | Ch 2 | — | reader | broken |\n",
        )
        findings = CHECKER.check(self.root)
        self.assertIn(
            "- [error] promises: \"Early payoff\" payoff Ch 4 precedes planted Ch 5",
            findings,
        )
        self.assertIn(
            "- [error] promises: \"No plant\" is planted but has no planted chapter",
            findings,
        )
        self.assertIn(
            "- [error] promises: \"Paid off without plant\" is paid-off but has no planted chapter",
            findings,
        )
        self.assertIn(
            "- [error] promises: \"No payoff\" is paid-off but has no payoff chapter",
            findings,
        )
        self.assertIn(
            "- [error] promises: \"Odd status\" has unknown status \"forgotten\"",
            findings,
        )
        self.assertIn(
            "- [warning] promises: \"planned drift\" is still planned but planted in Ch 2",
            findings,
        )
        self.assertIn(
            "- [warning] promises: \"Chekhov\" planted in Ch 2 with no payoff for 5 chapters",
            findings,
        )

    def test_question_lifecycle_violations(self):
        self.write("state.md", GOOD_STATE)
        self.write(
            "questions.md",
            "| Question | Status | Introduced | Answered | Evidence |\n"
            "|---|---|---|---|---|\n"
            "| Early answer | answered | Ch 5 | Ch 4 | broken |\n"
            "| Missing answer | answered | Ch 2 | — | broken |\n"
            "| Answered without introduction | answered | — | Ch 4 | broken |\n"
            "| Partial without introduction | partially-answered | — | Ch 4 | broken |\n"
            "| Open with answer | open | Ch 2 | Ch 5 | broken |\n"
            "| Future question | open | Ch 9 | — | broken |\n",
        )
        findings = CHECKER.check(self.root)
        self.assertIn(
            "- [error] questions: \"Early answer\" answered Ch 4 precedes introduced Ch 5",
            findings,
        )
        self.assertIn(
            "- [error] questions: \"Missing answer\" is answered but has no answered chapter",
            findings,
        )
        self.assertIn(
            "- [error] questions: \"Answered without introduction\" is answered "
            "but has no introduced chapter",
            findings,
        )
        self.assertIn(
            "- [error] questions: \"Partial without introduction\" is "
            "partially-answered but has no introduced chapter",
            findings,
        )
        self.assertIn(
            "- [warning] questions: \"Open with answer\" is open but answered in Ch 5",
            findings,
        )
        self.assertIn(
            "- [error] questions: \"Future question\" introduced in Ch 9 "
            "beyond current-chapter 7",
            findings,
        )

    def test_completion_gate_rejects_open_promises_and_questions(self):
        self.write("promises.md", GOOD_PROMISES)
        self.write("questions.md", GOOD_QUESTIONS)
        self.write("state.md", GOOD_STATE.replace("story-status: draft", "story-status: complete"))
        findings = CHECKER.check(self.root)
        self.assertIn(
            "- [error] promises: \"The harbor signal is answered\" is planted "
            "but the story is complete",
            findings,
        )
        self.assertIn(
            "- [error] questions: \"Who paid the smugglers?\" is open but the story is complete",
            findings,
        )

    def test_state_horizon_and_knowledge_checks(self):
        self.write("state.md", GOOD_STATE)
        self.write_scene("ch-07", GOOD_SCENES)
        self.write(
            "state.md",
            GOOD_STATE.replace("current-chapter: 7", "current-chapter: 12"),
        )
        findings = CHECKER.check(self.root)
        self.assertIn(
            "- [warning] state: current-chapter 12 is ahead of latest scene record "
            "ch-07; scene records are stale",
            findings,
        )
        self.write(
            "state.md",
            GOOD_STATE.replace(
                "| Kell | the crossing route | Ch 7 |",
                "| Kell | the crossing route | Ch 9 |",
            ),
        )
        findings = CHECKER.check(self.root)
        self.assertIn(
            "- [error] state: \"Kell\" learned a fact in Ch 9 beyond current-chapter 7",
            findings,
        )

    def test_timeline_anchor_and_order_checks(self):
        self.write("state.md", GOOD_STATE)
        self.write(
            "timeline.md",
            GOOD_TIMELINE.replace(
                "| Day 3, morning | Kell signals the harbor | kell-thread | strait-crossing | Ch 7 |",
                "| Day 3, midday | Kell signals the harbor | kell-thread | strait-crossing | Ch 8 |",
            ),
        )
        findings = CHECKER.check(self.root)
        self.assertIn(
            "- [warning] timeline: anchor \"strait-crossing\" mixes When values "
            "['Day 3, midday', 'Day 3, morning']",
            findings,
        )
        self.assertIn(
            "- [error] timeline: anchor \"strait-crossing\" spans chapters ['7', '8']",
            findings,
        )

    def test_character_subtimeline_anchor_conflicts_with_master_timeline(self):
        self.write("timeline.md", GOOD_TIMELINE)
        self.write(
            "characters/kell.md",
            "# Kell\n\n"
            "## Timeline\n\n"
            "| When | Event | Threads | Anchor | Chapter |\n"
            "|---|---|---|---|---|\n"
            "| Day 3, midday | Kell signals the harbor | kell-thread | "
            "strait-crossing | Ch 8 |\n",
        )
        findings = CHECKER.check(self.root)
        self.assertIn(
            "- [warning] timeline: anchor \"strait-crossing\" mixes When values "
            "['Day 3, midday', 'Day 3, morning']",
            findings,
        )
        self.assertIn(
            "- [error] timeline: anchor \"strait-crossing\" spans chapters ['7', '8']",
            findings,
        )

    def test_scene_anchor_must_exist_in_timeline(self):
        self.write("state.md", GOOD_STATE)
        self.write("timeline.md", GOOD_TIMELINE)
        self.write_scene(
            "ch-07", GOOD_SCENES.replace("strait-crossing", "harbor-raid")
        )
        findings = CHECKER.check(self.root)
        self.assertIn(
            "- [warning] scenes ch7: anchor \"harbor-raid\" is not in timeline.md",
            findings,
        )

    def test_pov_not_in_present_is_a_warning(self):
        self.write("state.md", GOOD_STATE)
        self.write_scene(
            "ch-07", GOOD_SCENES.replace("Sera, Kell | Mentor", "Kell | Mentor")
        )
        findings = CHECKER.check(self.root)
        self.assertIn(
            "- [warning] scenes ch7: POV \"Sera\" is not in Present", findings
        )

    def test_missing_records_report_warning_without_errors(self):
        findings = CHECKER.check(self.root)
        self.assertEqual(
            findings,
            ["- [warning] records: no continuity records found under plot/ or kb/"],
        )
        self.assertEqual(CHECKER.main([str(self.root)]), 0)

    def test_partial_record_set_is_an_error(self):
        self.write("timeline.md", "# Timeline\n")
        findings = CHECKER.check(self.root)
        self.assertEqual(
            [
                "- [error] records: missing promises.md",
                "- [error] records: missing questions.md",
                "- [error] records: missing state.md",
                "- [error] records: missing scenes/",
            ],
            [line for line in findings if "[error] records:" in line],
        )
        self.assertEqual(CHECKER.main([str(self.root)]), 1)

    def test_plot_layout_is_discovered(self):
        plot = self.root / "plot"
        scenes = plot / "scenes"
        scenes.mkdir(parents=True)
        for name, text in (
            ("timeline.md", GOOD_TIMELINE),
            ("promises.md", GOOD_PROMISES),
            ("questions.md", GOOD_QUESTIONS),
            ("state.md", GOOD_STATE),
        ):
            (plot / name).write_text(text, encoding="utf-8")
        (scenes / "ch-07.md").write_text(GOOD_SCENES, encoding="utf-8")
        findings = CHECKER.check(self.root)
        self.assertEqual([line for line in findings if "[error]" in line], [])

    def test_records_in_both_layout_roots_are_an_error(self):
        self.write("timeline.md", GOOD_TIMELINE)
        plot = self.root / "plot"
        plot.mkdir()
        (plot / "timeline.md").write_text(GOOD_TIMELINE, encoding="utf-8")
        findings = CHECKER.check(self.root)
        expected = (
            "- [error] records: both plot/ and kb/ contain continuity records; "
            + "configure exactly one continuity root in the project instructions"
        )
        self.assertEqual(
            findings,
            [expected],
        )
        self.assertEqual(CHECKER.main([str(self.root)]), 1)


if __name__ == "__main__":
    unittest.main()
