import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MUSE_ROOT = (
    REPO_ROOT
    / "plugins"
    / "creative-writing-skills"
    / "skills"
    / "creative-writing-muse"
)
WORKERS_ROOT = MUSE_ROOT / "resources" / "workers"
PRESSURE_RESULTS = REPO_ROOT / "tests" / "fixtures" / "muse-pressure" / "results.md"
AFFECTED_WORKERS = {
    "continuity-checker",
    "critic",
    "editor",
    "outliner",
    "writer",
}
PROSE_WORKERS = {"continuity-checker", "critic", "editor", "writer"}


class MuseProjectWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.muse = (MUSE_ROOT / "SKILL.md").read_text()
        cls.registry = json.loads((WORKERS_ROOT / "registry.json").read_text())
        cls.entries = {item["name"]: item for item in cls.registry["workers"]}
        cls.prompts = {
            name: (WORKERS_ROOT / cls.entries[name]["prompt"]).read_text()
            for name in AFFECTED_WORKERS
        }
        cls.pressure = PRESSURE_RESULTS.read_text()

    def test_preflight_matches_exactly_the_five_owned_prompts(self):
        pattern = re.compile(
            r"project-setup|kb-management|story-memory|story-review|"
            r"targeted-editing|chapters/|drafts/|continuity_check|analyze\.py"
        )
        matches = {
            path.stem
            for path in WORKERS_ROOT.glob("*.md")
            if pattern.search(path.read_text())
        }
        self.assertEqual(matches, AFFECTED_WORKERS)

    def test_registry_resolves_owned_prompts_and_agrees_with_worker_functions(self):
        for name in AFFECTED_WORKERS:
            entry = self.entries[name]
            self.assertEqual(entry["prompt"], f"{name}.md")
            self.assertTrue((WORKERS_ROOT / entry["prompt"]).is_file())
            self.assertTrue(entry["description"].strip())
            self.assertIn("## Required inputs", self.prompts[name])
            self.assertIn("## Return shape", self.prompts[name])

    def test_muse_routes_folder_repairs_and_runtime_failures_separately(self):
        lower = self.muse.lower()
        flat = re.sub(r"\s+", " ", lower)
        self.assertIn("$project-doctor", self.muse)
        self.assertIn("$cli-doctor", self.muse)
        self.assertRegex(flat, r"safe scaffold.*index.*tag")
        self.assertRegex(flat, r"\$cli-doctor[^.]*actual cli execution failure")
        self.assertRegex(flat, r"content language")
        self.assertRegex(flat, r"not cli (?:commands|ceremony|terminology)")

    def test_muse_preserves_distinct_durable_change_boundaries(self):
        lower = self.muse.lower()
        flat = re.sub(r"\s+", " ", lower)
        for decision in (
            "migration apply",
            "draft acceptance",
            "retcon",
        ):
            with self.subTest(decision=decision):
                self.assertRegex(
                    flat,
                    rf"(?:separate|explicit)[^.]*confirmation[^.]*{decision}|"
                    rf"{decision}[^.]*(?:separate|explicit)[^.]*confirmation",
                )
        self.assertRegex(flat, r"acceptance[^.]*manuscript only")
        self.assertRegex(
            flat,
            r"directly and unambiguously established[^.]*accepted prose[^.]*"
            r"separate[^.]*previewed[^.]*recoverable[^.]*transaction",
        )
        self.assertRegex(flat, r"separate transaction[^.]*does not[^.]*separate confirmation")
        self.assertRegex(
            flat,
            r"ask[^.]*only[^.]*(?:ambiguity|ambiguous)[^.]*inference[^.]*"
            r"conflict[^.]*retcon[^.]*source tag[^.]*knowledge boundary",
        )
        self.assertNotRegex(flat, r"durable memory[^.]*after (?:the )?author accepts")

    def test_confirmed_brainstorm_answers_persist_before_the_next_question(self):
        flat = re.sub(r"\s+", " ", self.muse.lower())
        self.assertIn("interactive brainstorming", flat)
        self.assertRegex(
            flat,
            r"direct author answer.{0,180}durable fact or decision.{0,180}"
            r"persist it immediately.{0,180}before asking the next question",
        )
        self.assertRegex(flat, r"do not ask[^.]*redundant[^.]*confirmation")
        self.assertRegex(flat, r"unless[^.]*provisional[^.]*not to save")

    def test_explicit_save_instruction_confirms_promotion(self):
        flat = re.sub(r"\s+", " ", self.muse.lower())
        self.assertIn("save this secret now", flat)
        self.assertRegex(flat, r"save this secret now[^.]*confirms[^.]*promotion")
        self.assertRegex(flat, r"author-only[^.]*character[^.]*reader")

    def test_muse_uses_existing_evidence_instead_of_blanket_reconfirmation(self):
        flat = re.sub(r"\s+", " ", self.muse.lower())
        self.assertRegex(flat, r"accepted prose[^.]*prior direct author answers[^.]*evidence")
        self.assertRegex(flat, r"different answers[^.]*materially change[^.]*canon[^.]*knowledge boundaries")
        self.assertNotRegex(flat, r"(?:always|every)[^.]{0,80}(?:ask|confirm)[^.]{0,80}promotion")

    def test_prose_workers_require_prepared_context_and_explicit_draft_target(self):
        for name in PROSE_WORKERS:
            required_inputs = self.prompts[name].split("## Work", 1)[0].lower()
            with self.subTest(worker=name):
                self.assertIn("prepared context plan", required_inputs)
                self.assertIn("explicit draft target path", required_inputs)

    def test_every_owned_worker_returns_proposals_without_direct_canon_mutation(self):
        for name, prompt in self.prompts.items():
            lower = prompt.lower()
            with self.subTest(worker=name):
                self.assertRegex(lower, r"return(?:s|ed)? (?:a |only )?(?:proposal|findings)")
                self.assertIn("never directly mutate accepted manuscript or kb", lower)
                self.assertIn("never make unjournaled changes", lower)

    def test_continuity_worker_uses_canonical_bundled_check(self):
        prompt = self.prompts["continuity-checker"]
        self.assertIn("cw check continuity", prompt)
        self.assertNotIn("continuity_check.py", prompt)
        self.assertNotIn("analyze.py", prompt)

    def test_write_workers_use_canonical_work_paths(self):
        self.assertIn("`work/plans/`", self.prompts["outliner"])
        self.assertNotIn("`work/outlines/`", self.prompts["outliner"])
        self.assertIn("`work/drafts/`", self.prompts["writer"])
        self.assertIn("`story/chapters/`", self.prompts["writer"])
        for prompt in self.prompts.values():
            self.assertNotRegex(prompt, r"(?<!story/)chapters/")

    def test_final_memory_pressure_reuses_exact_prompt_and_strongest_output(self):
        revised_prompt = re.search(
            r"<!-- prompt:memory-intent/revised -->.*?```text\n(.*?)```\n",
            self.pressure,
            re.DOTALL,
        )
        sample_five = re.search(
            r"<!-- sample:memory-intent/revised/5 compliant=true -->.*?"
            r"### Output\n\n```text\n(.*?)```\n",
            self.pressure,
            re.DOTALL,
        )
        final = re.search(
            r"<!-- final:memory-intent compliant=true -->.*?"
            r"#### Full prompt\n\n```text\n(.*?)```\n.*?"
            r"#### Raw output\n\n```text\n(.*?)```\n",
            self.pressure,
            re.DOTALL,
        )
        self.assertIsNotNone(revised_prompt)
        self.assertIsNotNone(sample_five)
        self.assertIsNotNone(final)
        self.assertEqual(final.group(1), revised_prompt.group(1))
        self.assertEqual(final.group(2), sample_five.group(1))
        self.assertIn("explicit instruction confirms promotion", final.group(2))


if __name__ == "__main__":
    unittest.main()
