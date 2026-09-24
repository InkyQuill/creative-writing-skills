"""Read-only inventory of author-owned Markdown folder candidates."""

from __future__ import annotations

from pathlib import Path

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


def inventory_layout(project: Project) -> dict[str, object]:
    """Report populated candidate folders without changing or choosing paths."""

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
        if len(populated) > 1:
            ambiguous.append(role)
        explicit = project.manifest.metadata.get(f"role-{role}")
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
    explicit = project.manifest.metadata.get(f"role-{role}")
    if explicit is not None:
        if not isinstance(explicit, str) or not explicit or explicit in {".", ".."}:
            raise ValueError(f"role-{role} must name a project-relative folder")
        project.resolve(explicit + "/.layout-check", for_write=True)
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
