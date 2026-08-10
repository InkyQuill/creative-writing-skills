import unittest

from scripts.distribution import SKILLS_ROOT


class WorldCreationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = (SKILLS_ROOT / "world-creation" / "SKILL.md").read_text()

    def test_both_project_layouts_are_named(self):
        for path in (
            "worldbuilding/",
            "kb/world/",
            "characters/",
            "kb/characters/",
            "chapters/",
            "story/",
            "drafts/",
            "work/drafts/",
            "plot/",
            "work/outline/",
        ):
            with self.subTest(path=path):
                self.assertIn(f"`{path}`", self.skill)

    def test_prose_is_read_only_and_canonization_requires_confirmation(self):
        self.assertRegex(self.skill, r"(?i)chapters.*read-only")
        self.assertRegex(self.skill, r"(?i)story.*read-only")
        self.assertRegex(self.skill, r"(?i)draft.*read-only")
        self.assertRegex(self.skill, r"(?i)confirmation.*canon")

    def test_unsupported_per_skill_interface_file_is_absent(self):
        self.assertFalse(
            (SKILLS_ROOT / "world-creation" / "agents" / "openai.yaml").exists()
        )


if __name__ == "__main__":
    unittest.main()
