import importlib.util
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = (_REPO / "plugins/creative-writing-skills/skills/creative-writing-craft"
           / "resources/dialogue_audit.py")


def load_module():
    spec = importlib.util.spec_from_file_location("dialogue_audit", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DialogueAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()

    def test_ru_dialogue_counts_and_attribution(self):
        text = (
            "— Приходи вовремя, — сказал Иван.\n"
            "— Я никогда не опаздываю, — ответила Мария.\n"
            "Описание места действия без реплик.\n"
            "— Учти это, — добавил Иван.\n"
        )
        stats = self.mod.audit_dialogue(text, language="ru")
        self.assertEqual(stats.total_lines, 4)
        self.assertEqual(stats.dialogue_lines, 3)
        self.assertEqual(stats.attribution_lines, 3)
        self.assertEqual(stats.attribution_ratio, 1.0)
        self.assertEqual(stats.max_same_speaker_run, 1)

    def test_same_speaker_run(self):
        text = (
            "— Слушай, — сказал Иван.\n"
            "— Что? — спросил Иван.\n"
            "— Ничего, — ответил Иван.\n"
        )
        stats = self.mod.audit_dialogue(text, language="ru")
        self.assertEqual(stats.max_same_speaker_run, 3)

    def test_detect_language(self):
        self.assertEqual(self.mod.detect_language("Он пошёл домой"), "ru")
        self.assertEqual(self.mod.detect_language("He went home"), "en")

    def test_en_attribution(self):
        text = '"Come here," said John.\n"Why?" asked Mary.\n'
        stats = self.mod.audit_dialogue(text, language="en")
        self.assertEqual(stats.attribution_lines, 2)
        self.assertEqual(stats.max_same_speaker_run, 1)

    def test_speaker_names_are_excluded_from_vocabulary(self):
        # Three attributed lines per speaker with disjoint content words and
        # one shared attribution verb: each speaker's vocabulary is four
        # words, so Jaccard is exactly 1/7 over the name-stripped union.
        # With names left in the vocabulary the union would be nine words
        # and the score 1/9, so the exact value pins the exclusion.
        text = (
            "— Слушай, — сказал Иван.\n"
            "— Осторожно, — сказал Иван.\n"
            "— Тихо, — сказал Иван.\n"
            "— Смотри, — сказал Пётр.\n"
            "— Быстро, — сказал Пётр.\n"
            "— Долго, — сказал Пётр.\n"
        )
        stats = self.mod.audit_dialogue(text, language="ru")
        self.assertEqual(
            stats.speaker_overlap, (("Иван", "Пётр", 1 / 7),)
        )

    def test_main_returns_two_on_missing_file(self):
        self.assertEqual(self.mod.main([str(_REPO / "no-such-file.md")]), 2)
        self.assertEqual(self.mod.main([]), 2)

    def test_main_returns_zero_and_prints_json(self):
        target = _REPO / "test" / "_dialogue_fixture.md"
        target.parent.mkdir(exist_ok=True)
        target.write_text("— Привет, — сказал Иван.\n", encoding="utf-8")
        try:
            import contextlib, io, json
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = self.mod.main([str(target), "--format", "json"])
            self.assertEqual(code, 0)
            payload = json.loads(buffer.getvalue())
            self.assertEqual(payload["dialogue_lines"], 1)
        finally:
            target.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
