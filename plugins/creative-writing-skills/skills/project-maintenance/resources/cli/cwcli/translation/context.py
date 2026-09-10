"""Read-only fixed packets for trusted literary translators."""
import hashlib
import json
from ..documents import parse_document
from .catalog import load_catalog, read_source, find_record
from .contract import SCOPE_FIELDS, strings, slug
from .directions import effective_direction, resolve_unit
from .memory import select_memory


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build_packet(project, direction, units, scope):
    slug(direction)
    if not units or len(set(units)) != len(units):
        raise ValueError('select unique source units')
    if set(scope) - set(SCOPE_FIELDS):
        raise ValueError('unknown context scope field')
    catalog = load_catalog(project)
    selected = [resolve_unit(project, ref) for ref in units]
    volumes = {doc.metadata.get('volume-id', '') for _, doc in selected}
    if len(volumes) != 1:
        raise ValueError('request one volume per context packet')
    volume = next(iter(volumes))
    settings = effective_direction(project, direction, volume)
    if any(ref.split(':')[0] != settings['primary-edition'] for ref in units):
        raise ValueError('selected units must belong to the primary edition')
    context_scope = {field: strings(scope, field) for field in SCOPE_FIELDS}
    derived = {'scope-units': list(units), 'scope-volumes': [volume] if volume else []}
    for field, values in derived.items():
        if field in scope and set(strings(scope, field)) != set(values):
            raise ValueError(f'{field} contradicts selected source units')
        context_scope[field] = values
    dependencies = {}

    def read(path):
        data = read_source(project, path)
        dependencies[path] = digest(data)
        return data

    def text(path):
        doc = parse_document(read(path))
        if 'original-path' in doc.metadata:
            original = read(doc.metadata['original-path'])
            if digest(original) != doc.metadata.get('original-sha256'):
                raise ValueError(f'original bytes changed: {doc.metadata["original-path"]}')
        if 'manuscript-path' in doc.metadata:
            doc = parse_document(read(doc.metadata['manuscript-path']))
        return {'path': path, 'text': doc.body}

    read('project.md')
    read(f'translations/{direction}/translation.md')
    override = f'translations/{direction}/volumes/{volume}/settings.md'
    if volume and override in catalog:
        read(override)
    primary = settings['primary-edition']
    editions = [primary, *settings['auxiliary-editions']]
    for edition in editions:
        path, _ = find_record(project, 'edition-id', edition)
        read(path)
    primary_text = [text(path) for path, _ in selected]
    auxiliary_paths = set()
    alignment_inventory = {}
    for path, doc in catalog.items():
        if path.startswith('kb/source-comparisons/'):
            alignment_inventory[path] = digest(read_source(project, path))
            if doc.metadata.get('status') == 'accepted' and set(strings(doc.metadata, 'source-units')) & set(units):
                read(path)
                for ref in strings(doc.metadata, 'reference-units'):
                    if ref.split(':')[0] in settings['auxiliary-editions']:
                        auxiliary_paths.add(resolve_unit(project, ref)[0])
    references = [text(path) for path in sorted(auxiliary_paths)]
    ordered = sorted((d.metadata['unit-id'], p) for p, d in catalog.items() if p.startswith(f'sources/{primary}/') and 'unit-id' in d.metadata and d.metadata.get('volume-id', '') == volume)
    chosen_paths = {p for p, _ in selected}
    neighbors = set()
    for index, (_, path) in enumerate(ordered):
        if path in chosen_paths:
            for offset in (-1, 1):
                if 0 <= index + offset < len(ordered):
                    neighbors.add(ordered[index + offset][1])
    neighbor_text = [text(path) for path in sorted(neighbors - chosen_paths)]
    rules = [text(path) for path in select_memory(project, direction, context_scope)]
    entities = []
    for entity in context_scope['scope-entities']:
        path, _ = find_record(project, 'entity-id', slug(entity))
        entities.append(text(path))
    inventory = {p: digest(read_source(project, p)) for p in catalog if p.startswith(f'translations/{direction}/memory/')}
    source_inventory = {p: digest(read_source(project, p)) for p in catalog if any(p.startswith(f'sources/{e}/') for e in editions)}
    _, primary_doc = find_record(project, 'edition-id', primary)
    return {'packet-version': 1, 'direction': direction, 'units': list(units), 'scope': context_scope,
            'primary-text': primary_text, 'reference-text': references, 'neighbor-text': neighbor_text,
            'rules': rules, 'entities': entities, 'dependencies': dict(sorted(dependencies.items())),
            'memory-catalog-digest': digest(json.dumps(inventory, sort_keys=True).encode()),
            'source-catalog-digest': digest(json.dumps(source_inventory, sort_keys=True).encode()),
            'alignment-catalog-digest': digest(json.dumps(alignment_inventory, sort_keys=True).encode()),
            'provenance': {'primary-edition': primary, 'auxiliary-editions': settings['auxiliary-editions'],
                           'indirect': primary_doc.metadata['edition-role'] == 'translation', 'language': settings['language'],
                           'inheritance': settings['inheritance']},
            'instructions': 'Primary source controls meaning. Neighbor text is read-only context, not output. Preserve deliberate ambiguity and reveal timing. Hidden material is trusted context only, never publishable prose.'}
