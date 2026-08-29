import os
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from tests.cw_cli import helpers  # noqa: F401
from cwcli import project
from cwcli.checks import prose


class ProseMetricTests(unittest.TestCase):
    def test_metrics_are_immutable_and_match_representative_legacy_counts(self):
        text = "Она вошла. Он молчал тихо.\n"
        metrics = prose.analyze_prose(text, language="ru")
        self.assertEqual((metrics.word_count, metrics.sentence_count), (5, 2))
        self.assertEqual(metrics.sentence_lengths, (2, 3))
        self.assertEqual(metrics.language, "ru")
        with self.assertRaises(FrozenInstanceError):
            metrics.word_count = 0

    def test_english_words_apostrophes_and_sentences_match_legacy_behavior(self):
        text = "She can't wait. They're here!\n"
        metrics = prose.analyze_prose(text, language="en-US")
        self.assertEqual((metrics.word_count, metrics.sentence_count), (5, 2))
        self.assertEqual(metrics.sentence_lengths, (3, 2))
        self.assertEqual(metrics.language, "en")

    def test_russian_pronoun_openings_are_retained_as_repetition_signals(self):
        metrics = prose.analyze_prose(
            "Она вошла в комнату.\n\nОна закрыла дверь.\n\nОн остался снаружи.\n",
            language="ru",
        )

        self.assertEqual(metrics.repeated_openings, (("она", 2),))

    def test_dialogue_ratio_recognizes_russian_dash_and_bilingual_quotes(self):
        metrics = prose.analyze_prose(
            "— Я здесь!\nThe room was still.\n\"Come in,\" she said.\n«Входи», — ответил он.\n",
            language="ru",
        )

        self.assertEqual(metrics.dialogue_ratio, 0.75)

    def test_frontmatter_and_fenced_code_are_excluded_from_metrics(self):
        metrics = prose.analyze_prose(
            "---\ntitle: Count nothing here\n---\nVisible words.\n\n```python\n"
            "hidden = 'many code words'\n```\n",
            language="en",
        )

        self.assertEqual(metrics.word_count, 2)
        self.assertEqual(metrics.paragraph_count, 1)

    def test_tilde_fences_and_full_legacy_metric_families(self):
        metrics = prose.analyze_prose(
            "She enters. And she waits.\n\nAlpha alpha alpha.\n\n~~~\nignored she alpha.\n~~~\n",
            language="en",
        )
        self.assertEqual((2, 3, 3), metrics.sentence_lengths)
        self.assertEqual(3.0, metrics.sentence_length_median)
        self.assertEqual(dict(metrics.opener_categories)["pronouns"], 1)
        self.assertEqual(dict(metrics.opener_categories)["conjunctions"], 1)
        self.assertGreater(dict(metrics.pronoun_distribution)["third-feminine"], 0)
        self.assertTrue(any(item[0] == "alpha" for item in metrics.windowed_repetitions))

    def test_unknown_language_falls_back_from_unicode_content(self):
        self.assertEqual(prose.analyze_prose("Тихий вечер.", language="unknown").language, "ru")
        self.assertEqual(prose.analyze_prose("Quiet evening.", language="").language, "en")

    def test_unicode_tokenizer_accepts_letters_and_internal_joiners_only(self):
        metrics = prose.analyze_prose(
            "naïve co-operate l’amour Ελληνικά 漢字 × ÷ ҂ ҈ ́",
            language="unknown",
        )

        self.assertEqual(metrics.word_count, 5)
        self.assertEqual(metrics.language, "en")

    def test_sentence_splitting_matches_legacy_whitespace_boundary(self):
        for text, expected in (
            ('"Go." she said. Then left.', (2, (3, 2))),
            ("Hello!Next. Last one.", (2, (2, 2))),
            ("Стемнело быстро. Ветер стих! Мы ушли… Дом молчал", (4, (2, 2, 2, 2))),
        ):
            with self.subTest(text=text):
                metrics = prose.analyze_prose(text, language="en")
                self.assertEqual((metrics.sentence_count, metrics.sentence_lengths), expected)

    def test_preprocessing_matches_legacy_paragraph_words_and_dialogue(self):
        text = (
            "Before `\"inline quote\" code` words.\n"
            "```python\nignored = 'quoted code'\n```\n"
            "After words.\n"
        )
        metrics = prose.analyze_prose(text, language="en")
        self.assertEqual(metrics.word_count, 7)
        self.assertEqual(metrics.paragraph_count, 1)
        self.assertEqual(metrics.dialogue_ratio, 0.5)

    def test_punctuation_only_sentences_and_paragraphs_match_legacy_behavior(self):
        text = "!!! Text.\n\n...\n\nAlpha alpha alpha.\n"
        metrics = prose.analyze_prose(text, language="en")
        self.assertEqual((4, 3), (metrics.sentence_count, metrics.paragraph_count))
        self.assertEqual(metrics.sentence_lengths, (1, 3))
        self.assertIn(("alpha", 1, 3, 3), metrics.windowed_repetitions)

    def test_legacy_russian_pronoun_groups_and_openers_remain_exact(self):
        grouped = prose.analyze_prose(
            "Мое решение в моем письме, твое мнение в твоем ответе и ее выбор.",
            language="ru",
        )
        self.assertEqual(
            dict(grouped.pronoun_distribution),
            {
                "first-singular": 2,
                "first-plural": 0,
                "second": 2,
                "third-masculine": 0,
                "third-feminine": 1,
                "third-plural": 0,
                "third-neuter": 0,
            },
        )

        opened = prose.analyze_prose(
            "Мое решение принято. Твое письмо пришло. Ее ответ готов.",
            language="ru",
        )
        self.assertEqual(dict(opened.opener_categories)["pronouns"], 3)

    def test_legacy_russian_sample_keeps_full_run_metrics(self):
        sample = """# Глава 1

Я вернулся в дом, когда стемнело, и долго стоял у крыльца, слушая,
как скрипит под ветром старая яблоня — та самая, под которой мы
когда-то зарыли жестяную коробку с письмами.

— Ты опять был там? — спросила мать, не оборачиваясь.

— Был, — сказал я и соврал ей впервые за много лет.

Она вздохнула, и в этом вздохе поместилось всё, что она не сказала.
"""
        metrics = prose.analyze_prose(sample, language="ru")
        self.assertGreater(metrics.word_count, 0)
        self.assertGreater(metrics.sentence_count, 0)
        self.assertEqual(metrics.dialogue_ratio, 2 / 7)


class ProseCheckTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.write("project.md", "---\nschema-version: 1\ntitle: Test\nlanguage: ru\nstatus: drafting\n---\n")
        for directory in ("story/chapters", "work/drafts", "kb/samples"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)

    def write(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def findings(self):
        return prose.check_prose(project.discover_project(self.root))

    def test_allowed_balanced_tags_and_fences_have_no_integrity_warning(self):
        self.write(
            "work/plans/outline.md",
            "---\nstatus: working\n---\n<AI>Текст <hidden>граница</hidden></AI>\n\n"
            "```html\n<AI>literal example\n```\n",
        )

        codes = {item.code for item in self.findings()}
        self.assertNotIn(prose.SOURCE_TAG, codes)
        self.assertNotIn(prose.SOURCE_TAG_POLICY, codes)
        self.assertNotIn(prose.MARKDOWN_FENCE, codes)

    def test_balanced_tags_still_obey_story_draft_and_kb_layer_policy(self):
        self.write(
            "story/chapters/ch-001.md",
            "---\nnumber: 1\n---\n<AI>Accepted</AI> <hidden>Secret</hidden>\n",
        )
        self.write("work/drafts/ch-002.md", "---\nstatus: working\n---\n<AI>Draft</AI>\n")
        self.write("kb/world/rules.md", "<AI>Unconfirmed</AI> <hidden>Allowed</hidden>\n")

        policy = [item for item in self.findings() if item.code == prose.SOURCE_TAG_POLICY]
        self.assertEqual(
            [(item.path, item.message) for item in policy],
            [
                ("kb/world/rules.md", "<AI> source tags are not allowed in durable KB documents"),
                ("story/chapters/ch-001.md", "<AI> source tags are not allowed in accepted story documents"),
                ("story/chapters/ch-001.md", "<hidden> source tags are not allowed in accepted story documents"),
                ("work/drafts/ch-002.md", "<AI> source tags are not allowed in working draft prose"),
            ],
        )

    def test_integrity_scans_non_prose_managed_markdown_but_metrics_do_not(self):
        self.write("kb/canon/fact.md", "<hidden>Unclosed boundary\n")
        self.write("work/reviews/review.md", "~~~text\nunclosed fence\n")
        self.write("story/chapters/ch-001.md", "---\nnumber: 1\n---\nChapter text.\n")

        findings = self.findings()
        self.assertTrue(any(item.code == prose.SOURCE_TAG and item.path == "kb/canon/fact.md" for item in findings))
        self.assertTrue(any(item.code == prose.MARKDOWN_FENCE and item.path == "work/reviews/review.md" for item in findings))
        metric_paths = [item.path for item in findings if item.code == prose.METRICS]
        self.assertEqual(metric_paths, ["story/chapters/ch-001.md"])

    def test_generated_indexes_still_receive_integrity_and_layer_checks(self):
        self.write("story/_index.md", "<AI>Forbidden and unclosed\n~~~text\nunclosed fence\n")

        findings = self.findings()
        index_codes = {
            item.code for item in findings if item.path == "story/_index.md"
        }
        self.assertEqual(
            index_codes,
            {prose.SOURCE_TAG, prose.SOURCE_TAG_POLICY, prose.MARKDOWN_FENCE},
        )
        self.assertFalse(
            any(item.code == prose.METRICS and item.path == "story/_index.md" for item in findings)
        )

    def test_unbalanced_and_crossed_source_tags_report_stable_lines(self):
        self.write(
            "story/chapters/ch-001.md",
            "---\nnumber: 1\n---\n<AI>Текст\n<hidden>Скрыто</AI>\n",
        )
        self.write("story/chapters/ch-002.md", "---\nnumber: 2\n---\n<AI>Без конца\n")

        tags = [item for item in self.findings() if item.code == prose.SOURCE_TAG]
        self.assertEqual([item.line for item in tags], [5, 4])
        self.assertEqual([item.path for item in tags], [
            "story/chapters/ch-001.md",
            "story/chapters/ch-002.md",
        ])

    def test_integrity_includes_project_and_raw_frontmatter(self):
        self.write(
            "project.md",
            "---\nschema-version: 1\ntitle: <AI>Broken\nlanguage: ru\nstatus: drafting\n---\n",
        )
        self.write(
            "kb/world/frontmatter.md",
            "---\ntitle: <hidden>Broken\nsources:\n  - https://example.com\n---\nBody.\n",
        )
        tags = [item for item in self.findings() if item.code == prose.SOURCE_TAG]
        self.assertEqual(
            [("kb/world/frontmatter.md", 2), ("project.md", 3)],
            [(item.path, item.line) for item in tags],
        )

    def test_unclosed_markdown_fence_is_a_mechanical_warning(self):
        self.write("story/chapters/ch-001.md", "---\nnumber: 1\n---\nText.\n```python\ncode\n")

        finding = next(item for item in self.findings() if item.code == prose.MARKDOWN_FENCE)
        self.assertEqual((finding.path, finding.line), ("story/chapters/ch-001.md", 5))

    def test_empty_document_and_repeated_openings_are_reported_without_judgment(self):
        self.write("story/chapters/empty.md", "---\nnumber: 1\n---\n")
        self.write(
            "story/chapters/ch-002.md",
            "---\nnumber: 2\n---\nОна вошла.\n\nОна села.\n",
        )

        findings = self.findings()
        self.assertIn(prose.EMPTY_DOCUMENT, {item.code for item in findings})
        repeated = next(item for item in findings if item.code == prose.REPEATED_OPENING)
        self.assertIn("opening 'она' occurs 2 times", repeated.message)
        messages = "\n".join(item.message.casefold() for item in findings)
        for judgment in ("good", "bad", "publishable", "quality", "хорош", "плох"):
            self.assertNotIn(judgment, messages)

    def test_language_is_inherited_and_each_prose_file_gets_explicit_counts(self):
        self.write("story/chapters/ch-001.md", "---\nnumber: 1\n---\nОна вошла. Он молчал тихо.\n")
        self.write("work/drafts/ch-002.md", "---\nstatus: working\n---\nЧерновик начат.\n")

        counts = [item for item in self.findings() if item.code == prose.METRICS]
        self.assertEqual([item.path for item in counts], [
            "story/chapters/ch-001.md",
            "work/drafts/ch-002.md",
        ])
        self.assertTrue(all("language=ru" in item.message for item in counts))

    def test_missing_manifest_language_falls_back_per_file(self):
        self.write("project.md", "---\nschema-version: 1\ntitle: Test\nstatus: drafting\n---\n")
        self.write("story/chapters/ch-001.md", "---\nnumber: 1\n---\nТихий вечер.\n")

        metrics = next(item for item in self.findings() if item.code == prose.METRICS)
        self.assertIn("language=ru", metrics.message)

    def test_malformed_file_does_not_abort_other_files_and_check_does_not_mutate(self):
        malformed = self.root / "kb/world/bad.md"
        malformed.parent.mkdir(parents=True)
        malformed.write_bytes(b"---\nnumber: 1\n---\n\xff\n")
        self.write("story/chapters/good.md", "---\nnumber: 2\n---\nReadable chapter.\n")
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }

        findings = self.findings()
        after = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        self.assertIn(prose.UNREADABLE_DOCUMENT, {item.code for item in findings})
        self.assertTrue(any(item.code == prose.METRICS and item.path.endswith("good.md") for item in findings))
        self.assertEqual(after, before)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_symlinks_and_nested_projects_are_not_followed(self):
        outside_temporary = tempfile.TemporaryDirectory()
        self.addCleanup(outside_temporary.cleanup)
        outside = Path(outside_temporary.name)
        (outside / "outside.md").write_text("Outside prose.", encoding="utf-8")
        os.symlink(outside / "outside.md", self.root / "story/chapters/link.md")
        nested = self.root / "story/chapters/nested"
        nested.mkdir()
        (nested / "project.md").write_text("---\nschema-version: 1\ntitle: Nested\nlanguage: en\nstatus: drafting\n---\n", encoding="utf-8")
        (nested / "chapter.md").write_text("Nested prose.", encoding="utf-8")
        self.write("story/chapters/local.md", "Local prose.\n")

        paths = {item.path for item in self.findings()}
        self.assertIn("story/chapters/local.md", paths)
        self.assertNotIn("story/chapters/link.md", paths)
        self.assertNotIn("story/chapters/nested/chapter.md", paths)


if __name__ == "__main__":
    unittest.main()
