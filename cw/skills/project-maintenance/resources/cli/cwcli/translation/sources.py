"""Import opaque editions and preserve working-unit revisions in the journal."""
import hashlib
from pathlib import Path
from ..documents import parse_document
from ..transactions import Change
from .catalog import find_record, load_catalog, make_plan, read_source, render, replacement
from .contract import project_settings, slug, strings


def external_bytes(value):
    path = Path(value).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError(f'import must be a regular file without links: {path}')
    return path.read_bytes()


def plan_source(project, request):
    if not isinstance(request, dict):
        raise ValueError('source request must be a JSON object')
    _, work, enabled = project_settings(project.manifest.metadata)
    if not enabled:
        raise ValueError('enable translation first')
    action = request.get('action')
    if action == 'edition':
        doc = parse_document(request['content'].encode('utf-8'))
        edition = slug(doc.metadata.get('edition-id'))
        for key in ('language', 'revision-label'):
            if not isinstance(doc.metadata.get(key), str) or not doc.metadata[key].strip():
                raise ValueError(f'edition requires {key}')
        if doc.metadata.get('edition-role') not in ('original', 'translation'):
            raise ValueError('edition-role must be original or translation')
        for volume in strings(doc.metadata, 'coverage'):
            slug(volume)
        path = f'sources/{edition}/edition.md'
        if (project.root / path).exists():
            raise ValueError('edition already registered; use a new identity for a new edition')
        return make_plan(project, ('translation', 'source'), [replacement(project, path, render(doc.metadata, doc.body))])
    if action not in ('unit', 'manuscript-unit', 'refresh-unit'):
        raise ValueError('unknown source action')
    edition, unit = slug(request.get('edition')), slug(request.get('unit'))
    edition_path, edition_doc = find_record(project, 'edition-id', edition)
    guards = {edition_path: hashlib.sha256(read_source(project, edition_path)).hexdigest()}
    if action == 'refresh-unit':
        path, doc = find_record(project, 'unit-id', unit, prefix=f'sources/{edition}/')
        if 'manuscript-path' in doc.metadata:
            raise ValueError('edit the referenced manuscript instead of refreshing a copy')
        text = external_bytes(request['text-file']).decode('utf-8-sig')
        return make_plan(project, ('translation', 'source'), [replacement(project, path, render(doc.metadata, text))], {'read-guards': guards})
    volume = request.get('volume', '')
    if work == 'series':
        slug(volume)
        if volume not in strings(edition_doc.metadata, 'coverage'):
            raise ValueError(f'edition does not cover volume {volume}')
    elif volume:
        raise ValueError('book units do not have volume IDs')
    base = f'sources/{edition}' + (f'/volumes/{volume}' if volume else '')
    if any(d.metadata.get('unit-id') == unit for p, d in load_catalog(project).items() if p.startswith(f'sources/{edition}/')):
        raise ValueError(f'duplicate unit identity: {unit}')
    orders = [d.metadata.get('order', 0) for p, d in load_catalog(project).items() if p.startswith(base + '/text/')]
    order = request.get('order', max(orders, default=0) + 1)
    if type(order) is not int or order < 1 or order in orders:
        raise ValueError('unit order must be a unique positive integer within its volume')
    metadata = {'unit-id': unit, 'order': order}
    if volume:
        metadata['volume-id'] = volume
    changes = []
    if action == 'manuscript-unit':
        relative = request['manuscript-path']
        if not relative.startswith(('story/chapters/', 'story/side-stories/')):
            raise ValueError('manuscript source must be accepted story prose')
        data = read_source(project, relative)
        guards[relative] = hashlib.sha256(data).hexdigest()
        metadata['manuscript-path'] = relative
        text = 'Source refers to the author manuscript; no prose is copied.\n'
    else:
        original = external_bytes(request['original-file'])
        extension = Path(request['original-file']).suffix
        original_path = f'{base}/originals/{unit}{extension}'
        if (project.root / original_path).exists():
            raise ValueError('cannot overwrite an original')
        changes.append(Change(original_path, None, original))
        metadata.update({'original-path': original_path, 'original-sha256': hashlib.sha256(original).hexdigest()})
        text = external_bytes(request['text-file']).decode('utf-8-sig')
    changes.append(replacement(project, f'{base}/text/{unit}.md', render(metadata, text)))
    return make_plan(project, ('translation', 'source'), changes, {'read-guards': guards})
