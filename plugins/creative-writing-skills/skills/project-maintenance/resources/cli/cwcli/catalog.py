"""Optional purpose tags and a shared view of author-owned documents."""
from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Literal, Mapping

from .project import Project


@dataclass(frozen=True)
class TagBinding:
    path: str
    kind: Literal['file', 'directory']
    tags: frozenset[str]
    remove: frozenset[str] = frozenset()


@dataclass(frozen=True)
class LayoutConfig:
    version: int = 1
    bindings: tuple[TagBinding, ...] = ()
    destinations: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))


def validate_binding_path(project: Project, path: str, kind: str) -> str:
    from .layout import validate_role_path
    if kind == 'directory':
        return validate_role_path(project, path)
    if kind != 'file' or not isinstance(path, str) or not path or path == '.':
        raise ValueError('binding needs a file or directory path')
    if any(part in {'', '.', '..'} for part in path.split('/')):
        raise ValueError('binding path must be project-relative')
    target = project.resolve(path, for_write=True)
    if target.exists() and not target.is_file():
        raise ValueError('file binding points to a directory')
    return target.relative_to(project.root).as_posix()


def _tags(value: object) -> frozenset[str]:
    if not isinstance(value, list) or any(not isinstance(tag, str) or not tag.strip() or tag != tag.strip() for tag in value):
        raise ValueError('tags must be a list of nonempty names')
    return frozenset(value)


def read_layout(project: Project) -> LayoutConfig:
    from .layout import LAYOUT_FILE, _validate_role_mapping
    path = project.root / LAYOUT_FILE
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    except FileNotFoundError:
        return LayoutConfig()
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('layout file must be regular')
        with os.fdopen(fd, 'r', encoding='utf-8') as stream:
            fd = -1
            data = json.load(stream)
    finally:
        if fd >= 0:
            os.close(fd)
    if not isinstance(data, dict):
        raise ValueError('invalid .cws-layout.json')
    if type(data.get('version')) is int and data['version'] == 1:
        roles = data.get('roles')
        _validate_role_mapping(roles)
        bindings = tuple(TagBinding(validate_binding_path(project, path, 'directory'), 'directory', frozenset({role})) for role, path in roles.items())
        return LayoutConfig(1, bindings, MappingProxyType(dict(roles)))
    if type(data.get('version')) is not int or data['version'] != 2 or not isinstance(data.get('bindings'), list):
        raise ValueError('invalid .cws-layout.json: expected version 1 roles or version 2 bindings')
    bindings = []
    seen = set()
    for raw in data['bindings']:
        if not isinstance(raw, dict) or set(raw) - {'path', 'kind', 'tags', 'remove'}:
            raise ValueError('invalid tag binding')
        kind = raw.get('kind')
        path = validate_binding_path(project, raw.get('path'), kind)
        tags, remove = _tags(raw.get('tags', [])), _tags(raw.get('remove', []))
        if tags & remove or (kind, path) in seen:
            raise ValueError('duplicate binding or overlapping add/remove tags')
        seen.add((kind, path))
        bindings.append(TagBinding(path, kind, tags, remove))
    destinations = data.get('destinations', {})
    if not isinstance(destinations, dict):
        raise ValueError('destinations must be an object')
    for tag, path in destinations.items():
        _tags([tag])
        validate_binding_path(project, path, 'directory')
    return LayoutConfig(2, tuple(bindings), MappingProxyType(dict(destinations)))


def effective_tags(config: LayoutConfig, relative: str) -> frozenset[str]:
    target = PurePosixPath(relative)
    tags: set[str] = set()
    for binding in sorted(config.bindings, key=lambda b: (b.kind == 'file', len(PurePosixPath(b.path).parts), b.path)):
        path = PurePosixPath(binding.path)
        applies = path == target if binding.kind == 'file' else path == target or path in target.parents
        if applies:
            tags.difference_update(binding.remove)
            tags.update(binding.tags)
    return frozenset(tags)


