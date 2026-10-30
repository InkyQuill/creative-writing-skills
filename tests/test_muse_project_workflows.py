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
        cls.all_prompts = {
            name: (WORKERS_ROOT / entry["prompt"]).read_text()
            for name, entry in cls.entries.items()
        }
        cls.prompts = {
            name: cls.all_prompts[name]
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
        self.assertRegex(flat, r"do not create a scaffold.*index.*tags")
        self.assertRegex(flat, r"\$cli-doctor[^.]*actual cli execution failure")
        self.assertRegex(flat, r"content language")
        self.assertRegex(flat, r"not cli (?:commands|ceremony|terminology)")

    def test_muse_conditionally_routes_pocket_editor_bookkeeping(self):
        flat = re.sub(r"\s+", " ", self.muse.lower())
        for marker in ("$pocket-editor-review", ".pocket-editor.json", "*.review.json", "deferred signal-cleanup requirement", "when neither file form exists"):
            self.assertIn(marker, flat)

    def test_muse_preserves_distinct_durable_change_boundaries(self):
        flat = re.sub(r"\s+", " ", self.muse.lower())
        for decision in ("draft acceptance", "migration apply", "retcon"):
            self.assertIn(decision, flat)
        self.assertIn("explicit authorization for one does not authorize the others", flat)
        self.assertIn("$kb-management", flat)
        kb = (MUSE_ROOT.parent / "kb-management/SKILL.md").read_text().lower()
        for boundary in ("manuscript state only", "separate update does not mean separate confirmation", "inference", "knowledge boundary"):
            self.assertIn(boundary, re.sub(r"\s+", " ", kb))

    def test_confirmed_brainstorm_answers_persist_before_the_next_question(self):
        self.assertIn("$kb-management", self.muse)
        kb = re.sub(r"\s+", " ", (MUSE_ROOT.parent / "kb-management/SKILL.md").read_text().lower())
        self.assertIn("direct author answer settling a durable fact is confirmation", kb)
        self.assertIn("documentation is in scope", kb)
        self.assertIn("before the next dependent question", kb)
        self.assertIn("unless marked provisional or not to be saved", kb)

    def test_explicit_save_instruction_confirms_promotion(self):
        kb = re.sub(r"\s+", " ", (MUSE_ROOT.parent / "kb-management/SKILL.md").read_text().lower())
        self.assertIn("save now", kb)
        self.assertIn("needs no second approval", kb)
        self.assertIn("do not create a second account or expose hidden facts", kb)

    def test_muse_uses_existing_evidence_instead_of_blanket_reconfirmation(self):
        self.assertIn("$kb-management", self.muse)
        kb = re.sub(r"\s+", " ", (MUSE_ROOT.parent / "kb-management/SKILL.md").read_text().lower())
        self.assertIn("direct author answer", kb)
        self.assertIn("re-read the prose", kb)
        self.assertIn("directly and unambiguously establishes", kb)
        self.assertIn("ask only when", kb)

    def test_prose_workers_support_inline_tasks_and_scoped_context(self):
        for name in PROSE_WORKERS:
            required_inputs = self.prompts[name].split("## Work", 1)[0].lower()
            with self.subTest(worker=name):
                self.assertIn("relevant prepared context", required_inputs)
                self.assertNotIn("explicit draft target path", required_inputs)
                self.assertIn("inline task", required_inputs)
        self.assertIn("draft target path only if writing a file", self.prompts["writer"])

    def test_every_owned_worker_returns_proposals_without_direct_canon_mutation(self):
        for name, prompt in self.prompts.items():
            lower = prompt.lower()
            with self.subTest(worker=name):
                self.assertRegex(lower, r"return(?:s|ed)? (?:a |only )?(?:proposal|findings)")
                self.assertIn("never directly mutate accepted manuscript or kb", lower)
                if self.entries[name]["access"] == "workspace-write":
                    self.assertIn("ordinary named edits need no scaffold", lower)

    def test_every_registry_workspace_write_worker_has_full_mutation_boundary(self):
        write_workers = {
            name
            for name, entry in self.entries.items()
            if entry["access"] == "workspace-write"
        }
        self.assertEqual(
            write_workers,
            {"brainstormer", "outliner", "style-creator", "web-researcher", "writer"},
        )
        for name in write_workers:
            lower = re.sub(r"\s+", " ", self.all_prompts[name].lower())
            with self.subTest(worker=name):
                self.assertRegex(
                    lower,
                    r"(?:(?:proposal|work output).{0,80}only|"
                    r"only.{0,80}(?:proposal|work output))",
                )
                self.assertRegex(lower, r"caller-assigned.{0,60}paths?")
                self.assertRegex(lower, r"selected (?:plans|drafts|reviews|brainstorm) folder|work/report|author.s chosen (?:layout|location)")
                self.assertIn("never directly mutate accepted manuscript or kb", lower)
                if self.entries[name]["access"] == "workspace-write":
                    self.assertIn("ordinary named edits need no scaffold", lower)

    def test_report_workers_preserve_named_write_scope_in_any_layout(self):
        for name in ("style-creator", "web-researcher"):
            lower = re.sub(r"\s+", " ", self.all_prompts[name].lower())
            with self.subTest(worker=name):
                self.assertIn("caller-assigned paths", lower)
                self.assertIn("assigned exact path", lower)
                self.assertIn("flat or nested folder", lower)
                self.assertIn("do not touch other paths", lower)

    def test_continuity_worker_uses_canonical_bundled_check(self):
        prompt = self.prompts["continuity-checker"]
        self.assertIn("cw check continuity", prompt)
        self.assertNotIn("continuity_check.py", prompt)
        self.assertNotIn("analyze.py", prompt)

    def test_write_workers_use_selected_work_paths(self):
        self.assertIn("cw get-folder plans", self.prompts["outliner"])
        self.assertIn("cw get-folder", self.prompts["writer"])
        self.assertIn("author's chosen layout", self.prompts["writer"])

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
        self.assertIn(
            "This is a settled decision, not a provisional option",
            revised_prompt.group(1),
        )
        self.assertNotRegex(revised_prompt.group(1).lower(), r"\bsave\b.{0,40}\bnow\b")

        revised_outputs = re.findall(
            r"<!-- sample:memory-intent/revised/[1-5] compliant=true -->.*?"
            r"### Output\n\n```text\n(.*?)```\n",
            self.pressure,
            re.DOTALL,
        )
        self.assertEqual(len(revised_outputs), 5)
        for output in revised_outputs:
            self.assertRegex(
                output,
                r"(?is)durable story memory:.{0,180}immediately record",
            )
        self.assertRegex(
            final.group(2),
            r"(?is)do not wait for drafting or ask for redundant confirmation",
        )


if __name__ == "__main__":
    unittest.main()
