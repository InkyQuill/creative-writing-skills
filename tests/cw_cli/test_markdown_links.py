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
