import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins" / "creative-writing-skills" / "skills"
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
