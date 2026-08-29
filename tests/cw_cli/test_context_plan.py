import io
import json
import tempfile
import unittest
from pathlib import Path

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import app, context, project, scaffold


class ContextPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "project"
        for relative, data in scaffold.render_scaffold("Context", "en").items():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (self.root / ".creative-writing/context").mkdir(parents=True)
        (self.root / ".creative-writing/transactions").mkdir(parents=True)
        self.project = project.discover_project(self.root)

    def write(self, relative: str, text: str) -> Path:
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def plan(self, kind: str, path: str, role: str = "trusted") -> context.ContextPlan:
        return context.plan_context(self.project, kind, path, role)

    def test_draft_prioritizes_target_direct_links_and_neighbor_then_structured_peers(self):
        self.write("story/chapters/ch-003.md", "---\nnumber: 3\n---\nThree.\n")
        self.write("story/chapters/ch-004.md", "---\nnumber: 4\n---\nFour.\n")
        self.write("story/chapters/ch-005.md", "---\nnumber: 5\n---\nFive.\n")
        self.write("kb/characters/mara.md", "---\ntitle: Mara\n---\nMara.\n")
        self.write("kb/world/castle.md", "---\ntitle: Castle\n---\nCastle.\n")
        self.write(
            "work/drafts/ch-004.md",
            "---\ntarget: story/chapters/ch-004.md\nrelated:\n"
            "  - kb/characters/mara.md\n---\nNo inferred link to kb/world/castle.md.\n",
        )
        self.write(
            "work/plans/ch-004-plan.md",
            "---\nstatus: active\nsubject: story/chapters/ch-004.md\n---\nPlan.\n",
        )
        self.write(
            "kb/issues/ch-004-gap.md",
            "---\nstatus: open\nsubject: story/chapters/ch-004.md\n---\nGap.\n",
        )
        self.write(
            "kb/world/backlink.md",
            "---\ntitle: Backlink\n---\n[Chapter](../../story/chapters/ch-004.md)\n",
        )

        plan = self.plan("draft", "work/drafts/ch-004.md")

        self.assertEqual("work/drafts/ch-004.md", plan.required[0])
        self.assertEqual("story/chapters/ch-004.md", plan.required[1])
        self.assertLess(
            plan.required.index("kb/characters/mara.md"),
            plan.required.index("kb/vocab.md"),
        )
        self.assertEqual(
            ("story/chapters/ch-003.md", "story/chapters/ch-005.md"),
            plan.suggested[:2],
        )
        self.assertLess(
            plan.suggested.index("work/plans/ch-004-plan.md"),
            plan.suggested.index("kb/world/backlink.md"),
        )
        self.assertLess(
            plan.suggested.index("kb/world/backlink.md"),
            plan.suggested.index("kb/issues/ch-004-gap.md"),
        )
        self.assertNotIn("kb/world/castle.md", plan.required + plan.suggested)

    def test_first_last_neighbors_and_duplicate_numbers_are_nonfatal_unresolved(self):
        self.write("story/chapters/first.md", "---\nnumber: 1\n---\n")
        self.write("story/chapters/middle.md", "---\nnumber: 2\n---\n")
        self.write("story/chapters/last.md", "---\nnumber: 3\n---\n")

        first = self.plan("chapter", "story/chapters/first.md")
        last = self.plan("chapter", "story/chapters/last.md")
        self.assertEqual(("story/chapters/middle.md",), first.suggested[:1])
        self.assertEqual(("story/chapters/middle.md",), last.suggested[:1])

        self.write("story/chapters/duplicate.md", "---\nnumber: 2\n---\n")
        duplicate = self.plan("chapter", "story/chapters/middle.md")
        self.assertTrue(any("chapter-number:2" in item for item in duplicate.unresolved))
        self.assertNotIn("story/chapters/first.md", duplicate.suggested)
        self.assertNotIn("story/chapters/last.md", duplicate.suggested)

    def test_kb_backlinks_deduplicate_by_portable_identity(self):
        self.write("kb/world/place.md", "---\ntitle: Place\n---\n")
        self.write(
            "kb/characters/mara.md",
            "---\nrelated:\n  - kb/world/place.md\n---\nCharacter.\n",
        )
        plan = self.plan("kb", "kb/world/place.md")
        self.assertEqual(1, plan.suggested.count("kb/characters/mara.md"))

    def test_unknown_character_and_missing_reference_are_unresolved_not_failure(self):
        self.write(
            "kb/world/place.md",
            "---\nrelated:\n  - kb/characters/missing.md\n---\nPlace.\n",
        )
        plan = self.plan("kb", "kb/world/place.md", "character:missing")
        self.assertIn("character:missing", plan.unresolved)
        self.assertIn("kb/characters/missing.md", plan.unresolved)

    def test_structured_paths_preserve_spaces_and_markdown_titles_are_separate(self):
        self.write("kb/world/ice castle.md", "---\ntitle: Ice Castle\n---\n")
        self.write("kb/world/other place.md", "---\ntitle: Other Place\n---\n")
        self.write(
            "kb/characters/mara.md",
            "---\nrelated:\n  - kb/world/ice castle.md\n---\n"
            '[Other](../world/other%20place.md "optional title words")\n',
        )

        plan = self.plan("kb", "kb/characters/mara.md")

        self.assertIn("kb/world/ice castle.md", plan.required)
        self.assertIn("kb/world/other place.md", plan.required)

    def test_markdown_parenthesized_title_keeps_its_closing_parenthesis(self):
        self.write("kb/world/linked place.md", "---\ntitle: Linked Place\n---\n")
        self.write(
            "kb/characters/mara.md",
            "---\ntitle: Mara\n---\n"
            "[Place](../world/linked%20place.md (Useful context title))\n",
        )

        plan = self.plan("kb", "kb/characters/mara.md")

        self.assertIn("kb/world/linked place.md", plan.required)
        self.assertFalse(any("Useful context title" in item for item in plan.unresolved))

    def test_explicit_context_never_selects_unmanaged_or_protected_paths(self):
        self.write("README.md", "Root notes.\n")
        self.write(".creative-writing/context/private.md", "Derived.\n")
        self.write(
            "kb/world/place.md",
            "---\nrelated:\n  - README.md\n  - .creative-writing/context/private.md\n---\n",
        )

        plan = self.plan("kb", "kb/world/place.md")

        self.assertNotIn("README.md", plan.required)
        self.assertNotIn(".creative-writing/context/private.md", plan.required)
        self.assertIn("README.md", plan.unresolved)
        self.assertIn(".creative-writing/context/private.md", plan.unresolved)

    def test_portable_identity_collision_selects_neither_explicit_path(self):
        self.write("kb/world/Place.md", "---\ntitle: Upper\n---\n")
        self.write("kb/world/place.md", "---\ntitle: Lower\n---\n")
        self.write(
            "kb/characters/mara.md",
            "---\nrelated:\n  - kb/world/Place.md\n  - kb/world/place.md\n---\n",
        )

        plan = self.plan("kb", "kb/characters/mara.md")

        self.assertNotIn("kb/world/Place.md", plan.required)
        self.assertNotIn("kb/world/place.md", plan.required)
        self.assertTrue(any("portable-path-collision" in item for item in plan.unresolved))

    def test_portable_identity_collision_on_subject_is_nonfatal_and_selects_neither(self):
        self.write("kb/world/Place.md", "---\ntitle: Upper\n---\n")
        self.write("kb/world/place.md", "---\ntitle: Lower\n---\n")

        plan = self.plan("kb", "kb/world/Place.md")
        stdout, stderr = io.StringIO(), io.StringIO()
        status = app.run(
            ["context", "kb", "kb/world/Place.md", "--format", "json"],
            cwd=self.root,
            stdout=stdout,
            stderr=stderr,
        )

        self.assertNotIn("kb/world/Place.md", plan.required)
        self.assertNotIn("kb/world/place.md", plan.required)
        self.assertTrue(any("portable-path-collision" in item for item in plan.unresolved))
        self.assertEqual((0, ""), (status, stderr.getvalue()))
        self.assertTrue(json.loads(stdout.getvalue())["unresolved"])

    def test_character_role_uses_unicode_portable_file_stems(self):
        self.write("kb/characters/мара.md", "---\ntitle: Мара\n---\n")
        self.write("kb/world/place.md", "---\ntitle: Place\n---\n")

        known = self.plan("kb", "kb/world/place.md", "character:мара")
        self.assertNotIn("character:мара", known.unresolved)
        for role in ("character:CON", "character:bad/name", "character:bad\x7f"):
            with self.subTest(role=role), self.assertRaises(context.ContextPlanError):
                self.plan("kb", "kb/world/place.md", role)

    def test_missing_canonical_context_dependencies_are_unresolved(self):
        self.write("story/chapters/one.md", "---\nnumber: 1\n---\n")
        (self.root / "kb/vocab.md").unlink()
        (self.root / "kb/continuity/state.md").unlink()

        plan = self.plan("chapter", "story/chapters/one.md")

        self.assertIn("kb/vocab.md", plan.unresolved)
        self.assertIn("kb/continuity/state.md", plan.unresolved)
        self.assertTrue(any("kb/vocab.md" in item for item in plan.warnings))

    def test_malformed_unrelated_files_warn_but_do_not_abort(self):
        self.write("story/chapters/one.md", "---\nnumber: 1\n---\nOne.\n")
        self.write("kb/world/broken.md", "---\nsources: [bad]\n---\n")
        plan = self.plan("chapter", "story/chapters/one.md")
        self.assertTrue(any("kb/world/broken.md" in item for item in plan.warnings))

    def test_nested_symlink_and_nonportable_subjects_are_rejected(self):
        self.write("story/chapters/one.md", "---\nnumber: 1\n---\n")
        nested = self.root / "story/chapters/nested"
        nested.mkdir()
        (nested / "project.md").write_text(
            "---\nschema-version: 1\ntitle: Nested\nlanguage: en\nstatus: drafting\n---\n",
            encoding="utf-8",
        )
        (nested / "inside.md").write_text("---\nnumber: 1\n---\n", encoding="utf-8")
        (self.root / "story/chapters/link.md").symlink_to(self.root / "story/chapters/one.md")

        for path in ("../outside.md", "story\\chapters\\one.md", "story/chapters/CON.md", "story/chapters/link.md", "story/chapters/nested/inside.md"):
            with self.subTest(path=path), self.assertRaises(context.ContextPlanError):
                self.plan("chapter", path)

    def test_cli_text_json_have_identical_facts_and_are_read_only(self):
        self.write("story/chapters/one.md", "---\nnumber: 1\n---\nOne.\n")
        before = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*"))

        outputs = []
        for output_format in ("text", "json"):
            stdout, stderr = io.StringIO(), io.StringIO()
            status = app.run(
                ["context", "chapter", "story/chapters/one.md", "--format", output_format],
                cwd=self.root,
                stdout=stdout,
                stderr=stderr,
            )
            self.assertEqual((0, ""), (status, stderr.getvalue()))
            outputs.append(json.loads(stdout.getvalue()))

        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(before, sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*")))

    def test_cli_invalid_kind_or_role_is_status_two(self):
        self.write("story/chapters/one.md", "---\nnumber: 1\n---\n")
        for argv in (
            ["context", "invalid", "story/chapters/one.md"],
            ["context", "chapter", "story/chapters/one.md", "--as", "character:../bad"],
        ):
            with self.subTest(argv=argv):
                stdout, stderr = io.StringIO(), io.StringIO()
                status = app.run(argv, cwd=self.root, stdout=stdout, stderr=stderr)
                self.assertEqual(2, status)


if __name__ == "__main__":
    unittest.main()
