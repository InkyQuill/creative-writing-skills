"""Boundary-aware record discovery; original files are opaque."""
import stat
from ..documents import parse_document
from .contract import project_settings, translation_kind


def read_source(project, relative):
    # The write resolver provides portable-name, link and nested-boundary checks,
    # without performing a write. Internal journal reads use TransactionStore.
    path = project.resolve(relative, for_write=True)
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f'not a regular source: {relative}')
    return path.read_bytes()


def load_catalog(project):
    _, work, enabled = project_settings(project.manifest.metadata)
    if not enabled:
        raise ValueError('enable translation before using translation commands')
    records, identities = {}, set()
    for path in project.iter_managed_markdown():
        relative = project.relative_id(path)
        kind = translation_kind(relative)
        if kind is None or kind == 'generated-index':
            continue
        parts = path.relative_to(project.root).parts
        if parts[0] in ('sources', 'translations'):
            volume_path = len(parts) > 3 and parts[2] == 'volumes'
            if kind in ('source-unit', 'translation-drafts', 'translation-reviews', 'translation-accepted', 'direction-settings') and volume_path != (work == 'series'):
                raise ValueError(f'mixed book/series layout: {relative}')
        doc = parse_document(read_source(project, relative))
        key = {'edition': 'edition-id', 'direction': 'direction-id', 'source-unit': 'unit-id', 'entity': 'entity-id', 'alignment': 'alignment-id', 'translation-memory': 'record-id'}.get(kind)
        if key:
            value = doc.metadata.get(key)
            if not isinstance(value, str) or not value:
                raise ValueError(f'missing {key}: {relative}')
            namespace = parts[1] if kind in ('source-unit', 'translation-memory') else ''
            identity = (kind, namespace, value)
            if identity in identities:
                raise ValueError(f'duplicate {key}: {value}')
            identities.add(identity)
        records[relative] = doc
    return records


def make_plan(project, command, changes, metadata=None):
    """Add recoverable creation of every missing output parent."""
    from ..transactions import TransactionPlan
    directories = set()
    for change in changes:
        parent = project.resolve(change.path, for_write=True).parent
        while parent != project.root and not parent.exists():
            directories.add(project.relative_id(parent))
            parent = parent.parent
    details = dict(metadata or {})
    details['directory-changes'] = {'create': sorted(directories, key=lambda p: (p.count('/'), p)), 'remove': []}
    return TransactionPlan(tuple(command), tuple(changes), details)


def find_record(project, key, value, *, prefix=''):
    matches = [(p, d) for p, d in load_catalog(project).items() if p.startswith(prefix) and d.metadata.get(key) == value]
    if len(matches) != 1:
        raise ValueError(f'expected one {key}={value}, found {len(matches)}')
    return matches[0]


def render(metadata, body):
    from ..documents import Document, render_document
    return render_document(Document(metadata, body, '\n', False))


def replacement(project, path, data):
    from ..transactions import Change
    target = project.resolve(path, for_write=True)
    return Change(path, read_source(project, path) if target.exists() else None, data)
