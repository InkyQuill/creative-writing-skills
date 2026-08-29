import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = (
    ROOT
    / "plugins"
    / "creative-writing-skills"
    / "skills"
    / "project-maintenance"
)
SKILL = SKILL_ROOT / "SKILL.md"
COMMAND_REFERENCE = SKILL_ROOT / "resources" / "command-reference.md"
AGENT_WORKFLOWS = SKILL_ROOT / "resources" / "agent-workflows.md"
RESOURCE_NAMES = (
    "command-reference.md",
    "project-contract.md",
    "agent-workflows.md",
)


def all_runtime_markdown() -> str:
    paths = [SKILL, *(SKILL_ROOT / "resources" / name for name in RESOURCE_NAMES)]
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


class ProjectMaintenanceSkillTests(unittest.TestCase):
    def test_skill_routes_to_complete_relative_resources(self):
        text = SKILL.read_text(encoding="utf-8")
        for name in RESOURCE_NAMES:
            self.assertTrue((SKILL_ROOT / "resources" / name).is_file())
            self.assertIn(f"resources/{name}", text)

    def test_skill_uses_direct_entrypoint_and_preview_before_apply(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("resources/cli/cw.py", text)
        self.assertIn("python", text.lower())
        self.assertIn("preview", text.lower())
        self.assertIn("--apply", text)

    def test_top_level_distinguishes_transaction_preview_from_context_snapshot(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?is)preview\s+every (journaled|transactional) mutation")
        self.assertRegex(text, r"(?is)context --snapshot.{0,120}without\s+`--apply`")
        self.assertNotIn("Preview every mutation first", text)

    def test_migration_preview_and_apply_include_expected_plan_hash(self):
        text = COMMAND_REFERENCE.read_text(encoding="utf-8")
        self.assertIn(
            "migrate --preview <plan.json> --expect-plan-hash <hash>", text
        )
        self.assertIn(
            "migrate --apply <plan.json> --expect-plan-hash <hash>", text
        )

    def test_migration_workflow_resolves_unresolved_and_rehashes_plan(self):
        text = AGENT_WORKFLOWS.read_text(encoding="utf-8")
        for action in ('"action": "move"', '"action": "preserve"', '"action": "merge"'):
            self.assertIn(action, text)
        self.assertIn('"content"', text)
        self.assertIn('"unresolved": []', text)
        self.assertIn("canonical_plan_hash", text)
        self.assertRegex(text, r"(?is)recomput.{0,100}plan-hash")
        self.assertNotRegex(text, r"(?i)ask the author to (edit|update).*(plan|hash)")

    def test_unknown_migration_role_can_remain_unmanaged_without_operation(self):
        text = AGENT_WORKFLOWS.read_text(encoding="utf-8")
        self.assertRegex(
            text,
            r"(?is)unknown-role.{0,220}remove.{0,100}unresolved.{0,160}no\s+operation",
        )
        self.assertRegex(text, r"(?is)unmanaged.{0,160}(do not|must not).{0,80}preserve")

    def test_contract_covers_complete_workflow_and_exit_handling(self):
        text = all_runtime_markdown()
        for phrase in (
            "check all",
            "context",
            "draft create",
            "migrate --plan",
            "history",
            "undo",
            "recover",
            "exit 0",
            "exit 1",
            "exit 2",
            "cli-doctor",
        ):
            self.assertIn(phrase, text)
        self.assertRegex(text, r"(?is)exit 1.*continue.*creative work")

    def test_contract_preserves_unknown_files_and_does_not_require_git(self):
        text = all_runtime_markdown()
        self.assertRegex(text, r"(?i)unknown files?.*(leave|remain|preserv|untouched)")
        self.assertRegex(text, r"(?i)Git (is )?optional|does not require Git")

    def test_contract_names_protected_paths_and_lifecycle_metadata(self):
        text = all_runtime_markdown()
        for protected in ("_index.md", ".creative-writing/", "base-revision"):
            self.assertIn(protected, text)
        self.assertIn("CLI-managed draft lifecycle metadata", text)
        self.assertIn("draft set-status", text)

    def test_skill_does_not_delegate_hash_or_index_work_to_author(self):
        text = all_runtime_markdown()
        self.assertNotRegex(
            text,
            r"(?i)ask the author to (edit|update|maintain|calculate).*(hash|index|base-revision)",
        )
        self.assertRegex(text, r"(?i)agent.*(hash|tag|index|base-revision|repair command)")

    def test_agent_owns_metadata_and_repair_command_selection(self):
        text = all_runtime_markdown()
        self.assertNotRegex(text, r"(?is)CLI owns.{0,120}(tags|repair commands)")
        for responsibility in ("hashes", "tags", "indexes", "base revisions"):
            self.assertRegex(text, rf"(?is)agent owns.{{0,160}}{responsibility}")
        self.assertRegex(text, r"(?is)agent owns.{0,200}repair-command (selection|choice)")

    def test_context_cache_writes_are_derived_not_journaled(self):
        text = all_runtime_markdown()
        self.assertRegex(text, r"(?is)context planning.{0,80}read-only")
        self.assertRegex(text, r"(?is)context --snapshot.{0,120}without `?--apply`?")
        self.assertRegex(text, r"(?is)clean-context.{0,180}(does not enter|outside).{0,80}transaction history")
        self.assertNotRegex(text, r"(?is)clean-context.{0,80}(previewed|journaled) transaction")

    def test_mechanical_warnings_do_not_block_unrelated_creative_work(self):
        text = all_runtime_markdown()
        self.assertRegex(
            text,
            r"(?is)(mechanical|repairable).{0,100}(never block|do not block).{0,100}(prose review|creative work)",
        )


if __name__ == "__main__":
    unittest.main()
