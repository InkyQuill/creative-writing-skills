"""Previewable role-folder relocation using the ordinary transaction journal."""
from __future__ import annotations

import hashlib
import posixpath
import re
import tempfile
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from .indexes import plan_reindex
from .layout import ROLE_CANDIDATES, LAYOUT_FILE, load_layout, render_layout, resolve_role, validate_role_path
from .project import Project, discover_project
from .transactions import Change, TransactionPlan


def plan_relocation(project: Project, selections: dict[str, str]) -> TransactionPlan:
    """Build guarded file, reference and directory changes for selected roles."""
    if not selections:
        raise ValueError("--relocate requires --set ROLE=FOLDER")
    if project.manifest.metadata.get("schema-version") != 1:
        raise ValueError("relocation currently supports schema-version 1 authoring projects")
    roles = load_layout(project)
    moves = {}
    for role, destination in selections.items():
        source = resolve_role(project, role)
        validate_role_path(project, destination)
        if source == destination:
            continue
        if not project.resolve(source, for_write=True).is_dir():
            raise ValueError(f"role source folder is missing: {source}")
        if source in moves:
            raise ValueError("multiple roles share one relocation source")
        moves[source] = destination
        roles[role] = destination
    render_layout(roles)
    effective = {role: roles.get(role, resolve_role(project, role)) for role in ROLE_CANDIDATES}
    for role, folder in effective.items():
        for other, other_folder in effective.items():
            if role != other and (folder == other_folder or folder.startswith(other_folder + "/")):
                raise ValueError("layout role folders must not overlap")
    if not moves:
        return TransactionPlan(command=("layout", "--relocate"), changes=(), metadata={"undoable": True})
    # Reject overlapping trees, including swaps and nested destinations. This
    # keeps path mapping unambiguous and prevents merging author content.
    trees = [*moves, *moves.values()]
    for i, first in enumerate(trees):
        for second in trees[i + 1:]:
            if first == second or first.startswith(second + "/") or second.startswith(first + "/"):
                raise ValueError("relocation folders must not overlap")
    for destination in moves.values():
        if project.resolve(destination, for_write=True).exists():
            raise ValueError(f"relocation destination already exists: {destination}")

    files: dict[str, bytes] = {}
    directories = set()
    # Include project-level references and binder JSON, but never enter journals,
    # VCS metadata, links, or nested projects. Reject unsafe entries in moved trees.
    def scan(directory: Path):
        """Inventory regular content without entering protected or nested trees."""
        relative = directory.relative_to(project.root).as_posix()
        moving = any(relative == source or relative.startswith(source + "/") for source in moves)
        for entry in sorted(directory.iterdir()):
            identity = entry.relative_to(project.root).as_posix()
            if directory == project.root and entry.name in {".creative-writing", ".git", ".remember"}:
                continue
            if entry.is_symlink():
                if moving or identity in moves:
                    raise ValueError(f"cannot relocate symlink: {identity}")
                continue
            if entry.is_dir():
                if (entry / "project.md").exists():
                    if moving or identity in moves:
                        raise ValueError(f"cannot relocate nested project: {identity}")
                    continue
                directories.add(identity)
                scan(entry)
            elif entry.is_file():
                project.resolve(identity, for_write=True)
                files[identity] = entry.read_bytes()
            elif moving:
                raise ValueError(f"cannot relocate special file: {identity}")
    scan(project.root)

    def mapped(path: str) -> str:
        """Map one project-relative identity through the disjoint role moves."""
        for source, destination in moves.items():
            if path == source or path.startswith(source + "/"):
                return destination + path[len(source):]
        return path

    final = {}
    for path, data in files.items():
        target = mapped(path)
        project.resolve(target, for_write=True)
        if path.endswith(".md"):
            data = _rewrite_markdown(data, path, target, mapped, moves)
        elif path.endswith(".json") and not path.endswith(".review.json") and "binder" in Path(path).name.lower():
            data = _rewrite_paths(data, moves)
        final[target] = data
    if moves:
        final[LAYOUT_FILE] = render_layout(roles)
    # Render indexes against the proposed layout in an isolated snapshot, without
    # scaffolding a legacy tree or writing anything to the author's project.
    with tempfile.TemporaryDirectory(prefix="cw-relocation-") as temporary:
        root = Path(temporary)
        for path, data in final.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        snapshot = discover_project(root)
        for change in plan_reindex(snapshot).changes:
            final[change.path] = change.after
    changes = tuple(Change(path, files.get(path), final.get(path))
                    for path in sorted(files.keys() | final.keys())
                    if files.get(path) != final.get(path))
    removed = {directory for directory in directories if mapped(directory) != directory}
    created = set()
    for directory in directories:
        target = mapped(directory)
        if target != directory:
            created.add(target)
    for path in final:
        parent = Path(path).parent
        while parent != Path("."):
            relative = parent.as_posix()
            if not (project.root / parent).exists():
                created.add(relative)
            parent = parent.parent
    return TransactionPlan(command=("layout", "--relocate"), changes=changes,
        metadata={"undoable": True, "relocations": moves,
                  "file-map": [{"source": path, "destination": mapped(path),
                                "sha256": hashlib.sha256(data).hexdigest()}
                               for path, data in sorted(files.items()) if mapped(path) != path],
                  "directory-changes": {"create": sorted(created), "remove": sorted(removed)},
                  "read-guards": {path: hashlib.sha256(data).hexdigest()
                                  for path, data in files.items()
                                  if path.endswith(".md") and final.get(path) == data}})


