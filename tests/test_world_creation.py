import unittest

from scripts.distribution import SKILLS_ROOT


class WorldCreationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = (SKILLS_ROOT / "world-creation" / "SKILL.md").read_text()
        cls.file_format = (
            SKILLS_ROOT
            / "world-creation"
            / "references"
            / "world-file-format.md"
        ).read_text()

    def test_uses_only_canonical_schema_v1_artifact_roots(self):
        for path in (
            "kb/world/",
            "kb/characters/",
            "story/chapters/",
            "work/drafts/",
            "work/plans/",
        ):
            with self.subTest(path=path):
                self.assertIn(f"`{path}`", self.skill)
        for legacy_path in (
            "worldbuilding/",
            "characters/",
            "chapters/",
            "drafts/",
            "plot/",
            "work/outline/",
        ):
            with self.subTest(legacy_path=legacy_path):
                self.assertNotIn(f"`{legacy_path}`", self.skill)
        self.assertNotRegex(self.skill, r"(?is)(equal|equivalent).{0,80}(layout|convention)")

    def test_prose_is_read_only_and_direct_answers_persist_incrementally(self):
        self.assertRegex(self.skill, r"(?is)`story/chapters/`.{0,120}read-only")
        self.assertRegex(self.skill, r"(?is)`work/drafts/`.{0,120}read-only")
        self.assertIn("$project-maintenance", self.skill)
        self.assertRegex(
            self.skill,
            r"(?is)direct author answer.{0,180}settles.{0,180}"
            r"previewed, recoverable transaction.{0,180}before.{0,80}next question",
        )
        self.assertRegex(self.skill, r"(?is)unless.{0,80}provisional.{0,100}(not to save|no-save)")
        self.assertRegex(self.skill, r"(?is)do not ask.{0,80}redundant.{0,80}confirmation")
        self.assertRegex(self.skill, r"(?is)agent.{0,100}reindex")

    def test_only_material_uncertainty_requires_author_resolution(self):
        self.assertRegex(
            self.skill,
            r"(?is)ask only.{0,320}(ambigu|infer|conflict|retcon).{0,320}"
            r"(source tag|knowledge boundar)",
        )
        self.assertNotRegex(
            self.skill,
            r"(?is)(always|every|separate).{0,100}(ask|confirm).{0,100}(canon|KB)",
        )

    def test_agent_owns_index_updates_in_the_same_transaction(self):
        self.assertRegex(
            self.file_format,
            r"(?is)update the nearest relevant index.{0,180}same previewed, recoverable"
            r".{0,100}\$project-maintenance.{0,100}transaction",
        )
        self.assertRegex(self.file_format, r"(?is)agent\s+owns reindexing")
        self.assertNotRegex(
            self.file_format,
            r"(?is)after the user confirms|user confirms that an index",
        )

    def test_unsupported_per_skill_interface_file_is_absent(self):
        self.assertFalse(
            (SKILLS_ROOT / "world-creation" / "agents" / "openai.yaml").exists()
        )


if __name__ == "__main__":
    unittest.main()
