import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins" / "creative-writing-skills" / "skills"
CRAFT = SKILLS / "creative-writing-craft"


def read(relative: str) -> str:
    return (SKILLS / relative).read_text(encoding="utf-8")


class LanguageProseRulesTests(unittest.TestCase):
    def test_project_contract_documents_optional_profile_and_checker_capabilities(self):
        setup = read("project-setup/SKILL.md")
        contract = read("project-maintenance/resources/project-contract.md")
        command_reference = read("project-maintenance/resources/command-reference.md")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        combined = "\n".join((setup, contract, command_reference, readme))

        for profile in (
            "general",
            "light-novel",
            "classical-literary",
            "literary-fiction",
        ):
            self.assertIn(profile, combined)
        self.assertRegex(combined, r"(?s)prose-profile.{0,220}(optional|default|general)")
        self.assertRegex(combined, r"(?s)unsupported\s+language.{0,300}(skip|omit)")
        self.assertRegex(combined, r"(?s)universal.{0,180}(metric|count)")

    def test_prose_resource_tree_separates_languages_and_profiles(self):
        expected = {
            "resources/prose/base.md",
            "resources/prose/languages/en.md",
            "resources/prose/languages/ru.md",
            "resources/prose/profiles/light-novel/base.md",
            "resources/prose/profiles/light-novel/en.md",
            "resources/prose/profiles/light-novel/ru.md",
            "resources/prose/profiles/classical-literary/base.md",
            "resources/prose/profiles/classical-literary/en.md",
            "resources/prose/profiles/classical-literary/ru.md",
            "resources/prose/profiles/literary-fiction/base.md",
        }
        actual = {
            path.relative_to(CRAFT).as_posix()
            for path in (CRAFT / "resources" / "prose").rglob("*.md")
        }
        self.assertEqual(expected, actual)
        self.assertFalse((CRAFT / "resources/prose-writing.md").exists())
        self.assertFalse((CRAFT / "resources/genre/litfic.md").exists())

    def test_language_references_are_native_and_profiles_are_substantive(self):
        english = read("creative-writing-craft/resources/prose/languages/en.md")
        russian = read("creative-writing-craft/resources/prose/languages/ru.md")
        self.assertRegex(english, r"(?i)dialogue|quotation|sentence")
        self.assertRegex(english, r'"[^"\n]+"')
        self.assertRegex(russian, r"[А-Яа-яЁё]{4,}")
        self.assertRegex(russian, r"«[^»\n]+»")

        for profile in ("light-novel", "classical-literary"):
            for adapter in ("base", "en", "ru"):
                text = read(
                    f"creative-writing-craft/resources/prose/profiles/{profile}/{adapter}.md"
                )
                self.assertGreaterEqual(len(text.split()), 90, (profile, adapter))
                self.assertRegex(text.lower(), r"variat|вариат")
                self.assertRegex(text.lower(), r"failure|ошиб|сбой|не пут")

    def test_router_defines_independent_axes_and_precedence(self):
        router = read("creative-writing-craft/SKILL.md")
        for axis in (
            "production mode",
            "market genre",
            "manuscript language",
            "prose profile",
            "author voice",
        ):
            self.assertIn(axis, router.lower())
        self.assertIn("ru-RU", router)
        self.assertIn("No prose profile means `general`", router)
        self.assertIn("without a profile overlay", router)
        ordered = [
            "universal prose base",
            "manuscript-language",
            "prose-profile",
            "project-wide",
            "narrator",
            "current author brief",
        ]
        positions = [router.lower().index(value) for value in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertRegex(router.lower(), r"unsupported.{0,180}never.{0,80}english")

    def test_profile_language_adapter_is_optional_when_profile_is_base_only(self):
        self.assertTrue(
            (
                CRAFT
                / "resources/prose/profiles/literary-fiction/base.md"
            ).is_file()
        )
        self.assertFalse(
            (
                CRAFT
                / "resources/prose/profiles/literary-fiction/en.md"
            ).exists()
        )
        for path in (
            "creative-writing-craft/SKILL.md",
            "creative-writing-muse/SKILL.md",
            "story-memory/resources/story-context.md",
        ):
            text = read(path).lower()
            self.assertRegex(
                text,
                r"language adapter.{0,100}(when|if).{0,80}(provide|exist|available)",
                path,
            )

    def test_generic_review_guidance_routes_surface_rules_to_language_stack(self):
        generic_paths = (
            "writing-principles/SKILL.md",
            "story-review/resources/line-edit.md",
            "story-review/resources/copyedit.md",
            "story-review/resources/proofreading.md",
            "story-review/resources/prose-critique/antipatterns.md",
            "story-review/resources/prose-critique/baseline.md",
            "story-review/resources/prose-critique/prose.md",
            "story-review/resources/prose-critique/tells.md",
            "story-review/resources/prose-critique/voice.md",
            "creative-writing-craft/resources/scene-construction.md",
        )
        combined = "\n".join(read(path) for path in generic_paths)
        for leaked in (
            "said is invisible",
            "serial comma",
            "honor/honour",
            "gray/grey",
            "Russian literary prose runs longer",
            "dash-opened line is dialogue",
            "«ёлочки»",
            "I/me/my counts",
            "delve, tapestry",
        ):
            self.assertNotIn(leaked.lower(), combined.lower())
        for path in generic_paths:
            text = read(path).lower()
            self.assertRegex(text, r"language|prose stack|selected prose")

    def test_muse_and_prose_workers_receive_the_resolved_stack(self):
        muse = read("creative-writing-muse/SKILL.md")
        self.assertIn("exact plugin resource paths", muse)
        for worker in ("writer", "editor", "critic", "style-creator"):
            text = read(f"creative-writing-muse/resources/workers/{worker}.md")
            for required in (
                "language tag",
                "prose profile",
                "base",
                "language resource",
                "profile",
                "samples",
            ):
                self.assertIn(required, text.lower(), (worker, required))
        style_creator = read(
            "creative-writing-muse/resources/workers/style-creator.md"
        ).lower()
        self.assertRegex(style_creator, r"never.{0,100}cross-language")

    def test_flat_sample_and_style_templates_preserve_promotion_boundary(self):
        kb = read("kb-management/SKILL.md")
        setup = read("project-setup/SKILL.md")
        analysis = read("creative-writing-craft/resources/style-analysis.md")
        combined = "\n".join((kb, setup, analysis)).lower()
        self.assertIn("kb/samples/<descriptive-name>.md", combined)
        self.assertIn("kb/styles/<descriptive-name>.md", combined)
        for role in ("authoritative", "aspirational", "negative"):
            self.assertIn(role, combined)
        for field in (
            "language",
            "scope",
            "source",
            "evidence",
            "observed",
            "author-specified",
            "allowed variation",
            "anti-patterns",
        ):
            self.assertIn(field, combined)
        self.assertRegex(combined, r"evidence.{0,120}not.{0,120}(imitat|mechanical)")
        self.assertIn("work/reviews/", combined)
        self.assertRegex(combined, r"style-creator[\s\S]{0,100}proposal")
        self.assertRegex(combined, r"previewed.{0,100}recoverable")

    def test_story_context_selects_scoped_language_and_voice_evidence(self):
        context = read("story-memory/resources/story-context.md").lower()
        for phrase in (
            "manuscript language",
            "prose profile",
            "kb/styles/",
            "kb/samples/",
            "knowledge boundaries",
        ):
            self.assertIn(phrase, context)
        self.assertRegex(context, r"only.{0,120}(relevant|applicable)")


if __name__ == "__main__":
    unittest.main()
