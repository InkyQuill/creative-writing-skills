"""Translation indexes derived from registered records, never opaque originals."""
from dataclasses import replace
from pathlib import PurePosixPath
from ..project import Project
from ..schema import required_paths
from .catalog import load_catalog, make_plan, render, replacement
from .contract import project_settings


def plan_translation_indexes(project, *, overlay=(), index_ids=None, skip_unparseable=False):
    from ..indexes import plan_reindex
    from ..documents import parse_document
    kind, _, _ = project_settings(project.manifest.metadata)
    records = load_catalog(project)
    for change in overlay:
        if change.after is None:
            records.pop(change.path, None)
        elif 'originals' not in PurePosixPath(change.path).parts:
            records[change.path] = parse_document(change.after)
    _, required = required_paths(project.manifest.metadata)
    selected = {p for p in required if p.endswith('_index.md') and (kind == 'translation' or p.startswith(('sources/', 'translations/', 'kb/entities/', 'kb/source-comparisons/')))}
    selected.update(f'translations/{d.metadata["direction-id"]}/_index.md' for p, d in records.items() if PurePosixPath(p).name == 'translation.md')
    changes = []
    if kind == 'authoring':
        legacy = Project(project.root, replace(project.manifest, metadata=dict(project.manifest.metadata, **{'schema-version': 1})))
        changes.extend(plan_reindex(legacy, overlay=tuple(c for c in overlay if c.path.startswith(('story/', 'work/', 'kb/'))), skip_unparseable=skip_unparseable).changes)
    if index_ids is not None:
        if not set(index_ids) <= selected | {c.path for c in changes}:
            raise ValueError('unknown translation index path')
        selected &= set(index_ids)
        changes = [c for c in changes if c.path in index_ids]
    for path in sorted(selected):
        parent = str(PurePosixPath(path).parent) + '/'
        body = '# Index\n\n<!-- generated registry -->\n\n' + ''.join(f'- `{p}`\n' for p in sorted(records) if p.startswith(parent))
        change = replacement(project, path, render({'generated': True}, body))
        if change.before != change.after:
            changes.append(change)
    return make_plan(project, ('reindex',), changes, {'derived': True, 'undoable': True})
