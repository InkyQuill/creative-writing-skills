import io
import json
import tempfile
import unittest
from pathlib import Path

from tests.cw_cli import helpers  # noqa: F401  (sets sys.path to the CLI root)

from cwcli import app
from cwcli.checks import prose_typography


def scan(text):
    return prose_typography.scan_lines([(1, text)])


class TypographyWarningRuleTests(unittest.TestCase):
    def test_straight_double_quote_is_warning(self):
        hits = scan('Он сказал "да", затем ушёл.')
        self.assertEqual([h.code for h in hits], ["CW-PROSE-100"])
        self.assertEqual(hits[0].severity, "warning")

    def test_latin_span_in_straight_quotes_is_info(self):
        hits = scan('Флаг компиляции "warning" включён.')
        self.assertEqual([h.code for h in hits], ["CW-PROSE-100"])
        self.assertEqual(hits[0].severity, "info")

    def test_spaced_hyphen_is_warning(self):
        hits = scan("Это - не тире.")
        self.assertEqual([h.code for h in hits], ["CW-PROSE-101"])

    def test_line_start_hyphen_bullet_is_not_flagged(self):
        self.assertEqual(scan("- пункт списка"), ())

    def test_three_dot_ellipsis_is_warning(self):
        hits = scan("Он замолчал...")
        self.assertEqual([h.code for h in hits], ["CW-PROSE-102"])

    def test_breakable_space_after_single_letter_word_is_warning(self):
        hits = scan("Он шёл в школу, а она осталась.")
        self.assertEqual([h.code for h in hits], ["CW-PROSE-103"])

    def test_nbsp_after_single_letter_word_is_not_flagged(self):
        self.assertEqual(scan("Он шёл в\u00a0школу."), ())

    def test_compound_hyphen_is_not_flagged(self):
        self.assertEqual(scan("Где-то там был светло-жёлтый дом."), ())

    def test_direct_speech_comma_dash_is_not_flagged(self):
        self.assertEqual(scan("«Сроки поедут», — предупредила Петрова."), ())


class TypographyInfoRuleTests(unittest.TestCase):
    def test_long_unseparated_digit_run(self):
        hits = scan("Он выиграл 1000000 рублей.")
        self.assertEqual([h.code for h in hits], ["CW-PROSE-110"])
        self.assertEqual(hits[0].severity, "info")

    def test_four_digit_number_not_flagged(self):
        # 1937-й is the correct form: four digits stay below CW-PROSE-110's
        # five-digit threshold and the hyphenated suffix is not closed up,
        # so no rule may fire.
        self.assertEqual(scan("Год 1937-й."), ())

    def test_decimal_point(self):
        hits = scan("Почти 3.14 метра.")
        self.assertEqual([h.code for h in hits], ["CW-PROSE-111"])

    def test_numero_forms(self):
        # A standalone "и" would also fire CW-PROSE-103 (Task 4 scope), so
        # this line isolates CW-PROSE-112 without the conjunction.
        hits = scan("Договор No. 5, приказ #7.")
        self.assertEqual([h.code for h in hits], ["CW-PROSE-112", "CW-PROSE-112"])

    def test_ordinal_suffix(self):
        hits = scan("Это был 1ый раз.")
        self.assertEqual([h.code for h in hits], ["CW-PROSE-113"])

    def test_closed_up_abbreviation(self):
        # Same CW-PROSE-103 isolation as test_numero_forms.
        hits = scan("Формы т.д., т.п. написаны слитно.")
        self.assertEqual(
            sorted(h.code for h in hits), ["CW-PROSE-114", "CW-PROSE-114"]
        )


class TypographyProseCheckTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.write(
            "project.md",
            "---\nschema-version: 1\ntitle: Test\nlanguage: ru\nstatus: drafting\n---\n",
        )
        (self.root / "story/chapters").mkdir(parents=True, exist_ok=True)

    def write(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_cli(self, *, strict: bool = False):
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = ["check", "prose", ".", "--format", "json"]
        if strict:
            argv.append("--strict")
        status = app.run(argv, cwd=self.root, stdout=stdout, stderr=stderr)
        self.assertEqual("", stderr.getvalue())
        return status, json.loads(stdout.getvalue())

    def typography_findings(self, payload):
        return [
            item
            for item in payload["findings"]
            if item["code"].startswith("CW-PROSE-10")
        ]

    def test_russian_chapter_with_straight_quote_reports_typography_warning(self):
        self.write("story/chapters/ch-001.md", 'Он сказал "да".\n')

        status, payload = self.run_cli()
        self.assertEqual(0, status)
        self.assertEqual([], payload["execution_errors"])
        typography = self.typography_findings(payload)
        self.assertEqual(len(typography), 1)
        self.assertEqual(typography[0]["code"], prose_typography.CW_PROSE_100)
        self.assertEqual(typography[0]["path"], "story/chapters/ch-001.md")
        self.assertEqual(typography[0]["line"], 1)
        self.assertEqual(typography[0]["severity"], "warning")

    def test_english_project_reports_no_typography_findings(self):
        self.write(
            "project.md",
            "---\nschema-version: 1\ntitle: Test\nlanguage: en\nstatus: drafting\n---\n",
        )
        self.write("story/chapters/ch-001.md", 'He said "yes" and left.\n')

        status, payload = self.run_cli()
        self.assertEqual(0, status)
        self.assertEqual([], self.typography_findings(payload))

    def test_strict_run_fails_on_warning_while_default_run_exits_zero(self):
        self.write("story/chapters/ch-001.md", 'Он сказал "да".\n')

        default_status, _ = self.run_cli()
        strict_status, strict_payload = self.run_cli(strict=True)
        self.assertEqual(0, default_status)
        self.assertEqual(1, strict_status)
        self.assertTrue(strict_payload["strict_failure"])


if __name__ == "__main__":
    unittest.main()
