"""Story-project discovery and path-boundary enforcement."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterator

from .documents import Document, parse_document


MANAGED_ROOTS = ("story", "work", "kb")
PROTECTED_ROOT = ".creative-writing"
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)
_WINDOWS_FORBIDDEN_CHARACTERS = frozenset('<>:"\\|?*')


class ProjectDiscoveryError(ValueError):
    """Raised when no enclosing story project can be found."""


class ProjectPathError(ValueError):
    """Raised when a project-relative path is unsafe to use."""


@dataclass(frozen=True)
class Project:
    """A discovered story project and its parsed manifest."""

    root: Path
    manifest: Document

    def resolve(self, relative: str, *, for_write: bool = False) -> Path:
        """Resolve a project-relative path without allowing boundary escapes."""

        relative_path = _relative_path(relative)
        target = self.root / relative_path
        _ensure_lexically_contained(self.root, target)

        if not for_write:
            return target

        if _contains_symlink(self.root, target):
            raise ProjectPathError("write target contains a symlink")
        _ensure_portable_write_path(self.root, relative_path)
        _ensure_resolved_containment(self.root, target)
        nested_root = _nested_project_root(self.root, target)
        if nested_root is not None:
            raise ProjectPathError(f"write target is inside nested project {nested_root}")
        return target

    def iter_managed_markdown(self) -> Iterator[Path]:
        """Yield managed Markdown files without entering links or nested projects."""

        for root_name in MANAGED_ROOTS:
            managed_root = self.root / root_name
            if not managed_root.is_dir() or managed_root.is_symlink():
                continue
            manifest = managed_root / "project.md"
            if manifest.is_file() and not manifest.is_symlink():
                continue
            yield from _iter_markdown(managed_root)

    def relative_id(self, path: Path) -> str:
        """Return a forward-slash identity for a path lexically inside this project."""

        try:
            return path.relative_to(self.root).as_posix()
        except ValueError as error:
            raise ProjectPathError(f"path is outside project: {path}") from error


def discover_project(start: Path) -> Project:
    """Find the nearest ancestor directory with a regular ``project.md`` manifest."""

    candidate = Path(start).absolute()
    if candidate.exists() and not candidate.is_dir():
        candidate = candidate.parent

    for root in (candidate, *candidate.parents):
        manifest_path = root / "project.md"
        if manifest_path.is_symlink() or not manifest_path.is_file():
            continue
        resolved_root = root.resolve()
        resolved_manifest = resolved_root / "project.md"
        if resolved_manifest.is_symlink():
            continue
        return Project(root=resolved_root, manifest=parse_document(resolved_manifest.read_bytes()))

    raise ProjectDiscoveryError(f"no project.md found above {start}")


def _relative_path(relative: str) -> Path:
    if not isinstance(relative, str):
        raise TypeError("project-relative path must be a string")
    if "\\" in relative:
        raise ProjectPathError("project-relative paths must use forward slashes")

    native = Path(relative)
    windows = PureWindowsPath(relative)
    posix = PurePosixPath(relative)
    if native.is_absolute() or posix.is_absolute() or windows.is_absolute() or windows.drive or windows.root:
        raise ProjectPathError("absolute paths are outside project")
    if ".." in native.parts:
        raise ProjectPathError("parent traversal is outside project")
    return native


def _ensure_lexically_contained(root: Path, target: Path) -> None:
    try:
        target.relative_to(root)
    except ValueError as error:
        raise ProjectPathError(f"path is outside project: {target}") from error


def _ensure_resolved_containment(root: Path, target: Path) -> None:
    try:
        target.resolve(strict=False).relative_to(root.resolve())
    except ValueError as error:
        raise ProjectPathError(f"resolved path is outside project: {target}") from error


def _ensure_portable_write_path(root: Path, relative: Path) -> None:
    if relative.parts and relative.parts[0].casefold() == PROTECTED_ROOT:
        raise ProjectPathError(f"write target is under protected {PROTECTED_ROOT}")

    current = root
    for part in relative.parts:
        _validate_portable_name(part)
        _ensure_no_portable_collision(current, part)
        current /= part


def _validate_portable_name(name: str) -> None:
    if unicodedata.normalize("NFC", name) != name:
        raise ProjectPathError(f"path component is not NFC-normalized: {name!r}")
    if name.endswith((".", " ")) or any(character in _WINDOWS_FORBIDDEN_CHARACTERS for character in name):
        raise ProjectPathError(f"path component is not portable to Windows: {name!r}")

    stem = name.rstrip(". ").split(".", 1)[0].upper()
    if stem in _WINDOWS_RESERVED_NAMES:
        raise ProjectPathError(f"Windows reserved path component: {name!r}")


def _ensure_no_portable_collision(parent: Path, name: str) -> None:
    if not parent.is_dir() or parent.is_symlink():
        return

    identity = _portable_name_identity(name)
    for existing in parent.iterdir():
        if existing.name != name and _portable_name_identity(existing.name) == identity:
            raise ProjectPathError(f"case-colliding path component: {name!r}")


def _portable_name_identity(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def _contains_symlink(root: Path, target: Path) -> bool:
    current = root
    if current.is_symlink():
        return True
    for part in target.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            return True
    return False


def _nested_project_root(root: Path, target: Path) -> Path | None:
    directory = target if target.is_dir() else target.parent
    current = root
    for part in directory.relative_to(root).parts:
        current /= part
        manifest = current / "project.md"
        if manifest.is_file() and not manifest.is_symlink():
            return current
    return None


def _iter_markdown(directory: Path) -> Iterator[Path]:
    for path in sorted(
        directory.iterdir(), key=lambda candidate: (_portable_name_identity(candidate.name), candidate.name)
    ):
        if path.is_symlink():
            continue
        if path.is_dir():
            manifest = path / "project.md"
            if manifest.is_file() and not manifest.is_symlink():
                continue
            yield from _iter_markdown(path)
        elif path.is_file() and path.suffix.casefold() == ".md":
            yield path


__all__ = [
    "MANAGED_ROOTS",
    "PROTECTED_ROOT",
    "Project",
    "ProjectDiscoveryError",
    "ProjectPathError",
    "discover_project",
]