def render_config(config: LayoutConfig) -> bytes:
    data = {'version': 2, 'bindings': [
        {'path': b.path, 'kind': b.kind, 'tags': sorted(b.tags), 'remove': sorted(b.remove)}
        for b in config.bindings
    ], 'destinations': dict(config.destinations)}
    return (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def tagged_directories(config: LayoutConfig, tag: str) -> tuple[str, ...]:
    return tuple(sorted({b.path for b in config.bindings if b.kind == 'directory'
                         and tag in effective_tags(config, str(PurePosixPath(b.path) / '.tag-probe'))}))


def resolve_destination(project: Project, tag: str, explicit: str | None = None) -> str:
    from .layout import LayoutAmbiguity
    config = read_layout(project)
    selected = explicit if explicit is not None else config.destinations.get(tag)
    if selected is not None:
        return validate_binding_path(project, selected, 'directory')
    folders = tagged_directories(config, tag)
    if len(folders) == 1:
        return folders[0]
    raise LayoutAmbiguity(f'No unique destination for {tag}; provide an explicit output path or layout destination')


def iter_documents(project: Project, *, target: str | None = None):
    """Inventory scoped Markdown; never follow links, service dirs or other projects."""
    def walk(directory: Path):
        for path in sorted(directory.iterdir(), key=lambda p: (p.name.casefold(), p.name)):
            if path.is_symlink() or path.name.startswith('.') or path.name in {'node_modules', '__pycache__'}:
                continue
            if path.is_dir():
                if any((path / name).is_file() for name in ('project.md', '.cws-layout.json')):
                    continue
                yield from walk(path)
            elif path.is_file() and path.suffix.casefold() == '.md':
                yield path
    if target is not None:
        path = project.resolve(target, for_write=True)
        if path.is_file():
            if path.suffix.casefold() == '.md':
                yield path
        elif path.is_dir():
            yield from walk(path)
        else:
            raise ValueError(f'check target does not exist: {target}')
    else:
        yield from walk(project.root)


KNOWLEDGE_TAGS = frozenset({'kb', 'characters', 'world', 'canon', 'styles', 'samples', 'issues', 'continuity', 'vocabulary'})
_ROLE_KINDS = {'chapters': 'chapter', 'side-stories': 'side-story',
               'drafts': 'work-artifact', 'plans': 'work-artifact',
               'reviews': 'work-artifact', 'brainstorm': 'work-artifact', 'archive': 'work-artifact',
               **{tag: 'kb-content' for tag in KNOWLEDGE_TAGS}, 'vocabulary': 'vocabulary',
               'continuity': 'continuity-record'}


@dataclass(frozen=True)
class DocumentClassification:
    tags: frozenset[str]
    origin: Literal['explicit', 'legacy', 'unknown']
    managed_kind: str | None
    conflicts: tuple[str, ...] = ()


def classify_document(project: Project, relative: str) -> DocumentClassification:
    from .schema import allowed_document_kind
    from .layout import ROLE_CANDIDATES, role_directories
    config = read_layout(project)
    tags = effective_tags(config, relative)
    if config.version == 2:
        # Purpose tags are not mutually exclusive; only operations requiring a
        # single document kind need to reject incompatible purposes.
        kinds = {_ROLE_KINDS[tag] for tag in tags if tag in _ROLE_KINDS and tag != 'archive'}
        if 'vocabulary' in kinds or 'continuity-record' in kinds:
            kinds.discard('kb-content')
        conflicts = tuple(sorted(kinds)) if len(kinds) > 1 else ()
        return DocumentClassification(tags, 'explicit' if tags else 'unknown',
                                      next(iter(kinds)) if len(kinds) == 1 else None, conflicts)
    if project.manifest is not None or config.bindings:
        for role in ROLE_CANDIDATES:
            if PurePosixPath(relative).parent.as_posix() in role_directories(project, role):
                tags |= {role}
        kind = allowed_document_kind(relative, schema_version=project.metadata.get('schema-version', 1))
        if PurePosixPath(relative).name == '_index.md' and tags:
            kind = 'generated-index'
        if kind is None:
            kinds = {_ROLE_KINDS[tag] for tag in tags if tag in _ROLE_KINDS}
            kind = next(iter(kinds)) if len(kinds) == 1 else None
        if kind in {'kb-content', 'continuity-record', 'continuity-scene', 'vocabulary'}:
            tags |= {'kb'}
        return DocumentClassification(frozenset(tags), 'legacy', kind)
    return DocumentClassification(frozenset(), 'unknown', None)


def document_paths(project: Project) -> tuple[Path, ...]:
    paths = list(project.iter_managed_markdown())
    if project.manifest is not None and project.selection is None:
        paths.insert(0, project.root / 'project.md')
    return tuple(dict.fromkeys(paths))


def has_tag(project: Project, relative: str, tag: str) -> bool:
    return tag in classify_document(project, relative).tags


def lifecycle_drafts(project: Project) -> tuple[Path, ...]:
    from .documents import read_document
    found = []
    for path in project.iter_managed_markdown():
        read = read_document(path.read_bytes())
        if read.document is not None and {'target', 'base-revision'} & read.document.metadata.keys():
            found.append(path)
    return tuple(found)
