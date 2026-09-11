import json
import unittest
import tempfile
from pathlib import Path
from scripts.validate_distribution import validate
from scripts.sync_claude_distribution import render_distribution

ROOT = Path(__file__).resolve().parents[1]


class TranslationDistributionTests(unittest.TestCase):
    def test_translation_skills_are_installable_in_all_generated_runtimes(self):
        config = json.loads((ROOT / 'config/distribution.json').read_text())
        expected = {'literary-translation', 'translation-memory', 'translation-review'}
        self.assertTrue(expected <= set(config['authored_skills']))
        self.assertEqual(35, len(config['canonical_skills']))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'cw'
            render_distribution(output)
            for name in expected:
                self.assertTrue((output / 'skills' / name / 'SKILL.md').is_file())
                self.assertFalse((output / 'skills' / name / 'agents/openai.yaml').exists())
