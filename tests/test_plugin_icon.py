import hashlib
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "creative-writing-skills"
ZCODE_ICON_URL = (
    "https://raw.githubusercontent.com/InkyQuill/creative-writing-skills/main/"
    "plugins/creative-writing-skills/assets/scroll-quill.png"
)


class PluginIconTests(unittest.TestCase):
    def test_canonical_manifest_icon_paths_resolve(self):
        manifest = json.loads(
            (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text()
        )

        expected_paths = {
            "composerIcon": "./assets/scroll-quill.svg",
            "logo": "./assets/scroll-quill.png",
            "logoDark": "./assets/scroll-quill.png",
        }
        for field, expected_path in expected_paths.items():
            with self.subTest(field=field):
                self.assertEqual(expected_path, manifest["interface"][field])
                self.assertTrue((PLUGIN_ROOT / expected_path).is_file())

    def test_committed_icon_assets_match_supplied_files(self):
        expected_hashes = {
            "scroll-quill.svg": (
                "24455dd38f41f3afa492ebe551f7b67bb7259242410d50ea18932c648d679cf6"
            ),
            "scroll-quill.png": (
                "7255e47dbc8334aec191f2c27081c6a2c6811a59547ed70cb71405ccaeb22594"
            ),
        }
        for filename, expected_hash in expected_hashes.items():
            with self.subTest(filename=filename):
                asset = PLUGIN_ROOT / "assets" / filename
                self.assertEqual(expected_hash, hashlib.sha256(asset.read_bytes()).hexdigest())

    def test_claude_compatible_manifests_exclude_codex_interface(self):
        for relative_path in (
            "cw/.claude-plugin/plugin.json",
            "cw/.zcode-plugin/plugin.json",
        ):
            with self.subTest(manifest=relative_path):
                manifest = json.loads((REPO_ROOT / relative_path).read_text())
                self.assertNotIn("interface", manifest)

    def test_zcode_marketplace_uses_configured_icon_without_claude_leakage(self):
        config = json.loads((REPO_ROOT / "config/distribution.json").read_text())
        zcode_marketplace = json.loads((REPO_ROOT / "marketplace.json").read_text())
        claude_marketplace = json.loads(
            (REPO_ROOT / ".claude-plugin/marketplace.json").read_text()
        )

        self.assertEqual(ZCODE_ICON_URL, config["zcode"]["icon"])
        self.assertEqual(
            config["zcode"]["icon"], zcode_marketplace["plugins"][0]["icon"]
        )
        self.assertNotIn("icon", claude_marketplace["plugins"][0])


if __name__ == "__main__":
    unittest.main()
