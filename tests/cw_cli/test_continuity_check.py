import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.cw_cli import helpers  # noqa: F401
from cwcli import app
from cwcli.checks import continuity
from cwcli.findings import Finding


TIMELINE = """# Timeline

## Story

| When | Event | Threads | Anchor | Chapter |
|---|---|---|---|---|
| Day 2 | Second | main | shared | Ch 2 |
| Day 1 | First | main | shared | Ch 1 |
"""

STATE = """# State
current-chapter: 7
story-status: draft

| Character | Location | Status | Injuries | Relationships |
|---|---|---|---|---|
| mara | tower | deceased (Ch 2) | — | — |
| ivo | quay | alive | — | — |

| Character | Fact | Learned in |
|---|---|---|
| ivo | the gate code | Ch 9 |
"""

PROMISES = """| Promise | Status | Planted | Payoff | POV knows | Evidence |
|---|---|---|---|---|---|
| early | paid-off | Ch 5 | Ch 4 | reader | explicit |
| no plant | planted | — | — | reader | explicit |
| paid no plant | paid-off | — | Ch 6 | reader | explicit |
| no payoff | paid-off | Ch 2 | — | reader | explicit |
| odd | forgotten | Ch 2 | Ch 3 | reader | explicit |
| drift | planned | Ch 2 | — | reader | explicit |
| chekhov | planted | Ch 2 | — | reader | explicit |
| future | paid-off | Ch 5 | Ch 9 | reader | explicit |
"""

QUESTIONS = """| Question | Status | Introduced | Answered | Evidence |
|---|---|---|---|---|
| early | answered | Ch 5 | Ch 4 | explicit |
| missing answer | answered | Ch 2 | — | explicit |
| no intro | answered | — | Ch 4 | explicit |
| partial no intro | partially-answered | — | Ch 4 | explicit |
| open answer | open | Ch 2 | Ch 5 | explicit |
| future intro | open | Ch 9 | — | explicit |
| future answer | answered | Ch 5 | Ch 9 | explicit |
| odd status | forgotten | Ch 2 | — | explicit |
"""

SCENE = """| Scene | POV | Location | Present | Mentions | Anchor | State changes |
|---|---|---|---|---|---|---|
| 1 | ivo | quay | mara | — | absent | none |
"""


