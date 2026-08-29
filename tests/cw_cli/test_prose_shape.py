import unittest

from tests.cw_cli import helpers  # noqa: F401

from cwcli.checks import prose


class ProseShapeMetricTests(unittest.TestCase):
    def test_p90_and_step_on_known_lengths(self):
        text = "Одно короткое. " + "Здесь предложение заметно длиннее, с оборотом. " * 4
        m = prose.analyze_prose(text, language="ru")
        lengths = sorted(m.sentence_lengths)
        n = len(lengths)
        self.assertEqual(m.sentence_length_p90, lengths[min(n - 1, int(0.9 * n))])
        step = sum(
            abs(m.sentence_lengths[i] - m.sentence_lengths[i + 1])
            for i in range(len(m.sentence_lengths) - 1)
        ) / (len(m.sentence_lengths) - 1)
        self.assertAlmostEqual(m.sentence_length_step, step)

    def test_single_sentence_has_zero_step(self):
        m = prose.analyze_prose("Одно целое предложение.", language="ru")
        self.assertEqual(m.sentence_length_step, 0.0)
        self.assertEqual(m.sentence_length_p90, m.sentence_lengths[0])

    def test_em_dash_count(self):
        m = prose.analyze_prose("Он сказал — и замолчал. Она ответила — и ушла.", language="ru")
        self.assertEqual(m.em_dash_count, 2)

    def test_ru_only_fields_are_none_for_english(self):
        m = prose.analyze_prose("He said that it was very odd. Really odd.", language="en")
        self.assertIsNone(m.subordination_mean)
        self.assertIsNone(m.intensifier_count)
        self.assertEqual(m.em_dash_count, 0)

    def test_ru_subordination_and_intensifiers(self):
        m = prose.analyze_prose(
            "Он знал, что она уйдёт, потому что очень устала. Честно, это было странно.",
            language="ru",
        )
        self.assertGreaterEqual(m.subordination_mean, 1.0)
        self.assertEqual(m.intensifier_count, 2)  # «очень» and «Честно»


if __name__ == "__main__":
    unittest.main()
