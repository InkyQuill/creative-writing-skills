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

    def test_render_adapts_qi_layer_mirror_command_without_losing_behavior(self):
        source = self.checkout / "cw" / "skills" / "qi-layer"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: qi-layer\n---\n"
            "`/qi-maintenance` owns when colocated knowledge must move with source changes.\n"
            "Run `meridian qi claude-md-fix <target-root>` on the containing tree\n"
            "after creating or moving AGENTS.md files: it creates missing mirrors, skips\n"
            "exact ones, and reports anything else as a conflict.\n\n"
            "Never write shared instructions into CLAUDE.md. Claude-only knowledge is\n"
            "rare; when it exists, put it below the `@AGENTS.md` import and expect\n"
            "`claude-md-fix` to keep flagging the file, so the divergence stays visible.\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills", return_value=("qi-layer",)
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills", return_value={"qi-layer"}
        ):
            render_from_checkout(self.checkout, self.output)
        rendered = (self.output / "qi-layer" / "SKILL.md").read_text()
        self.assertNotIn("meridian", rendered.lower())
        self.assertNotIn("claude-md-fix", rendered)
        self.assertIn("create missing mirrors", rendered)
        self.assertIn("leave exact mirrors unchanged", rendered)
        self.assertIn("report divergent files as conflicts", rendered)

    def test_render_adapts_mermaid_validation_command(self):
        source = self.checkout / "cw" / "skills" / "structured-artifact"
        (source / "resources").mkdir(parents=True)
        (source / "SKILL.md").write_text("---\nname: structured-artifact\n---\nBody.\n")
        (source / "resources" / "diagrams.md").write_text(
            "Validate with `meridian mermaid check`.\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("structured-artifact",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"structured-artifact"},
        ):
            render_from_checkout(self.checkout, self.output)
        rendered = (
            self.output / "structured-artifact" / "resources" / "diagrams.md"
        ).read_text()
        self.assertNotIn("meridian", rendered.lower())
        self.assertIn("available Mermaid parser or renderer", rendered)
        self.assertIn("report syntax errors before delivery", rendered)

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

    def test_normalizer_preserves_list_state_fenced_code_byte_for_byte(self):
        cases = {
            "blank line in open fence": (
                "- ```markdown\n"
                "  literal\n"
                "\n"
                "  [placeholder](kb/{domain}/vocab.md)\n"
                "  $chapter /story-memory @ghost\n"
                "  ```\n"
            ),
            "continuation after empty marker": (
                "-\n"
                "    ```markdown\n"
                "    [placeholder](kb/{domain}/vocab.md)\n"
                "    $chapter /story-memory @ghost\n"
                "    ```\n"
            ),
        }
        for label, source in cases.items():
            with self.subTest(label=label):
                rendered = normalize_codex_references(
                    source,
                    {"story-memory"},
                    "demo",
                )
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

    def test_normalizer_reopens_root_fence_after_list_fence_ends(self):
        source = (
            "- ```bash\n  Load /qi-maintenance.\n````\n"
            "Load /qi-maintenance.\nLoad /story-memory.\n````\n"
        )

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_reopens_root_fence_after_quote_fence_ends(self):
        source = (
            "> ```bash\n> Load /qi-maintenance.\n````\n"
            "Load /qi-maintenance.\nLoad /story-memory.\n````\n"
        )

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_reopens_root_fence_after_composed_container_ends(self):
        source = (
            "> - ```bash\n>   Load /qi-maintenance.\n````\n"
            "Load /qi-maintenance.\nLoad /story-memory.\n````\n"
        )

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_reopens_fence_at_surviving_outer_list_level(self):
        source = (
            "123. - ```bash\n       Load /qi-maintenance.\n     ````\n"
            "     Load /qi-maintenance.\n     Load /story-memory.\n     ````\n"
        )

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
