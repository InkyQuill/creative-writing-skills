from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = (
    REPO_ROOT
    / "plugins"
    / "creative-writing-skills"
    / "skills"
    / "pocket-editor-review"
    / "SKILL.md"
)


class PocketEditorReviewSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")

    def test_covers_all_six_review_surfaces(self):
        for token in (
            "`note`",
            "`change_required`",
            "`warning`",
            "`review`",
            "`edits[]`",
            "`chapter_note`",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.text)

    def test_consumes_only_decided_items_and_deletes_empty_sidecars(self):
        self.assertIn("Use the record ID as identity", self.text)
        self.assertIn("**Planned but not yet applied:** keep it in the sidecar", self.text)
        self.assertIn("use `$pocket-editor-review`", self.text)
        self.assertIn("**Unresolved:** preserve it", self.text)
        self.assertIn("delete the sidecar", self.text)

    def test_registers_new_chapters_without_rewriting_existing_identity(self):
        self.assertIn("Register confirmed new\nchapters", self.text)
        self.assertIn("preserve `schema_version`, `book_id`", self.text)
        self.assertIn("assign each new chapter a fresh UUID", self.text)
        self.assertIn("never duplicate a path or ID", self.text)

    def test_is_inert_without_pocket_editor_artifacts(self):
        self.assertIn(
            "do not create Pocket\nEditor artifacts for a project that has neither a binder nor review sidecars",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()
