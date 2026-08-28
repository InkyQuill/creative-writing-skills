import unittest

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import documents


class DocumentTests(unittest.TestCase):
    def test_supported_frontmatter_round_trips_crlf_and_bom(self):
        raw = (
            b"\xef\xbb\xbf---\r\n"
            b"title: Story\r\n"
            b"number: 3\r\n"
            b"hidden: false\r\n"
            b"tags:\r\n"
            b"  - sea\r\n"
            b"  - memory\r\n"
            b"---\r\n"
            b"\r\nText\r\n"
        )

        parsed = documents.parse_document(raw)

        self.assertEqual(
            {"title": "Story", "number": 3, "hidden": False, "tags": ["sea", "memory"]},
            parsed.metadata,
        )
        self.assertEqual("\r\n", parsed.newline)
        self.assertTrue(parsed.bom)
        self.assertEqual(raw, documents.render_document(parsed))

    def test_logical_hash_ignores_bom_and_line_endings(self):
        left = b"\xef\xbb\xbf---\r\ntitle: Story\r\n---\r\nBody\r\n"
        right = b"---\ntitle: Story\n---\nBody\n"

        self.assertEqual(documents.logical_hash(left), documents.logical_hash(right))

    def test_canonical_text_normalizes_all_line_endings(self):
        self.assertEqual("one\ntwo\nthree\n", documents.canonical_text(b"\xef\xbb\xbfone\r\ntwo\rthree\n"))

    def test_lf_russian_document_round_trips(self):
        raw = "---\ntitle: Море памяти\ntags:\n  - глава\n---\nТекст\n".encode("utf-8")

        parsed = documents.parse_document(raw)

        self.assertEqual({"title": "Море памяти", "tags": ["глава"]}, parsed.metadata)
        self.assertEqual("\n", parsed.newline)
        self.assertFalse(parsed.bom)
        self.assertEqual(raw, documents.render_document(parsed))

    def test_parses_supported_scalar_forms(self):
        raw = (
            b"---\n"
            b'title: "A \\"quoted\\" title"\n'
            b"author: 'O''Brien'\n"
            b"draft: true\n"
            b"chapter: -12\n"
            b"summary:\n"
            b"---\n"
        )

        self.assertEqual(
            {
                "title": 'A "quoted" title',
                "author": "O'Brien",
                "draft": True,
                "chapter": -12,
                "summary": "",
            },
            documents.parse_document(raw).metadata,
        )

    def test_list_items_remain_strings(self):
        raw = b"---\ntags:\n  - 3\n  - true\n  - 'sea''s edge'\n---\n"

        self.assertEqual(
            {"tags": ["3", "true", "sea's edge"]},
            documents.parse_document(raw).metadata,
        )

    def test_rejects_nested_mapping_with_line_number(self):
        with self.assertRaisesRegex(documents.DocumentError, r"line 3.*nested mapping"):
            documents.parse_document(b"---\nauthor:\n  name: Pavel\n---\n")

    def test_rejects_block_scalar_with_line_number(self):
        with self.assertRaisesRegex(documents.DocumentError, r"line 2.*block scalar"):
            documents.parse_document(b"---\nsummary: |\n  unsafe\n---\n")

    def test_rejects_duplicate_key_with_line_number(self):
        with self.assertRaisesRegex(documents.DocumentError, r"line 3.*duplicate key"):
            documents.parse_document(b"---\ntitle: First\ntitle: Second\n---\n")

    def test_rejects_invalid_utf8_with_line_number(self):
        with self.assertRaisesRegex(documents.DocumentError, r"line 2.*UTF-8"):
            documents.parse_document(b"---\nname: \xff\n---\n")

    def test_rejects_unterminated_frontmatter_with_line_number(self):
        with self.assertRaisesRegex(documents.DocumentError, r"line 4.*unterminated frontmatter"):
            documents.parse_document(b"---\ntitle: Story\nBody\n")

    def test_rejects_list_item_without_list_key_with_line_number(self):
        with self.assertRaisesRegex(documents.DocumentError, r"line 2.*list item"):
            documents.parse_document(b"---\n  - orphan\n---\n")


if __name__ == "__main__":
    unittest.main()
