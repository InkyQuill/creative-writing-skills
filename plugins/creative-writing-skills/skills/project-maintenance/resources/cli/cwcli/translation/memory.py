"""Explicit target-language decisions, scoped exceptions and provenance."""
from itertools import product
from ..documents import parse_document
from .catalog import load_catalog, make_plan, read_source, render, replacement
from .contract import SCOPE_FIELDS, slug, strings, scope_matches, scope_contains, validate_scope_size


def memory_records(project, direction, *, catalog=None):
    slug(direction)
    read_source(project, f'translations/{direction}/translation.md')
    catalog = load_catalog(project, strict=False) if catalog is None else catalog
    return {d.metadata['record-id']: (p, d) for p, d in catalog.items() if p.startswith(f'translations/{direction}/memory/')}


def validate_graph(records):
    for name, (_, doc) in records.items():
        seen = {name}
        current = doc
        while current.metadata.get('supersedes'):
            target = current.metadata['supersedes']
            if target not in records or target in seen:
                raise ValueError('missing or cyclic memory supersession')
            seen.add(target)
            parent = records[target][1]
            if current.metadata.get('subject') != parent.metadata.get('subject') or not scope_contains(parent.metadata, current.metadata):
                raise ValueError('supersession must keep subject and narrow or retain scope')
            current = parent


def plan_memory(project, direction, kind, content):
    doc = parse_document(content)
    if kind == 'entity':
        name = slug(doc.metadata.get('entity-id'))
        strings(doc.metadata, 'evidence')
        load_catalog(project)
        return make_plan(project, ('translation', 'memory'), [replacement(project, f'kb/entities/{name}.md', content)])
    if kind not in ('terms', 'voices', 'decisions', 'style'):
        raise ValueError('invalid memory kind')
    records = memory_records(project, direction)
    name = slug(doc.metadata.get('record-id'))
    if doc.metadata.get('status') not in ('observed', 'proposed', 'accepted', 'superseded'):
        raise ValueError('invalid memory status')
    if not isinstance(doc.metadata.get('subject'), str) or not doc.metadata['subject'].strip() or not doc.body.strip():
        raise ValueError('memory needs subject and rule/observation body')
    for field in (*SCOPE_FIELDS, 'evidence'):
        strings(doc.metadata, field)
    if not strings(doc.metadata, 'evidence'):
        raise ValueError('memory needs evidence or a cited user decision')
    path = f'translations/{direction}/memory/' + ('style.md' if kind == 'style' else f'{kind}/{name}.md')
    if name in records and records[name][0] != path:
        raise ValueError('record identity already exists at another path')
    if any(p == path and identity != name for identity, (p, _) in records.items()):
        raise ValueError('cannot change record identity at an existing memory path')
    updated = dict(records)
    updated[name] = (path, doc)
    validate_graph(updated)
    changes = [replacement(project, path, content)]
    previous = doc.metadata.get('supersedes')
    if previous and doc.metadata['status'] == 'accepted':
        old_path, old = records[previous]
        if scope_contains(doc.metadata, old.metadata):
            changes.append(replacement(project, old_path, render(dict(old.metadata, status='superseded'), old.body)))
    return make_plan(project, ('translation', 'memory'), changes)


def select_memory(project, direction, scope, *, catalog=None):
    validate_scope_size(scope)
    records = memory_records(project, direction, catalog=catalog)
    validate_graph(records)
    # Resolve supersession per point, then union the rules needed by the batch.
    # A narrow exception must not erase the general rule for other units.
    chosen_paths = set()
    dimensions = [strings(scope, field) or [None] for field in SCOPE_FIELDS]
    for point in product(*dimensions):
        context = {field: [value] if value is not None else [] for field, value in zip(SCOPE_FIELDS, point)}
        selected = {k: (p, d) for k, (p, d) in records.items() if d.metadata.get('status') == 'accepted' and scope_matches(d.metadata, context)}
        excluded = set()
        for _, doc in selected.values():
            parent = doc.metadata.get('supersedes')
            while parent:
                excluded.add(parent)
                parent = records[parent][1].metadata.get('supersedes')
        subjects = set()
        for name, (path, doc) in selected.items():
            if name in excluded:
                continue
            subject = doc.metadata['subject']
            if subject in subjects:
                raise ValueError(f'memory conflict for {subject}: {path}')
            subjects.add(subject)
            chosen_paths.add(path)
    return tuple(sorted(chosen_paths))
