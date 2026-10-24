"""Project-local folder choices and read-only discovery of existing content."""

from __future__ import annotations

import json
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
    "brainstorm": ("brainstorm", "work/brainstorm"),
    "reviews": ("reviews", "work/reviews"),
    "archive": ("archive", "work/archive"),
}
LAYOUT_FILE = ".cws-layout.json"


def validate_role_path(project: Project, relative: str) -> str:
    """Accept only a plain, project-relative directory without linked components."""
    _validate_role_path_syntax(relative)
    current = project.root
    for part in PurePosixPath(relative).parts:
        current /= part
        if current.exists() and not current.is_dir():
            raise ValueError(
                f"layout role path component is not a directory: {current.relative_to(project.root).as_posix()}"
            )
    project.resolve(relative + "/.layout-check", for_write=True)
    return relative


def _validate_role_path_syntax(relative: str) -> None:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("layout role path must be a project-relative folder")
    if relative == ".":
        return
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise ValueError("layout role path must be a project-relative folder")


def _validate_role_mapping(roles: dict[str, str]) -> None:
    if not isinstance(roles, dict):
        raise ValueError("layout roles must be an object")
    for role, relative in roles.items():
        if role not in ROLE_CANDIDATES:
            raise ValueError(f"unknown layout role: {role}")
        _validate_role_path_syntax(relative)


def load_layout(project: Project) -> dict[str, str]:
    """Read explicit folder selections from the separate project layout file."""
    from .catalog import read_layout, tagged_directories
    config = read_layout(project)
    if config.version == 1:
        return dict(config.destinations)
    return {role: folders[0] for role in ROLE_CANDIDATES
            if len(folders := tagged_directories(config, role)) == 1}


def render_layout(roles: dict[str, str]) -> bytes:
    _validate_role_mapping(roles)
    return (json.dumps({"version": 1, "roles": roles}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def inventory_layout(project: Project) -> dict[str, object]:
    """Report populated candidate folders without changing or choosing paths."""

    selected_roles = load_layout(project)
    roles: dict[str, dict[str, object]] = {}
    ambiguous: list[str] = []
    for role in ROLE_CANDIDATES:
        populated = _populated_candidates(project, role)
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
    from .catalog import read_layout, resolve_destination
    if project.manifest is None or read_layout(project).version == 2:
        return resolve_destination(project, role)
    explicit = load_layout(project).get(role)
    if explicit is not None:
        return explicit

    candidates = _populated_candidates(project, role)
    if len(candidates) > 1:
        raise LayoutAmbiguity(f"multiple populated folders for {role}: {', '.join(candidates)}")
    if candidates:
        return candidates[0]
    return ROLE_CANDIDATES[role][-1]


def role_directories(project: Project, role: str) -> tuple[str, ...]:
    """Folders to read for a role, retaining evidence when selection is ambiguous."""

    if role not in ROLE_CANDIDATES:
        raise ValueError(f"unknown folder role: {role}")
    from .catalog import read_layout, tagged_directories
    config = read_layout(project)
    if project.manifest is None or config.version == 2:
        return tagged_directories(config, role)
    explicit = load_layout(project).get(role)
    if explicit is not None:
        return (explicit,)
    candidates = _populated_candidates(project, role)
    if candidates:
        return tuple(candidates)
    return (ROLE_CANDIDATES[role][-1],)


def uses_flexible_layout(project: Project) -> bool:
    """Whether the project should avoid assuming the full v1 scaffold."""

    if project.unstructured:
        return True
    if project.metadata.get("scaffold-template") == "compact" or load_layout(project):
        return True
    return any(
        any(path != ROLE_CANDIDATES[role][-1] for path in role_directories(project, role))
        for role in ROLE_CANDIDATES
    )


def _populated_candidates(project: Project, role: str) -> list[str]:
    populated: list[str] = []
    for relative in ROLE_CANDIDATES[role]:
        directory = project.root / relative
        if not _safe_directory(project.root, directory):
            continue
        if any(
            child.is_file() and not child.is_symlink()
            and child.suffix.casefold() == ".md" and child.name != "_index.md"
            for child in directory.iterdir()
        ):
            populated.append(relative)
    return sorted(populated)


def _safe_directory(root: Path, directory: Path) -> bool:
    current = root
    for part in directory.relative_to(root).parts:
        current /= part
        if current.is_symlink() or not current.is_dir():
            return False
        if current != root and (current / "project.md").is_file():
            return False
    return True
