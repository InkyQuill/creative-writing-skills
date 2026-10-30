import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins" / "creative-writing-skills" / "skills"
CLI_ROOT = SKILLS / "project-maintenance" / "resources" / "cli"
sys.path.insert(0, str(CLI_ROOT))

from cwcli.schema import allowed_document_kind  # noqa: E402
DOMAIN_SKILLS = (
    "project-setup",
    "kb-management",
    "story-memory",
    "story-review",
    "targeted-editing",
)


def all_runtime_markdown(skill_name: str) -> str:
    skill_root = SKILLS / skill_name
    paths = sorted(skill_root.rglob("*.md"))
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


class StoryProjectIntegrationTests(unittest.TestCase):
    def test_setup_accepts_optional_tags_without_a_canonical_layout(self):
        text = all_runtime_markdown("project-setup")
        self.assertIn("flat, shared and nested", text)
        self.assertIn(".cws-layout.json", text)
        self.assertIn("no setup questionnaire, manifest, or scaffold", text)

    def test_setup_preserves_legacy_files_unless_reorganization_is_requested(self):
        text = all_runtime_markdown("project-setup")
        self.assertIn("only for a requested reorganization", text)
        self.assertIn("unknown files", text)
        self.assertIn("approval before applying", text)

    def test_domain_skills_use_project_maintenance_for_mechanical_floor(self):
        for skill_name in DOMAIN_SKILLS:
            with self.subTest(skill=skill_name):
                text = all_runtime_markdown(skill_name)
                self.assertIn("$project-maintenance", text)
        combined = "\n".join(all_runtime_markdown(name) for name in DOMAIN_SKILLS)
        self.assertRegex(combined, r"(?is)(repairable|mechanical) warnings?.{0,180}(proceed|continue).{0,180}(semantic|literary|review)")
        self.assertRegex(combined, r"(?is)required.{0,80}(target|file).{0,100}(unreadable|cannot be read).{0,160}(only|stop)")

    def test_story_memory_owns_canonical_continuity_records(self):
        text = all_runtime_markdown("story-memory")
        self.assertIn("kb/continuity/timeline.md", text)
        self.assertIn("kb/continuity/promises.md", text)
        self.assertIn("kb/continuity/questions.md", text)
        self.assertIn("kb/continuity/state.md", text)
        self.assertIn("kb/continuity/scenes/", text)
        self.assertIn("cw check continuity", text)
        self.assertRegex(text, r"(?is)(author|direct).{0,80}edits?.{0,120}(valid|tolerat|preserv)")

    def test_story_memory_tree_uses_selected_artifact_roots(self):
        text = all_runtime_markdown("story-memory")
        for path in ("kb/continuity/", "cw get-folder <role>", ".cws-layout.json"):
            self.assertIn(path, text)
        self.assertNotRegex(text, r"(?is)(selected|configured|swappable).{0,100}continuity root")

    def test_story_memory_tree_proposes_then_transacts_kb_promotion(self):
        text = all_runtime_markdown("story-memory")
        self.assertNotIn("Fact extraction writes", text)
        self.assertNotRegex(text, r"(?is)then write the chapter's scene record")
        extraction = (SKILLS / "story-memory/resources/fact-extraction.md").read_text()
        self.assertIn("## Prepare the Promotion Proposal", extraction)
        self.assertIn("$kb-management", extraction)
        self.assertIn("does not", extraction)
        self.assertIn("independently authorize file changes", extraction)
        kb = all_runtime_markdown("kb-management")
        self.assertIn("## Promotion Uses a Separate Reviewed Update", kb)
        self.assertIn("cw undo", kb)

    def test_story_memory_does_not_require_redundant_promotion_approval(self):
        extraction = (SKILLS / "story-memory/resources/fact-extraction.md").read_text()
        self.assertIn("$kb-management", extraction)
        kb = re.sub(r"\s+", " ", all_runtime_markdown("kb-management").lower())
        self.assertIn("draft acceptance changes manuscript state only", kb)
        self.assertIn("separate update does not mean separate confirmation", kb)
        self.assertIn("ask only when", kb)
        self.assertIn("keep those items provisional", kb)

    def test_kb_paths_match_schema_v1_allowed_locations(self):
        text = all_runtime_markdown("kb-management")
        allowed_paths = (
            "kb/vocab.md",
            "kb/characters/<name>.md",
            "kb/world/<topic>.md",
            "kb/canon/<chapter-or-arc>.md",
            "kb/styles/<style-name>.md",
            "kb/samples/<sample-name>.md",
            "kb/issues/<issue-name>.md",
            "kb/continuity/timeline.md",
        )
        for path in allowed_paths:
            with self.subTest(path=path):
                self.assertIn(path, text)
                concrete = path.replace("<name>", "sera").replace("<topic>", "harbor")
                concrete = concrete.replace("<chapter-or-arc>", "chapter-1")
                concrete = concrete.replace("<style-name>", "narrator")
                concrete = concrete.replace("<sample-name>", "sample-1")
                concrete = concrete.replace("<issue-name>", "pacing")
                self.assertIsNotNone(allowed_document_kind(concrete))
        self.assertNotIn("kb/world/<domain>/", text)
        self.assertNotIn("kb/timeline/", text)
        self.assertIn("optional legacy scaffold examples", text)

    def test_agent_kb_writes_are_previewed_recoverable_transactions(self):
        text = all_runtime_markdown("kb-management")
        self.assertIn("For ordinary files, use safe named edits", text)
        self.assertIn("For applicable managed operations", text)
        self.assertIn("cw undo", text)
        self.assertRegex(text, r"(?is)author direct edits?.{0,120}(valid|authoritative)")

    def test_review_prepares_context_and_continues_through_repairable_warnings(self):
        text = all_runtime_markdown("story-review")
        self.assertRegex(text, r"(?is)(context draft|prepare.{0,80}context).{0,300}(review|critique)")
        self.assertRegex(text, r"(?is)repairable warnings?.{0,180}(proceed|continue).{0,100}review")

    def test_targeted_edits_preview_exact_or_batch_operations_and_can_undo(self):
        editing = all_runtime_markdown("targeted-editing")
        self.assertIn("$project-maintenance", editing)
        self.assertIn("only then", editing)
        operations = (SKILLS / "project-maintenance/resources/agent-workflows.md").read_text()
        self.assertRegex(operations, r"(?is)literary scope.{0,100}exact-anchor.{0,80}batch")
        self.assertRegex(operations, r"(?is)repeated match.{0,100}expected-count assertion")
        self.assertRegex(operations, r"(?is)preview the complete.{0,180}before apply")
        self.assertIn("cw undo <transaction-id>", operations)
        self.assertIn("unjournaled", operations)

    def test_acceptance_and_kb_sync_use_separate_transactions_not_blanket_confirmation(self):
        review = (SKILLS / "story-review/SKILL.md").read_text()
        self.assertIn("$kb-management", review)
        kb = re.sub(r"\s+", " ", all_runtime_markdown("kb-management").lower())
        for boundary in ("draft acceptance changes manuscript state only", "directly and unambiguously establishes", "separate update does not mean separate confirmation", "previewed, recoverable", "reviewed named edit", "ask only when"):
            self.assertIn(boundary, kb)

    def test_routed_workflows_reject_delayed_and_blanket_confirmation_gates(self):
        brainstorming = (SKILLS / "story-planning/resources/brainstorming.md").read_text()
        world = (SKILLS / "world-creation/SKILL.md").read_text()
        for text in (brainstorming, world):
            self.assertIn("$kb-management", text)
        kb = re.sub(r"\s+", " ", all_runtime_markdown("kb-management").lower())
        self.assertIn("before the next dependent question", kb)
        self.assertIn("documentation is in scope", kb)
        command_reference = (SKILLS / "project-maintenance/resources/command-reference.md").read_text()
        self.assertNotIn("separate author-confirmed decisions", command_reference)
        self.assertRegex(command_reference, r"(?is)separate KB transaction.{0,120}(does not|is not).{0,100}separate approval")

    def test_author_is_never_asked_to_maintain_cli_metadata(self):
        text = "\n".join(all_runtime_markdown(name) for name in DOMAIN_SKILLS)
        self.assertNotRegex(
            text,
            r"(?is)(?<!never )ask (?:the )?author to.{0,120}(sha|hash|index|base[- ]revision|migration mechanics)",
        )
        for responsibility in ("hashes", "indexes", "base revisions", "migration mechanics"):
            self.assertRegex(text, rf"(?is)agent owns.{{0,220}}{re.escape(responsibility)}")


if __name__ == "__main__":
    unittest.main()
