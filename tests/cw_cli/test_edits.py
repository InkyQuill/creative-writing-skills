import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import edits, project


class EditPlanningTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "project"
        self.root.mkdir()
        (self.root / "project.md").write_text(
            "---\nschema-version: 1\ntitle: Test\nstatus: planning\n---\n",
            encoding="utf-8",
        )
        self.project = project.discover_project(self.root)

    def make_file(self, relative: str, data: str | bytes) -> Path:
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            target.write_bytes(data)
        else:
            target.write_text(data, encoding="utf-8", newline="")
        return target

    def test_repeated_text_requires_explicit_count(self):
        target = self.make_file("story/chapters/ch-001.md", "Rain.\nRain.\n")

        with self.assertRaisesRegex(edits.EditConflict, "found 2"):
            edits.plan_edits(
                self.project,
                [{"op": "replace", "path": "story/chapters/ch-001.md", "old": "Rain.", "new": "Snow."}],
            )

        plan = edits.plan_edits(
            self.project,
            [
                {
                    "op": "replace",
                    "path": "story/chapters/ch-001.md",
                    "old": "Rain.",
                    "new": "Snow.",
                    "expect-count": 2,
                }
            ],
        )
        self.assertEqual(b"Snow.\nSnow.\n", plan.changes[0].after)
        self.assertEqual(b"Rain.\nRain.\n", target.read_bytes())

    def test_zero_matches_conflict_and_all_replaces_one_or_more(self):
        self.make_file("story/chapters/ch-001.md", "Rain.\nRain.\n")
        with self.assertRaisesRegex(edits.EditConflict, "found 0"):
            edits.plan_edits(
                self.project,
                [{"op": "delete", "path": "story/chapters/ch-001.md", "old": "Snow."}],
            )

        plan = edits.plan_edits(
            self.project,
            [
                {
                    "op": "replace",
                    "path": "story/chapters/ch-001.md",
                    "old": "Rain.",
                    "new": "Snow.",
                    "all": True,
                }
            ],
        )
        self.assertEqual(b"Snow.\nSnow.\n", plan.changes[0].after)

    def test_replace_matches_whitespace_runs_including_nbsp_and_newlines(self):
        self.make_file(
            "story/chapters/ch-001.md",
            "\tОн\u00a0\u00a0сказал:\n    да.\n",
        )

        plan = edits.plan_edits(
            self.project,
            [
                {
                    "op": "replace",
                    "path": "story/chapters/ch-001.md",
                    "old": "    Он сказал: да.",
                    "new": "Он ответил: да.",
                }
            ],
        )

        self.assertEqual("Он ответил: да.\n".encode(), plan.changes[0].after)

    def test_whitespace_equivalent_replace_matches_remain_counted_for_safety(self):
        self.make_file(
            "story/chapters/ch-001.md",
            "Он сказал.\nОн  сказал.\nОн\u00a0сказал.\n",
        )

        with self.assertRaisesRegex(edits.EditConflict, "found 3"):
            edits.plan_edits(
                self.project,
                [
                    {
                        "op": "replace",
                        "path": "story/chapters/ch-001.md",
                        "old": "Он сказал.",
                        "new": "Он ответил.",
                    }
                ],
            )

    def test_insert_before_after_and_delete_are_sequential_on_one_file(self):
        self.make_file("story/chapters/ch-001.md", "Начало.\nЯкорь.\nКонец.\n")
        plan = edits.plan_edits(
            self.project,
            [
                {
                    "op": "insert-before",
                    "path": "story/chapters/ch-001.md",
                    "anchor": "Якорь.",
                    "new": "До.\n",
                },
                {
                    "op": "insert-after",
                    "path": "story/chapters/ch-001.md",
                    "anchor": "Якорь.",
                    "new": "\nПосле.",
                },
                {"op": "delete", "path": "story/chapters/ch-001.md", "old": "Начало.\n"},
            ],
        )
        self.assertEqual(b"\xd0\x94\xd0\xbe.\n\xd0\xaf\xd0\xba\xd0\xbe\xd1\x80\xd1\x8c.\n\xd0\x9f\xd0\xbe\xd1\x81\xd0\xbb\xd0\xb5.\n\xd0\x9a\xd0\xbe\xd0\xbd\xd0\xb5\xd1\x86.\n", plan.changes[0].after)
        self.assertEqual(1, len(plan.changes))

    def test_crlf_is_normalized_for_matching_and_preserved_for_rendering(self):
        target = self.make_file(
            "story/chapters/ch-001.md",
            b"---\r\ntitle: Rain\r\n---\r\nFirst.\r\nSecond.\r\n",
        )
        before = target.read_bytes()
        plan = edits.plan_edits(
            self.project,
            [
                {
                    "op": "replace",
                    "path": "story/chapters/ch-001.md",
                    "old": "First.\nSecond.",
                    "new": "One.\nTwo.",
                }
            ],
        )
        self.assertEqual(
            b"---\r\ntitle: Rain\r\n---\r\nOne.\r\nTwo.\r\n",
            plan.changes[0].after,
        )
        self.assertEqual(before, target.read_bytes())

    def test_body_edit_preserves_raw_frontmatter_prefix_byte_for_byte(self):
        prefix = b'\xef\xbb\xbf---\r\n# Keep this comment\r\ntitle: "Rain: quoted"\r\nlabels:\r\n  - one\r\n---\r\n'
        target = self.make_file("story/chapters/ch-001.md", prefix + b"Old body.\r\n")
        plan = edits.plan_edits(
            self.project,
            [
                {
                    "op": "replace",
                    "path": "story/chapters/ch-001.md",
                    "old": "Old body.",
                    "new": "New body.",
                }
            ],
        )

        self.assertEqual(prefix + b"New body.\r\n", plan.changes[0].after)
        self.assertEqual(prefix + b"Old body.\r\n", target.read_bytes())

    def test_frontmatter_set_preserves_body_and_supports_regular_values(self):
        self.make_file(
            "story/chapters/ch-001.md",
            "---\ntitle: Old\nnumber: 1\n---\nBody.\n",
        )
        plan = edits.plan_edits(
            self.project,
            [
                {
                    "op": "frontmatter-set",
                    "path": "story/chapters/ch-001.md",
                    "key": "title",
                    "value": "Новое имя",
                }
            ],
        )
        self.assertEqual(
            "---\ntitle: Новое имя\nnumber: 1\n---\nBody.\n",
            plan.changes[0].after.decode("utf-8"),
        )

    def test_refuses_generated_journal_and_lifecycle_fields(self):
        self.make_file("story/_index.md", "---\ngenerated: true\n---\n# Story\n")
        self.make_file(".creative-writing/note.md", "private\n")
        self.make_file("work/drafts/revision.md", "---\nstatus: working\n---\nDraft.\n")

        invalid = (
            {"op": "delete", "path": "story/_index.md", "old": "Story"},
            {"op": "delete", "path": ".creative-writing/note.md", "old": "private"},
            {
                "op": "frontmatter-set",
                "path": "work/drafts/revision.md",
                "key": "base-revision",
                "value": "abc",
            },
            {
                "op": "frontmatter-set",
                "path": "work/drafts/revision.md",
                "key": "status",
                "value": "ready",
            },
            {"op": "frontmatter-set", "path": "project.md", "key": "schema-version", "value": 1},
        )
        for operation in invalid:
            with self.subTest(operation=operation), self.assertRaises(edits.EditPlanError):
                edits.plan_edits(self.project, [operation])

    def test_schema_validation_finishes_before_any_target_is_read(self):
        target = self.make_file("story/chapters/ch-001.md", "Rain.\n")
        original_read_bytes = Path.read_bytes
        reads: list[Path] = []

        def tracked_read_bytes(path: Path) -> bytes:
            reads.append(path)
            return original_read_bytes(path)

        with mock.patch.object(Path, "read_bytes", tracked_read_bytes):
            with self.assertRaises(edits.EditPlanError):
                edits.plan_edits(
                    self.project,
                    [
                        {"op": "delete", "path": "story/chapters/ch-001.md", "old": "Rain."},
                        {"op": "replace", "path": "story/chapters/ch-001.md", "old": "Rain.", "new": "Snow.", "extra": 1},
                    ],
                )
        self.assertEqual([], reads)
        self.assertEqual(b"Rain.\n", target.read_bytes())

        with self.assertRaisesRegex(edits.EditPlanError, "field names must be strings"):
            edits.plan_edits(self.project, [{"op": "delete", "path": "story/a.md", "old": "x", 1: "bad"}])

    def test_lone_surrogate_is_rejected_before_any_target_is_read(self):
        self.make_file("story/chapters/ch-001.md", "Rain.\n")
        original_read_bytes = Path.read_bytes
        reads: list[Path] = []

        def tracked_read_bytes(path: Path) -> bytes:
            reads.append(path)
            return original_read_bytes(path)

        with mock.patch.object(Path, "read_bytes", tracked_read_bytes):
            with self.assertRaisesRegex(edits.EditPlanError, "Unicode scalar"):
                edits.plan_edits(
                    self.project,
                    [
                        {"op": "delete", "path": "story/chapters/ch-001.md", "old": "Rain."},
                        {
                            "op": "replace",
                            "path": "story/chapters/ch-001.md",
                            "old": "Rain.",
                            "new": "\ud800",
                        },
                    ],
                )
        self.assertEqual([], reads)

    def test_text_edit_cannot_create_frontmatter_or_edit_malformed_document(self):
        plain = self.make_file("story/chapters/plain.md", "Body.\n")
        malformed = self.make_file("story/chapters/malformed.md", "---\nstatus: working\nBody.\n")

        with self.assertRaisesRegex(edits.EditPlanError, "change frontmatter"):
            edits.plan_edits(
                self.project,
                [
                    {
                        "op": "replace",
                        "path": "story/chapters/plain.md",
                        "old": "Body.",
                        "new": "---\nstatus: ready\n---\nBody.",
                    }
                ],
            )
        with self.assertRaisesRegex(edits.EditPlanError, "cannot read edit target"):
            edits.plan_edits(
                self.project,
                [{"op": "delete", "path": "story/chapters/malformed.md", "old": "Body."}],
            )
        self.assertEqual(b"Body.\n", plain.read_bytes())
        self.assertEqual(b"---\nstatus: working\nBody.\n", malformed.read_bytes())

    def test_load_operations_validates_strict_json_schema(self):
        plans = Path(self.directory.name) / "plans"
        plans.mkdir()
        valid = plans / "valid.json"
        valid.write_text(
            json.dumps(
                [
                    {
                        "op": "replace",
                        "path": "story/chapters/ch-001.md",
                        "old": "Rain.",
                        "new": "Snow.",
                    }
                ]
            ),
            encoding="utf-8",
        )
        self.assertEqual("replace", edits.load_operations(valid)[0]["op"])

        invalid_plans = (
            {"not": "a list"},
            [{"op": "unknown", "path": "story/a.md"}],
            [{"op": "delete", "path": "/story/a.md", "old": "x"}],
            [{"op": "delete", "path": "story/a.md", "old": "x", "expect-count": 1, "all": True}],
            [{"op": "delete", "path": "story/a.md", "old": "x", "expect-count": True}],
            [{"op": "delete", "path": "story//a.md", "old": "x"}],
        )
        for index, content in enumerate(invalid_plans):
            path = plans / f"invalid-{index}.json"
            path.write_text(json.dumps(content), encoding="utf-8")
            with self.subTest(content=content), self.assertRaises(edits.EditPlanError):
                edits.load_operations(path)

        duplicate = plans / "duplicate.json"
        duplicate.write_text(
            '[{"op":"delete","path":"story/a.md","old":"x","old":"y"}]',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(edits.EditPlanError, "duplicate JSON field"):
            edits.load_operations(duplicate)

    def test_missing_or_non_markdown_target_is_rejected_without_writes(self):
        existing = self.make_file("story/chapters/ch-001.md", "Rain.\n")
        for path in ("story/chapters/missing.md", "notes.txt"):
            with self.subTest(path=path), self.assertRaises(edits.EditPlanError):
                edits.plan_edits(self.project, [{"op": "delete", "path": path, "old": "Rain."}])
        self.assertEqual(b"Rain.\n", existing.read_bytes())


if __name__ == "__main__":
    unittest.main()
