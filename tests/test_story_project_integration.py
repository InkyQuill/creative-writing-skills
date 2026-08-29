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
    def test_setup_has_one_canonical_layout(self):
        text = all_runtime_markdown("project-setup")
        self.assertNotIn("Layout A", text)
        self.assertNotIn("Layout B", text)
        self.assertIn("cw init", text)
        for path in ("project.md", "story/chapters/", "work/drafts/", "kb/continuity/"):
            self.assertIn(path, text)
        self.assertRegex(text, r"(?is)body of.{0,80}`project\.md`.{0,180}(durable|writing contract)")
        self.assertRegex(text, r"(?is)(AGENTS\.md|platform instruction).{0,180}(unmanaged|optional)")
        self.assertNotRegex(text, r"(?is)(working|durable|project-specific) `AGENTS\.md`")

    def test_setup_routes_legacy_content_through_reviewed_migration_preview(self):
        text = all_runtime_markdown("project-setup")
        self.assertIn("cw migrate --plan", text)
        self.assertRegex(text, r"(?is)recognized legacy.{0,500}preview")
        self.assertRegex(
            text,
            r"(?is)(?:apply.{0,120}only after.{0,120}(?:confirm|approv)|(?:confirm|approv).{0,120}before.{0,120}apply)",
        )
        self.assertRegex(text, r"(?is)(unknown files?|unmanaged).{0,120}(preserv|untouched|remain)")

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

    def test_story_memory_tree_uses_only_canonical_artifact_roots(self):
        text = all_runtime_markdown("story-memory")
        for path in ("kb/continuity/", "work/plans/", "work/reviews/"):
            self.assertIn(path, text)
        for rejected in ("plot/", "work/outline/", "work/critique-reports/"):
            self.assertNotIn(rejected, text)
        self.assertNotRegex(text, r"(?is)(selected|configured|swappable).{0,100}continuity root")

    def test_story_memory_tree_proposes_then_transacts_kb_promotion(self):
        text = all_runtime_markdown("story-memory")
        self.assertNotIn("Fact extraction writes", text)
        self.assertNotRegex(text, r"(?is)then write the chapter's scene record")
        self.assertNotRegex(text, r"(?is)when a work item completes, promote")
        self.assertRegex(text, r"(?is)fact extraction.{0,220}proposal")
        self.assertRegex(text, r"(?is)acceptance.{0,180}(does not|never).{0,160}(promot|KB write)")
        self.assertRegex(text, r"(?is)promotion.{0,240}separate author confirmation")
        self.assertRegex(text, r"(?is)promotion.{0,320}previewed,?\s+recoverable.{0,160}\$project-maintenance.{0,120}transaction")
        self.assertIn("cw undo", text)

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
        self.assertRegex(text, r"(?is)local\s+instructions.{0,120}(cannot|do not).{0,80}(customize|change).{0,80}managed")

    def test_agent_kb_writes_are_previewed_recoverable_transactions(self):
        text = all_runtime_markdown("kb-management")
        self.assertRegex(text, r"(?is)(agent|muse).{0,160}(never|must not).{0,100}unjournaled direct write")
        self.assertRegex(text, r"(?is)(agent|muse).{0,180}KB (mutation|edit).{0,220}preview.{0,180}(transaction|apply)")
        self.assertIn("cw undo", text)
        self.assertRegex(text, r"(?is)author direct edits?.{0,120}(valid|authoritative)")

    def test_review_prepares_context_and_continues_through_repairable_warnings(self):
        text = all_runtime_markdown("story-review")
        self.assertRegex(text, r"(?is)(context draft|prepare.{0,80}context).{0,300}(review|critique)")
        self.assertRegex(text, r"(?is)repairable warnings?.{0,180}(proceed|continue).{0,100}review")

    def test_targeted_edits_preview_exact_or_batch_operations_and_can_undo(self):
        text = all_runtime_markdown("targeted-editing")
        self.assertRegex(text, r"(?is)literary scope.{0,300}(exact[- ]anchor|exact anchor)")
        self.assertRegex(text, r"(?is)(exact[- ]anchor|exact anchor).{0,200}batch")
        self.assertRegex(text, r"(?is)repeated match.{0,180}(assert|expected count|explicit count)")
        self.assertRegex(text, r"(?is)preview.{0,300}(apply|--apply)")
        self.assertIn("cw undo", text)

    def test_acceptance_and_kb_promotion_remain_separate_confirmations(self):
        text = all_runtime_markdown("kb-management") + all_runtime_markdown("story-review")
        self.assertRegex(text, r"(?is)accept.{0,180}does not.{0,100}(KB|knowledge base)")
        self.assertRegex(text, r"(?is)KB promotion.{0,180}separate.{0,120}(author confirmation|confirmed decision)")
        self.assertRegex(text, r"(?is)(promotion transaction|promot).{0,220}(provenance|source|evidence)")

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
