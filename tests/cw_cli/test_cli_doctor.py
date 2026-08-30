import io
import json
import os
import shlex
import stat
import subprocess
import shutil
import sys
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from unittest import mock

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import __version__, app, cli_doctor


class CliDoctorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entrypoint = (
            helpers.REPO_ROOT
            / "plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cw.py"
        )

    def test_real_bundled_direct_invocation_works_without_launcher_or_executable_bit(self):
        mode = self.entrypoint.stat().st_mode
        self.entrypoint.chmod(mode & ~0o111)
        self.addCleanup(self.entrypoint.chmod, mode)
        with mock.patch("cwcli.cli_doctor.shutil.which", return_value=None):
            report = cli_doctor.diagnose_cli(self.entrypoint, Path(sys.executable))

        self.assertTrue(report.ok)
        self.assertTrue(report.direct_invocation.ok)
        self.assertTrue(report.version_agreement.ok)
        self.assertFalse(report.launcher.required)
        self.assertFalse(report.launcher.ok)
        self.assertIn("unnecessary", report.entrypoint.message)

    def test_python_39_fails_before_direct_probe_and_310_is_accepted(self):
        old = subprocess.CompletedProcess([], 0, b'{"major":3,"minor":9}\n', b"")
        current = subprocess.CompletedProcess([], 0, b'{"major":3,"minor":10}\n', b"")
        version = subprocess.CompletedProcess(
            [], 0, json.dumps({"name": "cw", "version": __version__}).encode(), b""
        )
        with mock.patch("cwcli.cli_doctor._run", return_value=old) as run:
            with mock.patch("cwcli.cli_doctor.shutil.which", return_value=None):
                old_report = cli_doctor.diagnose_cli(self.entrypoint, Path("python"))
        self.assertFalse(old_report.python.ok)
        self.assertFalse(old_report.direct_invocation.ok)
        self.assertEqual(1, run.call_count)

        with mock.patch("cwcli.cli_doctor._run", side_effect=(current, version)):
            with mock.patch("cwcli.cli_doctor.shutil.which", return_value=None):
                current_report = cli_doctor.diagnose_cli(self.entrypoint, Path("python"))
        self.assertTrue(current_report.ok)

    def test_missing_symlink_and_unreadable_entrypoints_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = root / "missing.py"
            self.assertFalse(cli_doctor.diagnose_cli(missing, Path(sys.executable)).entrypoint.ok)

            if hasattr(os, "symlink"):
                linked = root / "linked.py"
                linked.symlink_to(self.entrypoint)
                self.assertIn(
                    "symlink",
                    cli_doctor.diagnose_cli(linked, Path(sys.executable)).entrypoint.message,
                )

            unreadable = root / "unreadable.py"
            unreadable.write_text("print('x')", encoding="utf-8")
            unreadable.chmod(0)
            self.assertFalse(
                cli_doctor.diagnose_cli(unreadable, Path(sys.executable)).entrypoint.ok
            )

    def test_mismatched_stale_version_is_a_required_failure(self):
        py = subprocess.CompletedProcess([], 0, b'{"major":3,"minor":10}', b"")
        stale = subprocess.CompletedProcess([], 0, b'{"name":"cw","version":"0.0.0"}', b"")
        with mock.patch("cwcli.cli_doctor._run", side_effect=(py, stale)):
            with mock.patch("cwcli.cli_doctor.shutil.which", return_value=None):
                report = cli_doctor.diagnose_cli(self.entrypoint, Path("python"))
        self.assertTrue(report.direct_invocation.ok)
        self.assertFalse(report.version_agreement.ok)
        self.assertEqual(2, report.exit_status())

    def test_timeout_invalid_utf8_and_broken_optional_launcher_are_safe(self):
        py = subprocess.CompletedProcess([], 0, b'{"major":3,"minor":10}', b"")
        invalid = subprocess.CompletedProcess([], 0, b"\xff", b"")
        with mock.patch("cwcli.cli_doctor._run", side_effect=(py, invalid)):
            with mock.patch("cwcli.cli_doctor.shutil.which", return_value=None):
                invalid_report = cli_doctor.diagnose_cli(self.entrypoint, Path("python"))
        self.assertFalse(invalid_report.direct_invocation.ok)

        with mock.patch(
            "cwcli.cli_doctor._run", side_effect=subprocess.TimeoutExpired(["python"], 5)
        ):
            timeout_report = cli_doctor.diagnose_cli(self.entrypoint, Path("python"))
        self.assertFalse(timeout_report.python.ok)
        self.assertIn("timed out", timeout_report.python.message)

        direct = subprocess.CompletedProcess(
            [], 0, json.dumps({"name": "cw", "version": __version__}).encode(), b""
        )
        with mock.patch("cwcli.cli_doctor._run", side_effect=(py, direct, subprocess.CalledProcessError(1, ["cw"]))):
            with mock.patch("cwcli.cli_doctor.shutil.which", return_value="/bin/cw"):
                launcher_report = cli_doctor.diagnose_cli(self.entrypoint, Path("python"))
        self.assertTrue(launcher_report.ok)
        self.assertFalse(launcher_report.launcher.ok)
        self.assertFalse(launcher_report.launcher.required)

        stale_launcher = subprocess.CompletedProcess(
            [], 0, b'{"name":"cw","version":"0.0.0"}', b""
        )
        with mock.patch("cwcli.cli_doctor._run", side_effect=(py, direct, stale_launcher)):
            with mock.patch("cwcli.cli_doctor.shutil.which", return_value="/bin/cw"):
                stale_report = cli_doctor.diagnose_cli(self.entrypoint, Path("python"))
        self.assertTrue(stale_report.ok)
        self.assertFalse(stale_report.launcher.ok)
        self.assertIn("stale", stale_report.launcher.message)

    def test_probe_sets_no_bytecode_environment_and_preserves_windows_path_argument(self):
        completed = subprocess.CompletedProcess([], 0, b'{}', b"")
        windows = str(PureWindowsPath("C:/Program Files/Python/python.exe"))
        with mock.patch("cwcli.cli_doctor.subprocess.run", return_value=completed) as run:
            cli_doctor._run((windows, "--version"))
        args, kwargs = run.call_args
        self.assertEqual(windows, args[0][0])
        self.assertEqual("1", kwargs["env"]["PYTHONDONTWRITEBYTECODE"])
        self.assertEqual(subprocess.DEVNULL, kwargs["stdin"])
        self.assertEqual(5.0, kwargs["timeout"])

    def test_direct_display_quotes_posix_metacharacters_and_windows_branch(self):
        argv = (
            "/tmp/Python $(touch nope)",
            "/tmp/cw `id`; nope.py",
            "--version",
            "--format",
            "json",
        )
        self.assertEqual(shlex.join(argv), cli_doctor._render_command(argv, windows=False))
        self.assertEqual(
            subprocess.list2cmdline(list(argv)),
            cli_doctor._render_command(argv, windows=True),
        )
        diagnostic = cli_doctor.CliDiagnostic("direct", True, "ok", argv)
        report = cli_doctor.CliDoctorReport(
            diagnostic,
            diagnostic,
            diagnostic,
            diagnostic,
            cli_doctor.CliDiagnostic("launcher", False, "optional", required=False),
        )
        self.assertEqual(list(argv), report.as_dict()["direct_invocation"]["command"])
        with mock.patch("cwcli.cli_doctor.os.name", "posix"):
            self.assertIn(shlex.join(argv), report.as_text())

    def test_malformed_entrypoint_paths_never_escape_diagnosis(self):
        report = cli_doctor.diagnose_cli(Path("bad\x00entrypoint.py"), Path(sys.executable))
        self.assertFalse(report.entrypoint.ok)
        self.assertEqual(2, report.exit_status())
        self.assertIn("unsafe", report.entrypoint.message)

        malformed = mock.Mock()
        malformed.__fspath__ = mock.Mock(side_effect=UnicodeError("encoding injected"))
        report = cli_doctor.diagnose_cli(malformed, Path(sys.executable))
        self.assertFalse(report.entrypoint.ok)
        self.assertEqual(2, report.exit_status())

    def test_cli_doctor_is_projectless_and_text_json_agree(self):
        with tempfile.TemporaryDirectory() as directory:
            stdout, stderr = io.StringIO(), io.StringIO()
            with mock.patch(
                "cwcli.cli_doctor._ensure_launcher",
                return_value=(None, None, "no safe test launcher directory"),
            ), mock.patch("cwcli.cli_doctor.shutil.which", return_value=None):
                status = app.run(
                    ["cli-doctor", "--format", "json"],
                    cwd=Path(directory),
                    stdout=stdout,
                    stderr=stderr,
                )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, status)
            self.assertEqual("", stderr.getvalue())
            self.assertTrue(payload["direct_invocation_is_default"])
            self.assertFalse(payload["launcher"]["required"])

            stdout = io.StringIO()
            with mock.patch(
                "cwcli.cli_doctor._ensure_launcher",
                return_value=(None, None, "no safe test launcher directory"),
            ), mock.patch("cwcli.cli_doctor.shutil.which", return_value=None):
                status = app.run(
                    ["cli-doctor"], cwd=Path(directory), stdout=stdout, stderr=io.StringIO()
                )
            self.assertEqual(0, status)
            self.assertIn("direct invocation is the default solution", stdout.getvalue())
            self.assertIn(__version__, stdout.getvalue())

    def test_command_installs_and_refreshes_managed_launcher_for_new_plugin_path(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            launcher_directory = home / "bin"
            launcher_directory.mkdir()
            environment = {"PATH": str(launcher_directory)}

            installed = cli_doctor.diagnose_cli(
                self.entrypoint,
                Path(sys.executable),
                repair_launcher=True,
                environ=environment,
                home=home,
            )
            launcher = launcher_directory / "cw"
            self.assertTrue(installed.launcher.ok)
            self.assertIn("installed", installed.launcher.message)
            self.assertIn(str(self.entrypoint), launcher.read_text(encoding="utf-8"))
            self.assertEqual(0o700, stat.S_IMODE(launcher.stat().st_mode))

            updated_cli = home / "updated plugin" / "resources" / "cli"
            shutil.copytree(self.entrypoint.parent, updated_cli)
            updated_entrypoint = updated_cli / "cw.py"
            refreshed = cli_doctor.diagnose_cli(
                updated_entrypoint,
                Path(sys.executable),
                repair_launcher=True,
                environ=environment,
                home=home,
            )

            self.assertTrue(refreshed.launcher.ok)
            self.assertIn("refreshed", refreshed.launcher.message)
            wrapper = launcher.read_text(encoding="utf-8")
            self.assertIn(str(updated_entrypoint), wrapper)
            self.assertNotIn(str(self.entrypoint), wrapper)

    def test_automatic_setup_never_overwrites_an_unmanaged_path_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            launcher_directory = home / "bin"
            launcher_directory.mkdir()
            launcher = launcher_directory / "cw"
            launcher.write_text("author-owned\n", encoding="utf-8")

            report = cli_doctor.diagnose_cli(
                self.entrypoint,
                Path(sys.executable),
                repair_launcher=True,
                environ={"PATH": str(launcher_directory)},
                home=home,
            )

            self.assertTrue(report.ok)
            self.assertFalse(report.launcher.ok)
            self.assertEqual("author-owned\n", launcher.read_text(encoding="utf-8"))

    def test_automatic_setup_adopts_the_legacy_documented_wrapper(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            launcher_directory = home / "bin"
            launcher_directory.mkdir()
            launcher = launcher_directory / "cw"
            legacy_entrypoint = (
                home
                / "old plugin/project-maintenance/resources/cli/cw.py"
            )
            launcher.write_text(
                f'#!/bin/sh\nexec python3 "{legacy_entrypoint}" "$@"\n',
                encoding="utf-8",
            )
            launcher.chmod(0o700)

            report = cli_doctor.diagnose_cli(
                self.entrypoint,
                Path(sys.executable),
                repair_launcher=True,
                environ={"PATH": str(launcher_directory)},
                home=home,
            )

            self.assertTrue(report.launcher.ok)
            self.assertIn("refreshed", report.launcher.message)
            wrapper = launcher.read_text(encoding="utf-8")
            self.assertIn("managed by creative-writing-skills cli-doctor", wrapper)
            self.assertIn(str(self.entrypoint), wrapper)


if __name__ == "__main__":
    unittest.main()
