import unittest

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli.markdown_links import extract_links


class MarkdownLinkTests(unittest.TestCase):
    def test_ignores_nonprose_regions_and_preserves_lines(self):
        text = """---
link: [front](front.md)
---
`[inline](inline.md)`
<!-- [comment](comment.md) -->
~~~md
[fenced](fenced.md)
~~~
    [indented](indented.md)
![image](images/a(b).png "title")
[angle](<space name.md> 'title')
"""
        links = extract_links(text)
        self.assertEqual(
            [("images/a(b).png \"title\"", 10, True), ("<space name.md> 'title'", 11, False)],
            [(item.destination, item.line, item.image) for item in links],
        )

    def test_fence_closure_requires_matching_marker_and_whitespace_only_suffix(self):
        text = (
            "````md\n"
            "[hidden](hidden.md)\n"
            "```\n"
            "[still-hidden](still-hidden.md)\n"
            "```` text\n"
            "[also-hidden](also-hidden.md)\n"
            "`````   \n"
            "[visible](visible.md)\n"
        )

        self.assertEqual(
            [("visible.md", 8)],
            [(item.destination, item.line) for item in extract_links(text)],
        )

    def test_unmatched_backtick_is_literal_and_escaped_bracket_is_not_a_link(self):
        text = (
            "`literal [visible](visible.md)\n"
            "\\[escaped](escaped.md) and [kept](kept.md)\n"
            "``code [hidden](hidden.md)`` [after](after.md)\n"
        )

        self.assertEqual(
            [("visible.md", 1), ("kept.md", 2), ("after.md", 3)],
            [(item.destination, item.line) for item in extract_links(text)],
        )
