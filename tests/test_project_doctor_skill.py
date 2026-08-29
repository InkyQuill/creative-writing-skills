import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = (
    ROOT
    / "plugins"
    / "creative-writing-skills"
    / "skills"
    / "project-doctor"
)
SKILL = SKILL_ROOT / "SKILL.md"
REPAIR_POLICY = SKILL_ROOT / "resources" / "repair-policy.md"


def all_runtime_markdown() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in (SKILL, REPAIR_POLICY)
    )


class ProjectDoctorSkillTests(unittest.TestCase):
    def test_skill_has_valid_identity_and_routes_to_repair_policy(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^---\nname: project-doctor\ndescription: .+\n---$")
        self.assertTrue(REPAIR_POLICY.is_file())
        self.assertIn("resources/repair-policy.md", text)

    def test_doctor_skill_requires_read_only_diagnosis_before_repairs(self):
        text = all_runtime_markdown()
        self.assertIn("cw doctor --format json", text)
        self.assertRegex(text, r"(?is)read-only.{0,160}(before|first).{0,200}repair")
        self.assertRegex(text, r"(?is)preview.{0,160}--apply")
        self.assertRegex(text, r"(?is)(no|never).{0,100}(hidden|implicit).{0,80}repair")

    def test_incomplete_transactions_are_the_first_priority(self):
        text = all_runtime_markdown()
        self.assertRegex(
            text,
            r"(?is)(first|highest|top) priority.{0,180}(incomplete transaction|recovery blocker)",
        )

    def test_semantic_contradictions_are_not_autofixed(self):
        text = all_runtime_markdown()
        self.assertRegex(text, r"(?is)semantic (contradiction|retcon).{0,100}(never|do not).{0,60}auto")
        self.assertRegex(text, r"(?is)route.{0,100}owning domain skill")
        self.assertRegex(
            text,
            r"(?is)ask.{0,80}(content|canon) question.{0,140}(different answers|answer changes).{0,80}canon",
        )

    def test_material_summary_reports_exact_next_actions(self):
        text = all_runtime_markdown()
        self.assertRegex(text, r"(?is)summarize only material findings")
        self.assertRegex(text, r"(?is)exact next action")
        self.assertRegex(text, r"(?is)next action.{0,180}(command|skill|question)")

    def test_safe_mechanical_repair_is_agent_owned_and_previewed(self):
        text = all_runtime_markdown()
        self.assertIn("$project-maintenance", text)
        self.assertRegex(text, r"(?is)agent.{0,100}(handle|perform|apply).{0,100}safe mechanical")
        self.assertRegex(text, r"(?is)preview.{0,160}--apply")
        self.assertNotRegex(text, r"(?i)ask the author to fix (the )?project")

    def test_repairs_execute_structured_argv_without_shell_interpolation(self):
        text = all_runtime_markdown()
        for field in ('"groups"', '"commands"', '"argv"'):
            self.assertIn(field, text)
        self.assertRegex(
            text,
            r"(?is)groups.{0,120}ordered.{0,80}commands.{0,180}commands\[\*\]\.argv",
        )
        self.assertRegex(text, r"(?is)execute.{0,100}argv.{0,120}(directly|argument vector)")
        self.assertRegex(text, r"(?is)(without|never use).{0,80}shell interpolation")

    def test_display_and_next_action_are_reporting_text_only(self):
        text = all_runtime_markdown()
        self.assertRegex(
            text,
            r"(?is)display.{0,120}next_action.{0,160}reporting\s+text only",
        )
        self.assertRegex(
            text,
            r"(?is)(never|do not).{0,120}(execute|shell).{0,120}(display|next_action)",
        )

    def test_each_group_runs_preview_before_matching_apply_argv(self):
        text = all_runtime_markdown()
        self.assertRegex(
            text,
            r"(?is)(for each|each repair) group.{0,220}preview.{0,160}(matching|corresponding).{0,80}apply",
        )
        self.assertRegex(
            text,
            r"(?is)recovery.{0,240}commands\[\*\]\.argv.{0,180}preview.{0,160}apply",
        )

    def test_cosmetic_drift_does_not_block_unrelated_creative_work(self):
        text = all_runtime_markdown()
        self.assertRegex(
            text,
            r"(?is)(cosmetic|repairable) drift.{0,160}(does not|never).{0,40}block.{0,100}(unrelated )?creative\s+work",
        )
        self.assertIn("continue", text.lower())

    def test_cli_failures_route_to_canonical_cli_doctor_skill(self):
        text = all_runtime_markdown()
        self.assertIn("$cli-doctor", text)
        self.assertNotRegex(text, r"(?<!\$)cli-doctor workflow")


if __name__ == "__main__":
    unittest.main()
