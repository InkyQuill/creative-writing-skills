import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
ANALYZE_PATH = (
    REPO_ROOT
    / "plugins/creative-writing-skills/skills/story-review/resources/prose-critique/analyze.py"
)


def load_analyze():
    spec = importlib.util.spec_from_file_location("analyze_prose", ANALYZE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ANALYZE = load_analyze()

RUSSIAN_SAMPLE = """# Глава 1

Я вернулся в дом, когда стемнело, и долго стоял у крыльца, слушая,
как скрипит под ветром старая яблоня — та самая, под которой мы
когда-то зарыли жестяную коробку с письмами.

— Ты опять был там? — спросила мать, не оборачиваясь.

— Был, — сказал я и соврал ей впервые за много лет.

Она вздохнула, и в этом вздохе поместилось всё, что она не сказала.
"""


class AnalyzeProseLanguageTests(unittest.TestCase):
    def test_cyrillic_words_are_counted(self):
        found = ANALYZE.words("Я вернулся в дом, когда стемнело")
        self.assertEqual(found, ["я", "вернулся", "в", "дом", "когда", "стемнело"])

    def test_russian_sentences_are_split(self):
        sentences = ANALYZE.get_sentences("Стемнело быстро. Ветер стих! Мы ушли… Дом молчал")
        self.assertEqual(len(sentences), 4)

    def test_quotation_and_dash_dialogue_detection(self):
        self.assertTrue(ANALYZE.QUOTE_RE.search("Она ответила: «позже»"))
        self.assertTrue(ANALYZE.QUOTE_RE.search('He said "later"'))
        self.assertFalse(ANALYZE.QUOTE_RE.search("Ни одного упоминания дома не осталось"))

    def test_russian_pronouns_are_grouped(self):
        found = ANALYZE.words("Я сказал, что мы уйдём, а она останется")
        groups = ANALYZE.PRONOUN_GROUPS
        first_singular = sum(
            found.count(word) for word in groups["1st sing (I/me/my; я/меня/мой)"]
        )
        first_plural = sum(
            found.count(word) for word in groups["1st plur (we/us/our; мы/нас/наш)"]
        )
        third_fem = sum(
            found.count(word) for word in groups["3rd fem (she/her; она/её/ей)"]
        )
        self.assertEqual(first_singular, 1)
        self.assertEqual(first_plural, 1)
        self.assertEqual(third_fem, 1)

    def test_unaccented_russian_pronouns_are_grouped(self):
        output = io.StringIO()
        with redirect_stdout(output):
            ANALYZE.print_pronouns(
                "Мое решение в моем письме, твое мнение в твоем ответе и ее выбор."
            )
        text = output.getvalue()
        self.assertRegex(text, r"1st sing .*\s+2 \(")
        self.assertRegex(text, r"2nd .*\s+2 \(")
        self.assertRegex(text, r"3rd fem .*\s+1 \(")

    def test_unaccented_russian_pronouns_are_sentence_openers(self):
        output = io.StringIO()
        with redirect_stdout(output):
            ANALYZE.print_sentence_openers(
                ["Мое решение принято.", "Твое письмо пришло.", "Ее ответ готов."]
            )
        self.assertIn("Pronoun starts:      3 (100%)", output.getvalue())

    def test_full_run_on_russian_markdown(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "chapter-01.md"
            path.write_text(RUSSIAN_SAMPLE, encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output), mock.patch.object(
                sys, "argv", ["analyze.py", str(path)]
            ):
                status = ANALYZE.main()
        self.assertEqual(status, 0)
        text = output.getvalue()
        self.assertIn("Total words:", text)
        self.assertNotIn("(no words found)", text)
        self.assertNotIn("(no sentences found)", text)
        # Both dash-dialogue lines must register.
        self.assertIn("Dialogue lines:   2", text)
        self.assertRegex(text, r"Mean:\s+\d+\.\d words")


if __name__ == "__main__":
    unittest.main()
