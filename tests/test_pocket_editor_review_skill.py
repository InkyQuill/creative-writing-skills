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

    def test_covers_six_signal_types_and_two_other_review_surfaces(self):
        for token in (
            "`note`",
            "`change_required`",
            "`warning`",
            "`review`",
            "`good`",
            "`brilliant`",
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

    def test_positive_feedback_capture_is_routed_and_preserves_evidence(self):
        resource = SKILL.parent / "resources" / "positive-feedback.md"
        self.assertIn("resources/positive-feedback.md", self.text)
        text = resource.read_text(encoding="utf-8")
        for boundary in (
            "## Save, Verify, Then Consume",
            "exact\n  `selected_text`",
            "comment\n  verbatim",
            "composite identity",
            "If saving or verification fails, leave the signal",
            "Read-only tasks",
            "not acceptance of its story facts",
        ):
            with self.subTest(boundary=boundary):
                self.assertIn(boundary, text)

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