class ContinuityParityTests(unittest.TestCase):
    def test_managed_kb_subtimelines_keep_stable_conflict_evidence(self):
        self.write_records()
        world = self.root / "kb/world"
        world.mkdir()
        table = "| When | Event | Threads | Anchor | Chapter |\n|---|---|---|---|---|\n"
        (world / "a.md").write_text(table + "| Day 1 | A | side | side | Ch 1 |\n", encoding="utf-8")
        (world / "b.md").write_text(table + "| Day 2 | B | side | side | Ch 2 |\n", encoding="utf-8")
        conflicts = [item for item in self.findings() if item.code == continuity.TIMELINE and "side" in item.message]
        self.assertTrue(conflicts)
        self.assertTrue(all(item.path == "kb/world/a.md" and item.line == 3 for item in conflicts))

    def test_managed_kb_subtimeline_duplicate_semantic_header_warns_stably(self):
        self.write_records()
        world = self.root / "kb/world"
        world.mkdir()
        (world / "mara.md").write_text(
            "| When | Event | Threads | Anchor | Anchor | Chapter |\n"
            "|---|---|---|---|---|---|\n"
            "| Day 1 | Arrival | main | quay | quay | Ch 1 |\n",
            encoding="utf-8",
        )

        malformed = [
            item
            for item in self.findings()
            if item.code == continuity.MALFORMED
            and item.path == "kb/world/mara.md"
        ]

        self.assertEqual(
            [(item.line, item.message) for item in malformed],
            [(1, "mara.md contains a table with unrecognized columns")],
        )

    def test_duplicate_semantic_headers_and_huge_integers_warn_without_abort(self):
        huge = "9" * 10000
        self.write_records(
            state=f"current-chapter: {huge}\n\n| Character | Character | State | Since |\n|---|---|---|---|\n| mara | mara | dead | Ch 2 |\n"
        )
        findings = self.findings()
        self.assertIn(continuity.MALFORMED, {item.code for item in findings})
        self.assertIn(continuity.PROMISE, {item.code for item in findings})

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "project.md").write_text(
            "---\nschema-version: 1\ntitle: Test\nlanguage: ru\nstatus: drafting\n---\n",
            encoding="utf-8",
        )
        self.continuity = self.root / "kb/continuity"
        self.continuity.mkdir(parents=True)
        (self.continuity / "scenes").mkdir()
        characters = self.root / "kb/characters"
        characters.mkdir()
        for identity in ("mara", "ivo"):
            (characters / f"{identity}.md").write_text(f"# {identity}\n", encoding="utf-8")

    def write_records(self, *, timeline=TIMELINE, state=STATE, promises=PROMISES,
                      questions=QUESTIONS, scene=SCENE):
        for name, text in (("timeline.md", timeline), ("state.md", state),
                           ("promises.md", promises), ("questions.md", questions)):
            (self.continuity / name).write_text(text, encoding="utf-8")
        (self.continuity / "scenes/ch-004.md").write_text(scene, encoding="utf-8")

    def findings(self):
        status, payload = self.run_cli()
        self.last_status = status
        self.assertEqual([], payload["execution_errors"])
        self.assertEqual(["continuity"], payload["checks"])
        return [Finding(**item) for item in payload["findings"]]

    def run_cli(self, *, strict: bool = False):
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = ["check", "continuity", ".", "--format", "json"]
        if strict:
            argv.append("--strict")
        status = app.run(argv, cwd=self.root, stdout=stdout, stderr=stderr)
        self.assertEqual("", stderr.getvalue())
        return status, json.loads(stdout.getvalue())

    def write_clean_records(self):
        self.write_records(
            timeline=(
                "# Timeline\n\n## Story\n\n"
                "| When | Event | Threads | Anchor | Chapter |\n"
                "|---|---|---|---|---|\n"
                "| Day 1 | Arrival | main | arrival | Ch 1 |\n"
                "| Day 4 | Crossing | main | crossing | Ch 4 |\n"
            ),
            state=(
                "current-chapter: 4\nstory-status: draft\n\n"
                "| Character | State | Since |\n|---|---|---|\n| ivo | alive | Ch 1 |\n"
            ),
            promises=(
                "| Promise | Status | Planted | Payoff | POV knows | Evidence |\n"
                "|---|---|---|---|---|---|\n"
                "| crossing | paid-off | Ch 1 | Ch 4 | reader | explicit |\n"
            ),
            questions=(
                "| Question | Status | Introduced | Answered | Evidence |\n"
                "|---|---|---|---|---|\n"
                "| route | answered | Ch 1 | Ch 4 | explicit |\n"
            ),
            scene=(
                "| Scene | POV | Location | Present | Mentions | Anchor | State changes |\n"
                "|---|---|---|---|---|---|---|\n"
                "| 1 | ivo | quay | ivo |  | crossing | none |\n"
            ),
        )

    def test_clean_project_and_exit_status_are_exact_through_public_command(self):
        self.write_clean_records()
        status, payload = self.run_cli()
        self.assertEqual(0, status)
        self.assertEqual([], payload["findings"])

    def test_full_chapter_citation_is_parsed_through_public_command(self):
        self.write_clean_records()
        (self.continuity / "promises.md").write_text(
            "| Promise | Status | Planted | Payoff | POV knows | Evidence |\n"
            "|---|---|---|---|---|---|\n"
            "| letter | paid-off | Chapter 1: Scene where it is sealed | "
            "Chapter 4: Scene where it is opened | reader | explicit |\n",
            encoding="utf-8",
        )
        status, payload = self.run_cli()
        self.assertEqual(0, status)
        self.assertEqual([], payload["findings"])

    def test_partial_records_keep_exact_public_warning_and_strict_exit(self):
        (self.continuity / "timeline.md").write_text("# Timeline\n", encoding="utf-8")
        normal_status, normal = self.run_cli()
        strict_status, strict = self.run_cli(strict=True)
        expected = [
            ("kb/continuity/promises.md", "canonical continuity record is missing"),
            ("kb/continuity/questions.md", "canonical continuity record is missing"),
            ("kb/continuity/state.md", "canonical continuity record is missing"),
        ]
        actual = sorted(
            (item["path"], item["message"])
            for item in normal["findings"]
            if item["code"] == continuity.RECORD
        )
        self.assertEqual(sorted(expected), actual)
        self.assertEqual(0, normal_status)
        self.assertEqual(1, strict_status)
        self.assertTrue(strict["strict_failure"])

    def test_legacy_plot_fixture_is_discovered_after_public_migration_targeting(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        legacy_root = Path(temporary.name)
        (legacy_root / "project.md").write_text("# Legacy\n", encoding="utf-8")
        (legacy_root / "plot").mkdir()
        (legacy_root / "plot/timeline.md").write_text("# Timeline\n", encoding="utf-8")
        stdout, stderr = io.StringIO(), io.StringIO()
        plan_status = app.run(
            ["migrate", "--plan", "--format", "json"],
            cwd=legacy_root,
            stdout=stdout,
            stderr=stderr,
        )
        self.assertEqual(0, plan_status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            {
                "action": "move",
                "destination": "kb/continuity/timeline.md",
                "source": "plot/timeline.md",
            },
            json.loads(stdout.getvalue())["operations"],
        )

        self.write_clean_records()
        status, payload = self.run_cli()
        self.assertEqual(0, status)
        self.assertEqual([], payload["findings"])

    def test_dual_legacy_roots_are_rejected_by_public_migration_plan(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "project.md").write_text("# Test\n", encoding="utf-8")
        for base in ("plot", "kb"):
            (root / base).mkdir()
            (root / base / "timeline.md").write_text("# Timeline\n", encoding="utf-8")

        stdout, stderr = io.StringIO(), io.StringIO()
        status = app.run(
            ["migrate", "--plan", "--format", "json"],
            cwd=root,
            stdout=stdout,
            stderr=stderr,
        )
        self.assertEqual(0, status)
        self.assertEqual("", stderr.getvalue())
        unresolved = json.loads(stdout.getvalue())["unresolved"]
        self.assertIn(
            {
                "destination": None,
                "reason": "mixed-layout",
                "sources": ["kb/timeline.md", "plot/timeline.md"],
            },
            unresolved,
        )

    def test_deaths_knowledge_scene_cast_and_state_horizon_keep_legacy_rules(self):
        self.write_records()
        findings = self.findings()
        codes = {item.code for item in findings}
        messages = "\n".join(item.message for item in findings)
        self.assertIn(continuity.DEATH, codes)
        self.assertIn("learned a fact in chapter 9", messages)
        self.assertIn("POV 'ivo' is not in the explicit scene cast", messages)
        self.assertIn("current-chapter 7 is ahead of latest scene record chapter 4", messages)
        death = next(item for item in findings if item.code == continuity.DEATH)
        self.assertEqual((death.path, death.line), ("kb/continuity/scenes/ch-004.md", 3))

    def test_promise_parity_covers_every_legacy_lifecycle_rule(self):
        self.write_records()
        messages = "\n".join(item.message for item in self.findings() if item.code == continuity.PROMISE)
        for fragment in (
            "payoff chapter 4 precedes planted chapter 5",
            "is planted but has no planted chapter",
            "paid no plant' is paid-off but has no planted chapter",
            "is paid-off but has no payoff chapter",
            "unknown status 'forgotten'",
            "still planned but planted in chapter 2",
            "has no payoff for 5 chapters",
            "payoff chapter 9 is beyond current-chapter 7",
        ):
            self.assertIn(fragment, messages)

    def test_question_parity_covers_every_legacy_lifecycle_rule(self):
        self.write_records()
        messages = "\n".join(item.message for item in self.findings() if item.code == continuity.QUESTION)
        for fragment in (
            "answer chapter 4 precedes introduction chapter 5",
            "is answered but has no answered chapter",
            "is answered but has no introduced chapter",
            "is partially-answered but has no introduced chapter",
            "is open but has an answer in chapter 5",
            "introduction chapter 9 is beyond current-chapter 7",
            "answer chapter 9 is beyond current-chapter 7",
            "unknown status 'forgotten'",
        ):
            self.assertIn(fragment, messages)

    def test_complete_story_rejects_open_lifecycle_records(self):
        self.write_records(
            state=STATE.replace("story-status: draft", "story-status: complete"),
            promises=PROMISES + "| final promise | planned | — | — | reader | explicit |\n",
            questions=QUESTIONS + "| final question | partially-answered | Ch 2 | Ch 3 | explicit |\n",
        )
        messages = "\n".join(item.message for item in self.findings())
        self.assertIn("final promise", messages)
        self.assertIn("final question", messages)
        self.assertGreaterEqual(messages.count("story is complete"), 2)

    def test_timeline_order_shared_anchor_conflicts_subtimeline_and_scene_anchor(self):
        self.write_records()
        (self.root / "kb/characters/ivo.md").write_text(
            "## Timeline\n\n| When | Event | Threads | Anchor | Chapter |\n"
            "|---|---|---|---|---|\n| Day 3 | Third | ivo | shared | Ch 3 |\n",
            encoding="utf-8",
        )
        messages = "\n".join(item.message for item in self.findings() if item.code == continuity.TIMELINE)
        self.assertIn("out of order", messages)
        self.assertIn("mixes When values", messages)
        self.assertIn("spans chapters", messages)
        self.assertIn("scene anchor 'absent' is not present", messages)

    def test_compact_tables_support_explicit_ids_without_prose_inference(self):
        self.write_records(
            state="| character | state | since |\n|---|---|---|\n| mara | dead | ch-002 |\n",
            scene="| chapter | cast |\n|---|---|\n| ch-004 | mara, ivo |\n",
            timeline="# Timeline\n",
            promises="# No records\n",
            questions="# No records\n",
        )
        self.assertIn(continuity.DEATH, {item.code for item in self.findings()})

        (self.continuity / "state.md").write_text(
            "Mara was dead by chapter two, perhaps only metaphorically.\n", encoding="utf-8"
        )
        self.assertNotIn(continuity.DEATH, {item.code for item in self.findings()})

    def test_unknown_ids_warn_but_do_not_abort_other_rules(self):
        self.write_records(scene=SCENE.replace("mara", "unknown"))
        findings = self.findings()
        unknown = next(item for item in findings if item.code == continuity.UNKNOWN_CHARACTER)
        self.assertEqual((unknown.path, unknown.line), ("kb/continuity/scenes/ch-004.md", 3))
        self.assertIn(continuity.PROMISE, {item.code for item in findings})

    def test_mentions_ids_are_validated_but_deceased_mentions_are_not_present(self):
        self.write_records(scene=SCENE.replace("mara | —", "ivo | mara, unknown"))
        findings = self.findings()
        self.assertFalse(any(item.code == continuity.DEATH for item in findings))
        unknown = [item for item in findings if item.code == continuity.UNKNOWN_CHARACTER]
        self.assertEqual([item.message for item in unknown], ["unknown character ID 'unknown'"])

    def test_death_state_requires_an_exact_normalized_token(self):
        for identity in ("undead", "not-dead", "deadly", "bare-number"):
            (self.root / f"kb/characters/{identity}.md").write_text("# Character\n", encoding="utf-8")
        state = """| character | state | since |
|---|---|---|
| undead | undead | Ch 2 |
| not-dead | not dead | Ch 2 |
| deadly | deadly | Ch 2 |
| bare-number | dead (2) | — |
"""
        scene = "| chapter | cast |\n|---|---|\n| Ch 4 | undead, not-dead, deadly, bare-number |\n"
        self.write_records(state=state, scene=scene)
        self.assertNotIn(continuity.DEATH, {item.code for item in self.findings()})

        (self.continuity / "state.md").write_text(
            state + "| mara | deceased (Chapter 2) | — |\n", encoding="utf-8"
        )
        (self.continuity / "scenes/ch-004.md").write_text(
            scene.replace("bare-number |", "bare-number, mara |"), encoding="utf-8"
        )
        self.assertIn(continuity.DEATH, {item.code for item in self.findings()})

    def test_unknown_id_next_action_never_interpolates_unsafe_stems(self):
        self.write_records(scene="| chapter | cast |\n|---|---|\n| Ch 4 | ../mara, CON, valid-id |\n")
        actions = {
            item.message: item.next_action
            for item in self.findings()
            if item.code == continuity.UNKNOWN_CHARACTER
        }
        self.assertNotIn("Create", actions["unknown character ID '../mara'"])
        self.assertNotIn("Create", actions["unknown character ID 'CON'"])
        self.assertIn("Create kb/characters/valid-id.md", actions["unknown character ID 'valid-id'"])

    def test_malformed_record_warns_and_other_records_complete(self):
        self.write_records(promises="| Promise | Status |\n| -- | --- |\n| x | planted |\n")
        findings = self.findings()
        malformed = next(item for item in findings if item.code == continuity.MALFORMED)
        self.assertEqual((malformed.path, malformed.line), ("kb/continuity/promises.md", 1))
        self.assertIn(continuity.QUESTION, {item.code for item in findings})

    def test_each_valid_unrecognized_and_broken_table_sequence_warns_independently(self):
        promises = (
            "| Promise | Status | Planted | Payoff | POV knows | Evidence |\n"
            "|---|---|---|---|---|---|\n| kept | planned | — | — | reader | explicit |\n\n"
            "| Unknown | Columns |\n|---|---|\n| x | y |\n\n"
            "| Broken | Columns |\n| -- | --- |\n"
        )
        self.write_records(promises=promises)
        malformed = [item for item in self.findings() if item.code == continuity.MALFORMED and
                     item.path == "kb/continuity/promises.md"]
        self.assertEqual([(item.line, item.message) for item in malformed], [
            (5, "promises.md contains a table with unrecognized columns"),
            (9, "promises.md contains a malformed or incomplete table"),
        ])

    def test_single_prose_pipe_does_not_become_a_table_warning(self):
        self.write_records(promises="A comparison of left | right in ordinary prose.\n")
        self.assertFalse(any(item.code == continuity.MALFORMED and item.path.endswith("promises.md")
                             for item in self.findings()))

    def test_symlink_scene_and_nested_project_are_not_followed(self):
        self.write_records(scene="| chapter | cast |\n|---|---|\n| ch-004 | ivo |\n")
        outside = self.root.parent / f"{self.root.name}-outside.md"
        outside.write_text("| chapter | cast |\n|---|---|\n| ch-009 | mara |\n", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        os.symlink(outside, self.continuity / "scenes/ch-009.md")
        nested = self.continuity / "scenes/nested"
        nested.mkdir()
        (nested / "project.md").write_text("nested", encoding="utf-8")
        (nested / "ch-010.md").write_text(outside.read_text(), encoding="utf-8")
        findings = self.findings()
        self.assertTrue(any(item.path == "kb/continuity/scenes/ch-009.md" and item.code == continuity.RECORD
                            for item in findings))
        self.assertFalse(any(item.path and "nested" in item.path for item in findings))
        self.assertFalse(any("latest scene record chapter 9" in item.message or
                             "latest scene record chapter 10" in item.message for item in findings))

    def test_symlinked_kb_parent_and_nested_continuity_root_are_boundaries(self):
        outside = self.root.parent / f"{self.root.name}-outside-kb"
        outside.mkdir()
        self.addCleanup(lambda: __import__("shutil").rmtree(outside, ignore_errors=True))
        (self.root / "kb/characters/mara.md").unlink()
        (self.root / "kb/characters/ivo.md").unlink()
        (self.root / "kb/characters").rmdir()
        (self.root / "kb/continuity/scenes").rmdir()
        (self.root / "kb/continuity").rmdir()
        (self.root / "kb").rmdir()
        os.symlink(outside, self.root / "kb")
        finding = self.findings()[0]
        self.assertEqual((finding.code, finding.path), (continuity.RECORD, "kb/continuity"))
        self.assertIn("symlink", finding.message)

        (self.root / "kb").unlink()
        self.continuity.mkdir(parents=True)
        (self.continuity / "project.md").write_text("nested", encoding="utf-8")
        finding = self.findings()[0]
        self.assertIn("nested project", finding.message)

    def test_intermediate_nested_project_boundary_is_not_crossed(self):
        self.write_records()
        (self.root / "kb/project.md").write_text("nested", encoding="utf-8")
        findings = self.findings()
        self.assertEqual(len(findings), 1)
        self.assertIn("nested project", findings[0].message)

    def test_state_behind_latest_scene_keeps_stale_state_branch(self):
        self.write_records(state=STATE.replace("current-chapter: 7", "current-chapter: 2"))
        messages = "\n".join(item.message for item in self.findings() if item.code == continuity.STATE)
        self.assertIn("scene records reach chapter 4 beyond current-chapter 2", messages)

    def test_missing_scenes_is_reported_without_stopping_records(self):
        self.write_records()
        (self.continuity / "scenes/ch-004.md").unlink()
        (self.continuity / "scenes").rmdir()
        findings = self.findings()
        self.assertTrue(any(item.code == continuity.RECORD and item.path == "kb/continuity/scenes"
                            for item in findings))
        self.assertIn(continuity.PROMISE, {item.code for item in findings})

    def test_missing_record_paths_are_independent_warnings(self):
        (self.continuity / "state.md").write_text("# State\n", encoding="utf-8")
        findings = self.findings()
        missing = [item for item in findings if item.code == continuity.RECORD]
        self.assertEqual({item.path for item in missing}, {
            "kb/continuity/timeline.md", "kb/continuity/promises.md", "kb/continuity/questions.md"
        })
        self.assertFalse(any(item.code == continuity.STATE for item in findings))
        self.assertTrue(all(item.next_action for item in findings))

    def test_legacy_state_shape_without_current_chapter_keeps_legacy_detection(self):
        legacy_without_horizon = STATE.replace("current-chapter: 7\n", "")
        self.write_records(state=legacy_without_horizon)
        finding = next(item for item in self.findings() if item.code == continuity.STATE and
                       "current-chapter is missing" in item.message)
        self.assertEqual(finding.severity, "error")

    def test_representative_legacy_fixture_keeps_all_detection_categories(self):
        self.write_records()
        current_codes = {item.code for item in self.findings()}
        for code in (
            continuity.STATE,
            continuity.PROMISE,
            continuity.QUESTION,
            continuity.TIMELINE,
            continuity.DEATH,
            continuity.SCENE,
        ):
            self.assertIn(code, current_codes)


if __name__ == "__main__":
    unittest.main()
