"""Side-effect-free diagnostics for the bundled ``cw`` runtime."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from . import __version__


_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class CliDiagnostic:
    name: str
    ok: bool
    message: str
    command: tuple[str, ...] = ()
    required: bool = True
    version: str | None = None


@dataclass(frozen=True)
class CliDoctorReport:
    python: CliDiagnostic
    entrypoint: CliDiagnostic
    direct_invocation: CliDiagnostic
    version_agreement: CliDiagnostic
    launcher: CliDiagnostic

    @property
    def ok(self) -> bool:
        return all(
            diagnostic.ok
            for diagnostic in (
                self.python,
                self.entrypoint,
                self.direct_invocation,
                self.version_agreement,
            )
        )

    def exit_status(self) -> int:
        return 0 if self.ok else 2

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "direct_invocation_is_default": True,
            "python": asdict(self.python),
            "entrypoint": asdict(self.entrypoint),
            "direct_invocation": asdict(self.direct_invocation),
            "version_agreement": asdict(self.version_agreement),
            "launcher": asdict(self.launcher),
        }

    def as_text(self) -> str:
        lines = ["direct invocation is the default solution"]
        for diagnostic in (
            self.python,
            self.entrypoint,
            self.direct_invocation,
            self.version_agreement,
            self.launcher,
        ):
            state = "ok" if diagnostic.ok else "warning" if not diagnostic.required else "error"
            lines.append(f"{diagnostic.name} [{state}] {diagnostic.message}")
            if diagnostic.command:
                lines.append(f"  command: {subprocess.list2cmdline(list(diagnostic.command))}")
        return "\n".join(lines)


def diagnose_cli(entrypoint: Path, python: Path) -> CliDoctorReport:
    """Probe the supplied runtime without creating files or configuring a launcher."""

    python = Path(python)
    entrypoint = Path(entrypoint)
    python_result = _diagnose_python(python)
    entrypoint_result = _diagnose_entrypoint(entrypoint)
    direct_command = (str(python), str(entrypoint), "--version", "--format", "json")

    if python_result.ok and entrypoint_result.ok:
        direct_result, detected_version = _probe_version(
            "direct-invocation", direct_command, required=True
        )
    else:
        direct_result = CliDiagnostic(
            name="direct-invocation",
            ok=False,
            message="direct invocation was not attempted because a required prerequisite failed",
            command=direct_command,
        )
        detected_version = None

    version_ok = direct_result.ok and detected_version == __version__
    version_result = CliDiagnostic(
        name="version-agreement",
        ok=version_ok,
        message=(
            f"entrypoint version {detected_version} agrees with bundled package {__version__}"
            if version_ok
            else f"entrypoint version {detected_version or 'unknown'} does not agree with bundled package {__version__}"
        ),
        version=detected_version,
    )

    launcher_path = shutil.which("cw")
    if launcher_path is None:
        launcher_result = CliDiagnostic(
            name="launcher",
            ok=False,
            required=False,
            message="optional cw launcher was not found; keep using direct invocation",
        )
    else:
        launcher_result, launcher_version = _probe_version(
            "launcher", (launcher_path, "--version", "--format", "json"), required=False
        )
        if launcher_result.ok and launcher_version != __version__:
            launcher_result = CliDiagnostic(
                name="launcher",
                ok=False,
                required=False,
                message=(
                    f"optional launcher reports stale cw {launcher_version}; "
                    f"bundled runtime is {__version__}; keep using direct invocation"
                ),
                command=launcher_result.command,
                version=launcher_version,
            )

    return CliDoctorReport(
        python=python_result,
        entrypoint=entrypoint_result,
        direct_invocation=direct_result,
        version_agreement=version_result,
        launcher=launcher_result,
    )


def _diagnose_python(python: Path) -> CliDiagnostic:
    command = (
        str(python),
        "-c",
        "import json,sys; print(json.dumps({'major':sys.version_info[0],'minor':sys.version_info[1]}))",
    )
    try:
        completed = _run(command)
        payload = _json_stdout(completed)
        major, minor = payload.get("major"), payload.get("minor")
        if not isinstance(major, int) or isinstance(major, bool) or not isinstance(minor, int) or isinstance(minor, bool):
            raise ValueError("interpreter returned an invalid version payload")
        ok = (major, minor) >= (3, 10)
        return CliDiagnostic(
            name="python",
            ok=ok,
            message=f"Python {major}.{minor} {'is supported' if ok else 'is too old; Python 3.10+ is required'}",
            command=command,
            version=f"{major}.{minor}",
        )
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        return CliDiagnostic("python", False, f"Python probe failed safely: {error}", command)


def _diagnose_entrypoint(entrypoint: Path) -> CliDiagnostic:
    try:
        entrypoint_stat = entrypoint.lstat()
        mode = entrypoint_stat.st_mode
        if stat.S_ISLNK(mode):
            raise OSError("entrypoint is a symlink and will not be followed")
        if not stat.S_ISREG(mode):
            raise OSError("entrypoint is not a regular file")
        if mode & 0o444 == 0:
            raise OSError("entrypoint has no readable permission bits")
        descriptor = os.open(entrypoint, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened_stat = os.fstat(descriptor)
            if not stat.S_ISREG(opened_stat.st_mode):
                raise OSError("entrypoint is not a regular file")
            if (entrypoint_stat.st_dev, entrypoint_stat.st_ino) != (
                opened_stat.st_dev,
                opened_stat.st_ino,
            ):
                raise OSError("entrypoint changed while it was being inspected")
        finally:
            os.close(descriptor)
    except OSError as error:
        return CliDiagnostic("entrypoint", False, f"entrypoint is unavailable or unsafe: {error}")
    executable = bool(mode & 0o111)
    detail = "executable bit is present" if executable else "executable bit is unnecessary for direct Python invocation"
    return CliDiagnostic("entrypoint", True, f"readable no-follow regular file; {detail}")


def _probe_version(
    name: str, command: tuple[str, ...], *, required: bool
) -> tuple[CliDiagnostic, str | None]:
    try:
        completed = _run(command)
        payload = _json_stdout(completed)
        if payload.get("name") != "cw" or not isinstance(payload.get("version"), str):
            raise ValueError("version probe returned an invalid cw JSON envelope")
        version = payload["version"]
        return (
            CliDiagnostic(name, True, f"reported cw {version}", command, required, version),
            version,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        return CliDiagnostic(name, False, f"probe failed safely: {error}", command, required), None


def _run(command: tuple[str, ...]) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        timeout=_TIMEOUT_SECONDS,
        env=environment,
    )


def _json_stdout(completed: subprocess.CompletedProcess[bytes]) -> dict[str, object]:
    text = completed.stdout.decode("utf-8")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("probe output must be a JSON object")
    return payload


__all__ = ["CliDiagnostic", "CliDoctorReport", "diagnose_cli"]
