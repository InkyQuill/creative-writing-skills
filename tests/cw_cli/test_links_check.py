import tempfile
import unittest
from pathlib import Path

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import project, scaffold
from cwcli.checks import links


def make_project(root: Path) -> project.Project:
    for relative, data in scaffold.render_scaffold("Links", "en").items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (root / ".creative-writing/context").mkdir(parents=True, exist_ok=True)
    (root / ".creative-writing/transactions").mkdir(parents=True, exist_ok=True)
    return project.discover_project(root)


class LinkCheckTests(unittest.TestCase):
    def test_malformed_percent_decoding_and_nul_do_not_abort_peer_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            chapter = root / "story/chapters/one.md"
            chapter.write_text(
                "---\nnumber: 1\n---\n[bad](%FF.md) [nul](bad%00.md) [missing](missing.md)\n",
                encoding="utf-8",
            )

            findings = links.check_links(model)

            self.assertEqual(2, sum(item.code == links.MALFORMED_LINK for item in findings))
            self.assertEqual(1, sum(item.code == links.MISSING_TARGET for item in findings))

    def test_external_opaque_paths_are_classified_without_percent_decoding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            chapter = root / "story/chapters/one.md"
            chapter.write_text(
                "---\nnumber: 1\n---\n"
                "[https](https://example.com/%FF) [http](http://example.com/%00) "
                "[network](//example.com/%FF) [mail](mailto:test%FF@example.com) "
                "[other](gemini://example.com/%FF)\n",
                encoding="utf-8",
            )

            findings = links.check_links(model)

            self.assertFalse([item for item in findings if item.code == links.MALFORMED_LINK])
            self.assertEqual(1, sum(item.code == links.EXTERNAL_REFERENCE for item in findings))

    def test_missing_external_parent_and_nested_links_are_classified_without_following(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            chapter = root / "story/chapters/one.md"
            chapter.write_text(
                "---\nnumber: 1\n---\n[missing](two.md) [web](https://example.com/x) "
                "[parent](../../../outside.md) [nested](nested/page.md)\n",
                encoding="utf-8",
            )
            nested = root / "story/chapters/nested"
            nested.mkdir()
            (nested / "project.md").write_text("---\nschema-version: 1\ntitle: N\nlanguage: en\nstatus: planning\n---\n", encoding="utf-8")
            (nested / "page.md").write_text("nested", encoding="utf-8")

            findings = links.check_links(model)

            self.assertEqual(1, sum(item.code == links.MISSING_TARGET for item in findings))
            self.assertEqual(2, sum(item.code == links.EXTERNAL_REFERENCE for item in findings))
            self.assertNotIn("https://example.com/x", " ".join(item.message for item in findings))

    def test_target_class_orphan_and_index_drift_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            chapter = root / "story/chapters/one.md"
            chapter.write_text("---\nnumber: 1\n---\n[bad](../../kb/world)\n", encoding="utf-8")

            findings = links.check_links(model)

            codes = {item.code for item in findings}
            self.assertIn(links.TARGET_CLASS, codes)
            self.assertIn(links.ORPHAN_PAGE, codes)
            self.assertIn(links.INDEX_DRIFT, codes)
