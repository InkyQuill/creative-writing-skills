import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from scripts.vendor_generic_skills import (
    SOURCE,
    VendorDriftError,
    _replace_directory,
    check_checkout,
    normalize_codex_references,
    render_from_checkout,
)


class VendorGenericSkillsTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.checkout = self.root / "checkout"
        self.output = self.root / "output"
        skill = self.checkout / "cw" / "skills" / "demo"
        (skill / "resources").mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: demo\n---\n\n# Demo\n")
        (skill / "resources" / "guide.md").write_text("Guide\n")
        self.vendored_skills = patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("demo",),
        )
        self.vendored_skills.start()
        self.addCleanup(self.vendored_skills.stop)
        self.canonical_skills = patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"demo"},
        )
        self.canonical_skills.start()
        self.addCleanup(self.canonical_skills.stop)

    def test_render_copies_complete_skill_directory(self):
        render_from_checkout(self.checkout, self.output)
        self.assertEqual(
            (self.output / "demo" / "SKILL.md").read_text(),
            (self.checkout / "cw" / "skills" / "demo" / "SKILL.md").read_text(),
        )
        self.assertTrue((self.output / "demo" / "resources" / "guide.md").is_file())

    def test_check_reports_changed_vendored_file(self):
        render_from_checkout(self.checkout, self.output)
        (self.output / "demo" / "SKILL.md").write_text("changed\n")
        with self.assertRaisesRegex(VendorDriftError, "demo/SKILL.md"):
            check_checkout(self.checkout, self.output)

    def test_source_is_licensed_snapshot_not_meridian_base(self):
        self.assertEqual(SOURCE.license, "Apache-2.0")
        self.assertEqual(SOURCE.commit, "fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3")
        self.assertNotIn("meridian-base", SOURCE.url)

    def test_normalizer_changes_known_skill_refs_but_preserves_shell_and_urls(self):
        source = "Use /story-memory.\n```bash\necho $chapter\n```\nhttps://example.com/story-memory\n"
        rendered = normalize_codex_references(source, {"story-memory"}, "demo")
        self.assertIn("Use $story-memory.", rendered)
        self.assertIn("echo $chapter", rendered)
        self.assertIn("https://example.com/story-memory", rendered)

    def test_normalizer_rejects_unbundled_skill_reference(self):
        with self.assertRaisesRegex(ValueError, "qi-layer: unbundled skill reference /qi-maintenance"):
            normalize_codex_references("Load /qi-maintenance.\n", {"qi-layer"}, "qi-layer")

    def test_invalid_vendored_names_do_not_mutate_output_or_escape_it(self):
        outside = self.root / "escape"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep\n")
        invalid_configurations = (
            ("../escape",),
            (str(outside),),
            ("demo/demo",),
            (".",),
            ("demo", "demo"),
            ("not-canonical",),
        )

        for index, names in enumerate(invalid_configurations):
            output = self.root / f"output-{index}"
            with self.subTest(names=names), patch(
                "scripts.vendor_generic_skills.vendored_skills", return_value=names
            ), patch(
                "scripts.vendor_generic_skills.canonical_skills", return_value=set(names) - {"not-canonical"}
            ):
                with self.assertRaises(ValueError):
                    render_from_checkout(self.checkout, output)
            self.assertFalse(output.exists())
            self.assertEqual((outside / "keep.txt").read_text(), "keep\n")

    def test_normalizer_preserves_commonmark_fenced_blocks(self):
        source = (
            "Use /story-memory.\n"
            "   ```bash\nLoad /qi-maintenance.\n   ```\n"
            "~~~text\nLoad /qi-maintenance.\n~~~\n"
            "```\n~~~\nLoad /qi-maintenance.\n```\n"
            "````\n```\nLoad /qi-maintenance.\n````\n"
            "```\n```not-a-close /qi-maintenance\n```\n"
            "```\nLoad /qi-maintenance.\n"
        )

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source.replace("Use /story-memory.", "Use $story-memory."))

    def test_normalizer_preserves_block_quote_fenced_code(self):
        source = "> ```bash\n> Load /qi-maintenance.\n> Load /story-memory.\n> ```\n"

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_preserves_list_continuation_fenced_code(self):
        source = "- ```bash\n  Load /qi-maintenance.\n  Load /story-memory.\n  ```\n"

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_preserves_quote_list_fenced_code(self):
        source = "> - ```bash\n>   Load /qi-maintenance.\n>   Load /story-memory.\n>   ```\n"

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_preserves_list_quote_fenced_code(self):
        source = "- > ```bash\n  > Load /qi-maintenance.\n  > Load /story-memory.\n  > ```\n"

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_preserves_nested_list_fenced_code(self):
        source = "- - ```bash\n    Load /qi-maintenance.\n    Load /story-memory.\n    ```\n"

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_preserves_tab_separated_list_fenced_code(self):
        source = "-\t```bash\n    Load /qi-maintenance.\n    Load /story-memory.\n    ```\n"

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_replace_preserves_preexisting_backup_collision(self):
        destination = self.root / "demo"
        destination.mkdir()
        (destination / "value.txt").write_text("old\n")
        staged = self.root / "staged"
        staged.mkdir()
        (staged / "value.txt").write_text("new\n")
        collision = self.root / ".demo.vendor-backup"
        collision.mkdir()
        (collision / "keep.txt").write_text("keep\n")

        _replace_directory(staged, destination)

        self.assertEqual((destination / "value.txt").read_text(), "new\n")
        self.assertEqual((collision / "keep.txt").read_text(), "keep\n")

    def test_replace_rolls_back_when_install_rename_fails(self):
        destination = self.root / "demo"
        destination.mkdir()
        (destination / "value.txt").write_text("old\n")
        staged = self.root / "staged"
        staged.mkdir()
        (staged / "value.txt").write_text("new\n")
        real_replace = os.replace

        def fail_install(source, target):
            if Path(source) == staged and Path(target) == destination:
                raise OSError("injected install failure")
            return real_replace(source, target)

        with patch("scripts.vendor_generic_skills.os.replace", side_effect=fail_install):
            with self.assertRaisesRegex(OSError, "injected install failure"):
                _replace_directory(staged, destination)

        self.assertEqual((destination / "value.txt").read_text(), "old\n")
        self.assertTrue(staged.is_dir())
