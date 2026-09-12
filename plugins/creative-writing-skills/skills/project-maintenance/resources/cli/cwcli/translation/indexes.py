"""Translation indexes derived from registered records, never opaque originals."""
from dataclasses import replace
from pathlib import PurePosixPath
from ..project import Project
from ..schema import GENERATED_INDEX_FILES, required_paths
from .catalog import load_catalog, make_plan, render, replacement
from .contract import project_settings, translation_kind


def plan_translation_indexes(project, *, overlay=(), index_ids=None, skip_unparseable=False):
    from ..indexes import plan_reindex
    from ..documents import parse_document
    kind, _, _ = project_settings(project.manifest.metadata)
    overlay = tuple(overlay)
    records = load_catalog(project, skip_unparseable=skip_unparseable)
    for change in overlay:
        if change.after is None:
            records.pop(change.path, None)
        elif translation_kind(change.path) not in (None, 'generated-index'):
            try:
                records[change.path] = parse_document(change.after)
            except ValueError:
                if not skip_unparseable:
                    raise
                records.pop(change.path, None)
    _, required = required_paths(project.manifest.metadata)
    selected = {p for p in required if p.endswith('_index.md') and (kind == 'translation' or p.startswith(('sources/', 'translations/', 'kb/entities/', 'kb/source-comparisons/')))}
    selected.update(f'translations/{d.metadata["direction-id"]}/_index.md' for p, d in records.items() if PurePosixPath(p).name == 'translation.md')
    changes = []
    if kind == 'authoring':
        legacy = Project(project.root, replace(project.manifest, metadata=dict(project.manifest.metadata, **{'schema-version': 1})))
        changes.extend(plan_reindex(legacy, overlay=tuple(c for c in overlay if c.path.startswith(('story/', 'work/', 'kb/'))), skip_unparseable=skip_unparseable).changes)
    if index_ids is not None:
        index_ids = tuple(index_ids)
        if len(set(index_ids)) != len(index_ids):
            raise ValueError("index_ids must contain unique generated index paths")
        known = selected | (set(GENERATED_INDEX_FILES) if kind == 'authoring' else set())
        if not set(index_ids) <= known:
            raise ValueError('unknown translation index path')
        selected &= set(index_ids)
        changes = [c for c in changes if c.path in index_ids]
    for path in sorted(selected):
        parent = str(PurePosixPath(path).parent) + '/'
        change = replacement(project, path, render_translation_index(p for p in records if p.startswith(parent)))
        if change.before != change.after:
            changes.append(change)
    return make_plan(project, ('reindex',), changes, {'derived': True, 'undoable': True})


def render_translation_index(paths=()):
    """Render both initial and refreshed registries in the same stable format."""
    body = '# Index\n\n<!-- generated registry -->\n\n' + ''.join(f'- `{p}`\n' for p in sorted(paths))
    return render({'generated': True}, body)
