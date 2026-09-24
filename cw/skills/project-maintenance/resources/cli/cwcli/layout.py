"""Project-local folder choices and read-only discovery of existing content."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path, PurePosixPath

from .project import Project


class LayoutAmbiguity(ValueError):
    """Several populated folders could serve the same role."""


ROLE_CANDIDATES = {
    "chapters": ("chapters", "story/chapters"),
    "side-stories": ("side-stories", "story/side-stories"),
    "drafts": ("drafts", "work/drafts"),
    "characters": ("characters", "kb/characters"),
    "world": ("world", "kb/world"),
    "plans": ("plans", "work/plans"),
    "reviews": ("reviews", "work/reviews"),
    "archive": ("archive", "work/archive"),
}
LAYOUT_FILE = ".cws-layout.json"


def validate_role_path(project: Project, relative: str) -> str:
    """Accept only a plain, project-relative directory without linked components."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("layout role path must be a project-relative folder")
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise ValueError("layout role path must be a project-relative folder")
    project.resolve(relative + "/.layout-check", for_write=True)
    return relative


def load_layout(project: Project) -> dict[str, str]:
    """Read explicit folder selections from the separate project layout file."""
    path = project.root / LAYOUT_FILE
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return {}
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("layout file must be a regular file")
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            fd = -1
            data = json.load(stream)
    finally:
        if fd >= 0:
            os.close(fd)
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("roles"), dict):
        raise ValueError("invalid .cws-layout.json: expected version 1 and roles object")
    roles = data["roles"]
    for role, relative in roles.items():
        if role not in ROLE_CANDIDATES:
            raise ValueError(f"unknown layout role: {role}")
        validate_role_path(project, relative)
    return roles


def render_layout(roles: dict[str, str]) -> bytes:
    return (json.dumps({"version": 1, "roles": roles}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def inventory_layout(project: Project) -> dict[str, object]:
    """Report populated candidate folders without changing or choosing paths."""

    selected_roles = load_layout(project)
    roles: dict[str, dict[str, object]] = {}
    ambiguous: list[str] = []
    for role, options in ROLE_CANDIDATES.items():
        populated: list[str] = []
        for relative in options:
            directory = project.root / relative
            if not _safe_directory(project.root, directory):
                continue
            if any(
                child.is_file() and not child.is_symlink()
                and child.suffix.casefold() == ".md" and child.name != "_index.md"
                for child in directory.iterdir()
            ):
                populated.append(relative)
        populated.sort()
        if len(populated) > 1 and role not in selected_roles:
            ambiguous.append(role)
        explicit = selected_roles.get(role)
        roles[role] = {
            "candidates": populated,
            "selected": explicit if isinstance(explicit, str) and explicit else (
                populated[0] if len(populated) == 1 else None
            ),
        }
    return {"roles": roles, "ambiguous_roles": ambiguous}


def resolve_role(project: Project, role: str) -> str:
    """Resolve a folder role from an optional author choice or existing files."""

    if role not in ROLE_CANDIDATES:
        raise ValueError(f"unknown folder role: {role}")
    explicit = load_layout(project).get(role)
    if explicit is not None:
        return explicit

    candidates = inventory_layout(project)["roles"][role]["candidates"]
    if len(candidates) > 1:
        raise LayoutAmbiguity(f"multiple populated folders for {role}: {', '.join(candidates)}")
    if candidates:
        return candidates[0]
    return ROLE_CANDIDATES[role][-1]


def role_directories(project: Project, role: str) -> tuple[str, ...]:
    """Folders to read for a role, retaining evidence when selection is ambiguous."""

    try:
        return (resolve_role(project, role),)
    except LayoutAmbiguity:
        candidates = inventory_layout(project)["roles"][role]["candidates"]
        return tuple(candidates)


def uses_flexible_layout(project: Project) -> bool:
    """Whether existing content or an explicit choice differs from v1 paths."""

    return any(
        any(path != ROLE_CANDIDATES[role][-1] for path in role_directories(project, role))
        for role in ROLE_CANDIDATES
    )


def _safe_directory(root: Path, directory: Path) -> bool:
    current = root
    for part in directory.relative_to(root).parts:
        current /= part
        if current.is_symlink() or not current.is_dir():
            return False
        if current != root and (current / "project.md").is_file():
            return False
    return True
