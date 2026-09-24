"""Keep author-control examples discoverable in the canonical skills."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1] / "plugins/creative-writing-skills/skills"


class AuthorWorkflowContractTests(unittest.TestCase):
    def test_shared_contract_covers_distinct_author_roles_and_one_task_override(self):
        contract = (ROOT / "project-bootstrap/resources/author-workflow-contract.md").read_text()
        for example in (
            "analysis only",
            "draft on request",
            "edit accepted prose",
            "one-task override",
            "conflicting sources",
        ):
            with self.subTest(example=example):
                self.assertIn(example, contract)

    def test_entry_skills_resolve_author_workflow_before_prose_or_file_edits(self):
        for skill in ("project-setup", "creative-writing-muse", "story-review"):
            with self.subTest(skill=skill):
                content = (ROOT / skill / "SKILL.md").read_text()
                self.assertIn("author-workflow-contract.md", content)


if __name__ == "__main__":
    unittest.main()
