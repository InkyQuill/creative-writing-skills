"""Read-only inventory of author-owned Markdown folder candidates."""

from __future__ import annotations

from pathlib import Path

from .project import Project


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
        roles[role] = {
            "candidates": populated,
            "selected": populated[0] if len(populated) == 1 else None,
        }
    return {"roles": roles, "ambiguous_roles": ambiguous}


def _safe_directory(root: Path, directory: Path) -> bool:
    current = root
    for part in directory.relative_to(root).parts:
        current /= part
        if current.is_symlink() or not current.is_dir():
            return False
        if current != root and (current / "project.md").is_file():
            return False
    return True
