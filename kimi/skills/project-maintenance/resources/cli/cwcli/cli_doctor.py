"""Side-effect-free diagnostics for the bundled ``cw`` runtime."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from . import __version__


_TIMEOUT_SECONDS = 5.0
_MANAGED_MARKER = "managed by creative-writing-skills cli-doctor"


@dataclass(frozen=True)
class CliDiagnostic:
    name: str
    ok: bool
    message: str
    command: tuple[str, ...] = ()
    required: bool = True
    version: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ok": self.ok,
            "message": self.message,
            "command": list(self.command),
            "required": self.required,
            "version": self.version,
        }


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
            "python": self.python.as_dict(),
            "entrypoint": self.entrypoint.as_dict(),
            "direct_invocation": self.direct_invocation.as_dict(),
            "version_agreement": self.version_agreement.as_dict(),
            "launcher": self.launcher.as_dict(),
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
                lines.append(f"  command: {_render_command(diagnostic.command)}")
        return "\n".join(lines)


def diagnose_cli(
    entrypoint: Path,
    python: Path,
    *,
    repair_launcher: bool = False,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> CliDoctorReport:
    """Probe the runtime and optionally install or refresh a managed launcher."""

    try:
        python = Path(python)
        python_text = str(python)
    except (OSError, TypeError, UnicodeError, ValueError) as error:
        python_text = "<invalid-python-path>"
        python_result = CliDiagnostic(
            "python", False, f"Python path cannot be represented safely: {error}"
        )
    else:
        python_result = _diagnose_python(python)
    try:
        entrypoint = Path(entrypoint)
        entrypoint_text = str(entrypoint)
    except (OSError, TypeError, UnicodeError, ValueError) as error:
        entrypoint_text = "<invalid-entrypoint-path>"
        entrypoint_result = CliDiagnostic(
            "entrypoint", False, f"entrypoint path cannot be represented safely: {error}"
        )
    else:
        entrypoint_result = _diagnose_entrypoint(entrypoint)
    direct_command = (python_text, entrypoint_text, "--version", "--format", "json")

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

    launcher_action: str | None = None
    launcher_problem: str | None = None
    if repair_launcher and version_result.ok:
        try:
            launcher_path, launcher_action, launcher_problem = _ensure_launcher(
                entrypoint,
                python,
                environ=os.environ if environ is None else environ,
                home=Path.home() if home is None else Path(home),
            )
        except (OSError, TypeError, UnicodeError, ValueError) as error:
            launcher_path = None
            launcher_problem = f"automatic cw launcher setup failed safely: {error}"
    else:
        launcher_path = None

    try:
        if launcher_path is None:
            search_path = None if environ is None else environ.get("PATH")
            launcher_path = shutil.which("cw", path=search_path)
    except (OSError, TypeError, UnicodeError, ValueError) as error:
        launcher_result = CliDiagnostic(
            name="launcher",
            ok=False,
            required=False,
            message=f"optional launcher discovery failed safely: {error}",
        )
        launcher_path = None
        launcher_failed = True
    else:
        launcher_failed = False
    if launcher_path is None and not launcher_failed:
        launcher_result = CliDiagnostic(
            name="launcher",
            ok=False,
            required=False,
            message=(
                launcher_problem
                or "cw launcher was not found and no safe user-owned PATH directory was available"
            ),
        )
    elif launcher_path is not None:
        launcher_result, launcher_version = _probe_version(
            "launcher", (launcher_path, "--version", "--format", "json"), required=False
        )
        if launcher_result.ok and launcher_version != __version__:
            launcher_result = CliDiagnostic(
                name="launcher",
                ok=False,
                required=False,
                message=(
                    f"launcher reports stale cw {launcher_version}; bundled runtime is {__version__}; "
                    "automatic repair was not safe"
                ),
                command=launcher_result.command,
                version=launcher_version,
            )
        elif launcher_result.ok and launcher_action is not None:
            launcher_result = CliDiagnostic(
                name="launcher",
                ok=True,
                required=False,
                message=f"managed cw launcher {launcher_action} and verified",
                command=launcher_result.command,
                version=launcher_version,
            )
        elif launcher_result.ok and launcher_problem is not None:
            launcher_result = CliDiagnostic(
                name="launcher",
                ok=True,
                required=False,
                message=f"{launcher_problem}; the existing launcher still reports the current version",
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


def _ensure_launcher(
    entrypoint: Path,
    python: Path,
    *,
    environ: Mapping[str, str],
    home: Path,
) -> tuple[str | None, str | None, str | None]:
    path_value = environ.get("PATH", "")
    discovered = shutil.which("cw", path=path_value)
    desired = _launcher_bytes(entrypoint, python)
    if discovered is not None:
        target = Path(discovered)
        if _safe_launcher_target(target, home, allow_missing=False):
            current = target.read_bytes()
            if current == desired:
                return str(target), None, None
            if _is_repairable_launcher(current):
                _replace_launcher(target, desired)
                return str(target), "refreshed", None
        return None, None, "existing cw launcher is not a managed user-owned file; it was not overwritten"

    name = "cw.cmd" if os.name == "nt" else "cw"
    for raw_directory in path_value.split(os.pathsep):
        if not raw_directory:
            continue
        directory = Path(raw_directory)
        target = directory / name
        if not _safe_launcher_target(target, home, allow_missing=True):
            continue
        if os.path.lexists(target):
            try:
                if not _is_repairable_launcher(target.read_bytes()):
                    continue
            except OSError:
                continue
        _replace_launcher(target, desired)
        return str(target), "installed", None
    return None, None, "cw launcher could not be installed: no safe user-owned directory is present in PATH"


def _launcher_bytes(entrypoint: Path, python: Path) -> bytes:
    if os.name == "nt":
        command = subprocess.list2cmdline([str(python), str(entrypoint)])
        return f"@rem {_MANAGED_MARKER}\r\n@{command} %*\r\n".encode("utf-8")
    return (
        f"#!/bin/sh\n# {_MANAGED_MARKER}\n"
        f"exec {shlex.quote(str(python))} {shlex.quote(str(entrypoint))} \"$@\"\n"
    ).encode("utf-8")


def _is_managed_launcher(content: bytes) -> bool:
    return content.startswith(
        (
            f"@rem {_MANAGED_MARKER}\r\n" if os.name == "nt" else f"#!/bin/sh\n# {_MANAGED_MARKER}\n"
        ).encode("utf-8")
    )


def _is_repairable_launcher(content: bytes) -> bool:
    if _is_managed_launcher(content):
        return True
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if os.name == "nt":
        lines = text.splitlines()
        return (
            len(lines) == 1
            and lines[0].startswith("@py -3 \"")
            and lines[0].endswith("\\project-maintenance\\resources\\cli\\cw.py\" %*")
        )
    lines = text.splitlines()
    if len(lines) != 2 or lines[0] != "#!/bin/sh" or not lines[1].startswith("exec "):
        return False
    try:
        command = shlex.split(lines[1].removeprefix("exec "))
    except ValueError:
        return False
    return (
        len(command) == 3
        and command[2] == "$@"
        and command[1].endswith("/project-maintenance/resources/cli/cw.py")
    )


def _safe_launcher_target(target: Path, home: Path, *, allow_missing: bool) -> bool:
    try:
        home_real = home.resolve(strict=True)
        directory_real = target.parent.resolve(strict=True)
        directory_real.relative_to(home_real)
        if target.parent.absolute() != directory_real:
            return False
        directory_stat = directory_real.stat()
        if not stat.S_ISDIR(directory_stat.st_mode) or not os.access(directory_real, os.W_OK):
            return False
        if hasattr(os, "getuid") and directory_stat.st_uid != os.getuid():
            return False
        entry = target.lstat()
    except FileNotFoundError:
        return allow_missing and target.parent.is_dir()
    except (OSError, RuntimeError, ValueError):
        return False
    if not stat.S_ISREG(entry.st_mode):
        return False
    return not hasattr(os, "getuid") or entry.st_uid == os.getuid()


def _replace_launcher(target: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".cw-launcher-", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != "nt":
            temporary.chmod(0o700)
        os.replace(temporary, target)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


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
    except (OSError, TypeError, UnicodeError, ValueError) as error:
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


def _render_command(command: tuple[str, ...], *, windows: bool | None = None) -> str:
    """Render argv for the current shell family without changing the executable data."""

    if windows is None:
        windows = os.name == "nt"
    return subprocess.list2cmdline(list(command)) if windows else shlex.join(command)


__all__ = ["CliDiagnostic", "CliDoctorReport", "diagnose_cli"]
