import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.automatic_release import (
    MANIFEST,
    check_versions,
    prepare_assets,
    release_notes,
    stable_version,
    verify_source,
    version_change,
)
from scripts.release import ReleaseError, run_release


class AutomaticReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / MANIFEST).parent.mkdir(parents=True)
        self.write_version("0.11.0")
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Release Test")
        self.git("config", "user.email", "release@example.com")
        self.before = self.commit()
        self.git("update-ref", "refs/remotes/origin/main", self.before)

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.root, check=True, capture_output=True, text=True
        ).stdout.strip()

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-m", "test release metadata")
        return self.git("rev-parse", "HEAD")

    def write_version(self, version):
        (self.root / MANIFEST).write_text(json.dumps({"version": version}))
        (self.root / "version.txt").write_text(version + "\n")
        (self.root / ".release-please-manifest.json").write_text(
            json.dumps({".": version})
        )

    def test_runtime_manifest_is_authoritative_and_tracking_must_match(self):
        self.assertEqual("0.11.0", check_versions(self.root))
        (self.root / "version.txt").write_text("0.12.0\n")
        with self.assertRaisesRegex(ValueError, "differs"):
            check_versions(self.root)
        (self.root / "version.txt").write_text("0.11.0\n")
        (self.root / ".release-please-manifest.json").write_text('{".": "0.12.0"}')
        with self.assertRaisesRegex(ValueError, "differs"):
            check_versions(self.root)

    def test_version_change_only_releases_an_increasing_version(self):
        self.assertIsNone(version_change(self.root, self.before))
        self.write_version("0.12.0")
        self.assertEqual("v0.12.0", version_change(self.root, self.before))
        self.assertIsNone(version_change(self.root, ""))
        self.write_version("0.10.0")
        with self.assertRaisesRegex(ValueError, "increase"):
            version_change(self.root, self.before)

    def test_verification_rejects_wrong_tag_sha_and_moving_tags(self):
        verify_source(self.root, "v0.11.0", self.before)
        with self.assertRaisesRegex(ValueError, "does not match"):
            verify_source(self.root, "v0.12.0", self.before)
        with self.assertRaisesRegex(ValueError, "checkout"):
            verify_source(self.root, "v0.11.0", "a" * 40)
        self.git("tag", "v0.12.0")
        self.write_version("0.12.0")
        head = self.commit()
        self.git("update-ref", "refs/remotes/origin/main", head)
        with self.assertRaisesRegex(ValueError, "another commit"):
            verify_source(self.root, "v0.12.0", head)
        self.assertEqual(self.before, self.git("rev-parse", "v0.12.0"))

    def test_verification_requires_a_commit_on_main(self):
        self.write_version("0.12.0")
        head = self.commit()
        with self.assertRaises(subprocess.CalledProcessError):
            verify_source(self.root, "v0.12.0", head)

    def test_release_notes_are_exactly_one_matching_section(self):
        notes = "# Changelog\n\n## [0.12.0](https://example.test) (2026-10-07)\n\n### Features\n\nNew.\n\n## 0.11.0\n\nOld.\n"
        actual = release_notes(notes, "0.12.0")
        self.assertIn("### Features", actual)
        self.assertNotIn("Old.", actual)
        self.assertEqual("## 0.11.0\n\nOld.\n", release_notes(notes, "0.11.0"))
        with self.assertRaisesRegex(ValueError, "no entry"):
            release_notes(notes, "0.1.0")

    def assets_fixture(self):
        (self.root / "config").mkdir()
        (self.root / "config/distribution.json").write_text(
            json.dumps({"canonical_skills": ["first", "second"]})
        )
        (self.root / "CHANGELOG.md").write_text("# Changelog\n\n## 0.11.0\n\nNotes.\n")
        directory = self.root / "zips"
        directory.mkdir()
        (directory / "first.skill").write_bytes(b"first")
        (directory / "second.skill").write_bytes(b"second")
        return directory

    def test_published_checksums_match_built_bytes_in_exact_inventory(self):
        directory = self.assets_fixture()
        prepare_assets(self.root, "v0.11.0")
        expected = "".join(
            f"{hashlib.sha256(name.encode()).hexdigest()}  {name}.skill\n"
            for name in ("first", "second")
        )
        self.assertEqual(expected, (directory / "SHA256SUMS").read_text())
        self.assertEqual(
            "## 0.11.0\n\nNotes.\n", (directory / "RELEASE_NOTES.md").read_text()
        )
        (directory / "unexpected.skill").write_bytes(b"unknown")
        with self.assertRaisesRegex(ValueError, "inventory"):
            prepare_assets(self.root, "v0.11.0")

    def test_missing_empty_or_linked_assets_block_publication(self):
        directory = self.assets_fixture()
        asset = directory / "first.skill"
        asset.unlink()
        with self.assertRaisesRegex(ValueError, "inventory"):
            prepare_assets(self.root, "v0.11.0")
        asset.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "empty"):
            prepare_assets(self.root, "v0.11.0")
        asset.unlink()
        asset.symlink_to(directory / "second.skill")
        with self.assertRaisesRegex(ValueError, "unsafe"):
            prepare_assets(self.root, "v0.11.0")

    def test_manual_release_cannot_compete_with_release_please(self):
        (self.root / "release-please-config.json").write_text("{}")
        runner = mock.Mock()
        with self.assertRaisesRegex(ReleaseError, "managed by release-please"):
            run_release(self.root, "minor", runner=runner)
        runner.assert_not_called()
        self.assertEqual("0.11.0", check_versions(self.root))

    def test_rejects_nonstable_versions_and_unsafe_git_refs(self):
        for value in ("v0.11.0", "0.11", "01.11.0", "0.12.0-dev", "--help", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                stable_version(value)
        with self.assertRaisesRegex(ValueError, "full Git SHA"):
            version_change(self.root, "--help")
