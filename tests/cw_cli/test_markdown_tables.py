import unittest

from tests.cw_cli import helpers  # noqa: F401
from cwcli.markdown_tables import malformed_table_lines, parse_tables, table_header_lines


class MarkdownTableTests(unittest.TestCase):
    def test_tables_inside_fenced_and_indented_code_are_ignored(self):
        text = "```\n| a | b |\n|---|---|\n```\n~~~\n| c | d |\n|---|---|\n~~~\n    | e | f |\n    |---|---|\n"
        self.assertEqual((), parse_tables(text))
        self.assertEqual((), malformed_table_lines(text))
    def test_parses_trimmed_cells_and_preserves_source_lines(self):
        tables = parse_tables("intro\n\n | Name | Value |\n | :--- | ---: |\n | Mara |  7  |\n")
        self.assertEqual(tables[0].headers, ("Name", "Value"))
        self.assertEqual(tables[0].rows[0].cells, ("Mara", "7"))
        self.assertEqual(tables[0].rows[0].line, 5)

    def test_escaped_pipe_stays_inside_one_cell(self):
        table = parse_tables("| key | text |\n|---|---|\n| one | left \\| right |\n")[0]
        self.assertEqual(table.rows[0].cells, ("one", r"left \| right"))

    def test_even_backslashes_do_not_escape_separator(self):
        table = parse_tables("| a | b | c |\n|---|---|---|\n| one \\\\| two | three |\n")[0]
        self.assertEqual(table.rows[0].cells, ("one " + "\\\\", "two", "three"))

    def test_invalid_or_missing_delimiter_is_not_a_table(self):
        self.assertEqual(parse_tables("| a | b |\n| one | two |\n"), ())
        self.assertEqual(parse_tables("| a | b |\n| -- | --- |\n| x | y |\n"), ())

    def test_russian_unicode_and_non_table_prose_are_preserved(self):
        text = "Мара сказала: один | два.\n\n| Герой | Состояние |\n|---|---|\n| Мара | жива |\n"
        tables = parse_tables(text)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0].rows[0].cells, ("Мара", "жива"))
        self.assertEqual(tables[0].rows[0].line, 5)

    def test_mismatched_body_row_ends_table_without_guessing(self):
        tables = parse_tables("| a | b |\n|---|---|\n| one |\n| two | three |\n")
        self.assertEqual(tables[0].rows, ())

    def test_diagnostics_require_a_credible_table_sequence(self):
        text = "Ordinary prose with left | right but no table delimiter.\n"
        self.assertEqual(malformed_table_lines(text), ())

        mixed = "| good | table |\n|---|---|\n| yes | value |\n\n| broken | table |\n| -- | --- |\n"
        self.assertEqual(table_header_lines(mixed), (1,))
        self.assertEqual(malformed_table_lines(mixed), (5,))


if __name__ == "__main__":
    unittest.main()