def _rewrite_paths(data: bytes, moves: dict[str, str]) -> bytes:
    """Rewrite explicit path prefixes without treating bare folder words as paths."""
    # Work on UTF-8 path tokens only; retain formatting, BOM and line endings.
    text = data.decode("utf-8")
    for source, destination in sorted(moves.items(), key=lambda item: -len(item[0])):
        # A bare single-segment folder name is also an ordinary prose word.
        # Folder-only Markdown links are handled by the link resolver below;
        # generic path tokens must carry a slash when their source is one word.
        ending = r"(?=/|[\s`\"'<>)]|$)" if "/" in source else r"(?=/)"
        text = re.sub(r"(?<![\w./-])" + re.escape(source) + ending,
                      lambda match: destination, text)
    return text.encode("utf-8")


def _rewrite_markdown(data: bytes, old: str, new: str, mapped, moves) -> bytes:
    """Rebase local Markdown links and explicit project path tokens."""
    text = data.decode("utf-8")
    def link(match):
        """Preserve remote links and rewrite local paths relative to the new file."""
        value = match.group("url")
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or value.startswith(("/", "#")):
            return match.group(0)
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(old), unquote(parsed.path)))
        if resolved == ".." or resolved.startswith("../"):
            return match.group(0)
        destination = mapped(resolved)
        if destination == resolved and old == new:
            return match.group(0)
        relative = posixpath.relpath(destination, posixpath.dirname(new) or ".")
        encoded = quote(relative, safe="/._-~") if "%" in value else relative
        suffix = ("?" + parsed.query if parsed.query else "") + ("#" + parsed.fragment if parsed.fragment else "")
        start, end = match.span("url")
        return match.group(0)[:start-match.start()] + encoded + suffix + match.group(0)[end-match.start():]
    # Inline links/images and reference definitions; leave titles and fragments.
    text = re.sub(r"\]\(<?(?P<url>[^\s)>]+)>?(?:[^\n)]*)\)|(?m:^\s*\[[^\]]+\]:\s*<?(?P<ref>[^\s>]+)>?)",
                  lambda match: link(match) if match.group("url") else _reference_link(match, old, new, mapped), text)
    return _rewrite_paths(text.encode("utf-8"), moves)


def _reference_link(match, old, new, mapped):
    """Rebase a Markdown reference definition while retaining its suffix."""
    value = match.group("ref")
    if urlsplit(value).scheme or value.startswith(("/", "#")):
        return match.group(0)
    parsed = urlsplit(value)
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(old), unquote(parsed.path)))
    if resolved.startswith("../") or resolved == "..":
        return match.group(0)
    destination = mapped(resolved)
    if destination == resolved and old == new:
        return match.group(0)
    relative = posixpath.relpath(destination, posixpath.dirname(new) or ".")
    if "%" in value:
        relative = quote(relative, safe="/._-~")
    relative += ("?" + parsed.query if parsed.query else "") + ("#" + parsed.fragment if parsed.fragment else "")
    start, end = match.span("ref")
    return match.group(0)[:start-match.start()] + relative + match.group(0)[end-match.start():]
