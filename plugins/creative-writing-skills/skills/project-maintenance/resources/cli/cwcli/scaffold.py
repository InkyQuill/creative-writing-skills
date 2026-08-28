"""Deterministic rendering and transactional bootstrap of story projects."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from .documents import Document, parse_document, render_document
from .indexes import render_index
from .project import MANAGED_ROOTS, Project
from .schema import GENERATED_INDEX_FILES, SCHEMA_VERSION, SCAFFOLD_DIRECTORIES, SCAFFOLD_FILES
from .transactions import Change, TransactionEngine, TransactionPlan, TransactionRecord, _fsync_directory

_STARTER_DOCUMENTS = {
    "kb/vocab.md": (
        "Vocabulary",
        "# Vocabulary\n\nRecord canonical names, spellings, aliases, and terminology here.\n",
    ),
    "kb/continuity/timeline.md": (
        "Timeline",
        "# Timeline\n\nRecord established events in story order.\n",
    ),
    "kb/continuity/state.md": (
        "State",
        "# State\n\nRecord the current durable state of characters, places, and unresolved changes.\n",
    ),
    "kb/continuity/promises.md": (
        "Promises",
        "# Promises\n\nRecord setups, reader expectations, and planned payoffs.\n",
    ),
    "kb/continuity/questions.md": (
        "Questions",
        "# Questions\n\nRecord open continuity questions that need an author decision.\n",
    ),
}


def render_scaffold(title: str, language: str) -> dict[str, bytes]:
    """Render every authored file in a new project in stable path order."""

    rendered: dict[str, bytes] = {}
    for relative_id in SCAFFOLD_FILES:
        if relative_id == "project.md":
            rendered[relative_id] = _render_manifest(title, language)
        elif relative_id in GENERATED_INDEX_FILES:
            rendered[relative_id] = render_index(relative_id)
        else:
            document_title, body = _STARTER_DOCUMENTS[relative_id]
            rendered[relative_id] = _render_document({"title": document_title}, body)
    return rendered


class InitError(RuntimeError):
    """Raised when initialization would overwrite or reinterpret managed content."""


def plan_init(target: Path, title: str, language: str) -> TransactionPlan:
    """Plan missing scaffold files for an absent or existing ordinary folder."""

    root = Path(target).absolute()
    _validate_init_target(root)
    rendered = render_scaffold(title, language)
    created_directories = tuple(
        relative for relative in SCAFFOLD_DIRECTORIES if not (root / relative).is_dir()
    )
    changes: list[Change] = []
    for relative_id, after in rendered.items():
        path = root / relative_id
        before = path.read_bytes() if path.is_file() and not path.is_symlink() else None
        if before is None:
            changes.append(Change(relative_id, None, after))
    return TransactionPlan(
        command=("init",),
        changes=tuple(changes),
        metadata={
            "bootstrap": True,
            "created-directories": created_directories,
            "protected-directories": (
                ".creative-writing/context",
                ".creative-writing/transactions",
            ),
            "undoable": False,
        },
    )


def apply_init(target: Path, title: str, language: str) -> TransactionRecord:
    """Apply bootstrap atomically for an absent target or transactionally in-place."""

    root = Path(target).absolute()
    if root.exists() or root.is_symlink():
        plan = plan_init(root, title, language)
        _create_scaffold_directories(root)
        return TransactionEngine(_bootstrap_project(root, title, language)).apply(plan)
    return _apply_absent_init(root, title, language)


def preview_init(target: Path, title: str, language: str) -> TransactionPlan:
    """Return the bootstrap plan without creating the target or any parent."""

    return plan_init(Path(target).absolute(), title, language)


def _validate_init_target(root: Path) -> None:
    if _has_symlink_component(root):
        raise InitError("initialization target path must not contain a symlink")
    if root.exists() and not root.is_dir():
        raise InitError("initialization target must be an ordinary directory, not a link or file")
    if not root.exists():
        if not root.parent.is_dir() or root.parent.is_symlink():
            raise InitError("initialization target parent must be an existing ordinary directory")
        return

    manifest = root / "project.md"
    if manifest.exists() or manifest.is_symlink():
        if manifest.is_symlink() or not manifest.is_file():
            raise InitError(_migration_message("project.md has an incompatible filesystem kind"))
        try:
            schema_version = parse_document(manifest.read_bytes()).metadata.get("schema-version")
        except (OSError, UnicodeError, ValueError) as error:
            raise InitError(_migration_message(f"project.md is incompatible: {error}")) from error
        if schema_version != SCHEMA_VERSION or isinstance(schema_version, bool):
            raise InitError(_migration_message("project.md uses an incompatible schema"))

    for name in MANAGED_ROOTS:
        managed = root / name
        if managed.is_symlink() or (managed.exists() and not managed.is_dir()):
            raise InitError(_migration_message(f"managed root {name} has an incompatible kind"))
        if managed.is_dir():
            populated = _populated_managed_entry(root, managed)
            if populated is not None:
                raise InitError(_migration_message(f"managed root {name} is populated at {populated}"))

    for relative in SCAFFOLD_DIRECTORIES:
        candidate = root / relative
        if candidate.is_symlink() or (candidate.exists() and not candidate.is_dir()):
            raise InitError(_migration_message(f"scaffold path {relative} has an incompatible kind"))


def _has_symlink_component(path: Path) -> bool:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            return True
    return False


def _populated_managed_entry(root: Path, managed: Path) -> str | None:
    canonical_directories = {
        (root / relative).absolute() for relative in SCAFFOLD_DIRECTORIES
    }
    pending = [managed]
    while pending:
        directory = pending.pop()
        for entry in directory.iterdir():
            if entry.is_symlink() or not entry.is_dir():
                return entry.relative_to(root).as_posix()
            if entry.absolute() not in canonical_directories:
                return entry.relative_to(root).as_posix()
            pending.append(entry)
    return None


def _migration_message(reason: str) -> str:
    return f"{reason}; use cw migrate --plan instead of init to preserve managed content"


def _bootstrap_project(root: Path, title: str, language: str) -> Project:
    manifest_path = root / "project.md"
    manifest_bytes = (
        manifest_path.read_bytes()
        if manifest_path.is_file() and not manifest_path.is_symlink()
        else render_scaffold(title, language)["project.md"]
    )
    return Project(root=root.resolve(), manifest=parse_document(manifest_bytes))


def _create_scaffold_directories(root: Path) -> None:
    for relative in SCAFFOLD_DIRECTORIES:
        directory = root / relative
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise InitError(f"cannot create scaffold directory {relative}: incompatible path")
        directory.mkdir(exist_ok=True)
        _fsync_directory(directory.parent)


def _apply_absent_init(root: Path, title: str, language: str) -> TransactionRecord:
    temporary = Path(tempfile.mkdtemp(prefix=f".{root.name}.cw-init-", dir=root.parent))
    installed = False
    try:
        plan = plan_init(temporary, title, language)
        _create_scaffold_directories(temporary)
        record = TransactionEngine(_bootstrap_project(temporary, title, language)).apply(plan)
        _fsync_tree(temporary)
        if root.exists() or root.is_symlink():
            raise InitError("initialization target appeared while bootstrap was being prepared")
        os.rename(temporary, root)
        installed = True
        _fsync_directory(root.parent)
        return record
    finally:
        if not installed and temporary.exists():
            shutil.rmtree(temporary)
            _fsync_directory(temporary.parent)


def _fsync_tree(root: Path) -> None:
    for directory, child_directories, _files in os.walk(root, topdown=False):
        for name in child_directories:
            _fsync_directory(Path(directory) / name)
        _fsync_directory(Path(directory))


def _render_manifest(title: str, language: str) -> bytes:
    body = (
        f"# {title}\n\n"
        "## Project instructions\n\n"
        "Keep manuscript prose in `story/chapters/`. Keep plans, drafts, reviews, and brainstorming "
        "in `work/`. Record durable story knowledge in `kb/`, and keep project-specific conventions "
        "and decisions in this manifest.\n"
    )
    return _render_document(
        {
            "schema-version": SCHEMA_VERSION,
            "title": title,
            "language": language,
            "status": "planning",
        },
        body,
    )


def _render_document(metadata: dict[str, str | int | bool], body: str) -> bytes:
    return render_document(Document(metadata=metadata, body=body, newline="\n", bom=False))


__all__ = ["InitError", "apply_init", "plan_init", "preview_init", "render_scaffold"]
