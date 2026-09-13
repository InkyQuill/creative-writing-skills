"""Read-only fixed packets for trusted literary translators."""
import hashlib
import json
from ..documents import parse_document
from .catalog import load_catalog, read_source, find_record, filter_catalog
from .contract import SCOPE_FIELDS, strings, slug, validate_scope_size
from .directions import effective_direction, resolve_unit
from .memory import select_memory
from .external_memory import validate_memory_input


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rebuild_packet(project, captured, *, catalog=None, cache=None):
    """Rebuild a supported packet from only its validated operation inputs."""
    if not isinstance(captured, dict) or type(captured.get('packet-version')) is not int:
        raise ValueError('missing or invalid translation packet version')
    version = captured['packet-version']
    if version not in (1, 2):
        raise ValueError('unsupported translation packet version')
    if (version == 1 and 'memory-input' in captured) or (version == 2 and not isinstance(captured.get('memory-input'), dict)):
        raise ValueError('memory-input does not match translation packet version')
    return build_packet(project, captured['direction'], tuple(captured['units']), captured['scope'],
                        memory_input=captured.get('memory-input'), catalog=catalog, cache=cache)


def build_packet(project, direction, units, scope, *, catalog=None, cache=None, memory_input=None):
    slug(direction)
    if not isinstance(scope, dict):
        raise ValueError('scope must be a JSON object')
    if not units or len(set(units)) != len(units):
        raise ValueError('select unique source units')
    if set(scope) - set(SCOPE_FIELDS):
        raise ValueError('unknown context scope field')
    validate_scope_size(dict(scope, **{'scope-units': list(units), 'scope-volumes': []}))
    if memory_input is not None:
        memory_input = validate_memory_input(project, direction, scope, memory_input)
    excluded_memory = () if memory_input is None else memory_input['excluded-file-memory']
    if catalog is not None:
        catalog = filter_catalog(catalog, excluded_memory)
    lookup_catalog = load_catalog(project, strict=False, excluded_memory=excluded_memory) if catalog is None else catalog
    selected = [resolve_unit(project, ref, catalog=lookup_catalog) for ref in units]
    volumes = {doc.metadata.get('volume-id', '') for _, doc in selected}
    if len(volumes) != 1:
        raise ValueError('request one volume per context packet')
    volume = next(iter(volumes))
    catalog = load_catalog(project, strict=False, volume=volume, excluded_memory=excluded_memory) if catalog is None else catalog
    cache = {} if cache is None else cache
    settings = effective_direction(project, direction, volume, catalog=catalog)
    if any(ref.split(':')[0] != settings['primary-edition'] for ref in units):
        raise ValueError('selected units must belong to the primary edition')
    context_scope = {field: strings(scope, field) for field in SCOPE_FIELDS}
    derived = {'scope-units': list(units), 'scope-volumes': [volume] if volume else []}
    for field, values in derived.items():
        if field in scope and set(strings(scope, field)) != set(values):
            raise ValueError(f'{field} contradicts selected source units')
        context_scope[field] = values
    dependencies = {}

    def cached_read(path):
        key = ('bytes', path)
        if key not in cache:
            data = read_source(project, path)
            cache[key] = (data, digest(data))
        return cache[key]

    def read(path):
        data, fingerprint = cached_read(path)
        dependencies[path] = fingerprint
        return data

    def inventory_digest(key, paths):
        if memory_input is not None:
            key = ('memory-input', json.dumps(memory_input, sort_keys=True), *key)
        if key not in cache:
            inventory = {p: cached_read(p)[1] for p in paths}
            cache[key] = digest(json.dumps(inventory, sort_keys=True).encode())
        return cache[key]

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
        path, _ = find_record(project, 'edition-id', edition, catalog=catalog)
        read(path)
    primary_text = [text(path) for path, _ in selected]
    auxiliary_paths = set()
    alignment_digest = inventory_digest(('alignments',), (p for p in catalog if p.startswith('kb/source-comparisons/')))
    for path, doc in catalog.items():
        if path.startswith('kb/source-comparisons/'):
            if doc.metadata.get('status') == 'accepted' and set(strings(doc.metadata, 'source-units')) & set(units):
                read(path)
                for ref in strings(doc.metadata, 'reference-units'):
                    if ref.split(':')[0] in settings['auxiliary-editions']:
                        auxiliary_paths.add(resolve_unit(project, ref, catalog=catalog)[0])
    references = [text(path) for path in sorted(auxiliary_paths)]
    ordered = sorted((d.metadata.get('order', 0), p) for p, d in catalog.items() if p.startswith(f'sources/{primary}/') and 'unit-id' in d.metadata and d.metadata.get('volume-id', '') == volume)
    chosen_paths = {p for p, _ in selected}
    neighbors = set()
    for index, (_, path) in enumerate(ordered):
        if path in chosen_paths:
            for offset in (-1, 1):
                if 0 <= index + offset < len(ordered):
                    neighbors.add(ordered[index + offset][1])
    neighbor_text = [text(path) for _, path in ordered if path in neighbors and path not in chosen_paths]
    rules = []
    for path in select_memory(project, direction, context_scope, catalog=catalog):
        metadata = catalog[path].metadata
        rules.append(dict(text(path), **{'record-id': metadata['record-id'],
            'scope': {field: strings(metadata, field) for field in SCOPE_FIELDS},
            'supersedes': metadata.get('supersedes')}))
    entities = []
    for entity in context_scope['scope-entities']:
        if memory_input is not None and entity in memory_input['external-entities']:
            continue
        path, _ = find_record(project, 'entity-id', slug(entity), catalog=catalog)
        entities.append(text(path))
    memory_digest = inventory_digest(('memory', direction), (p for p in catalog if p.startswith(f'translations/{direction}/memory/')))
    source_digest = inventory_digest(('sources', *editions), (p for p in catalog if any(p.startswith(f'sources/{e}/') for e in editions)))
    _, primary_doc = find_record(project, 'edition-id', primary, catalog=catalog)
    packet = {'packet-version': 1, 'direction': direction, 'units': list(units), 'scope': context_scope,
            'primary-text': primary_text, 'reference-text': references, 'neighbor-text': neighbor_text,
            'rules': rules, 'entities': entities, 'dependencies': dict(sorted(dependencies.items())),
            'memory-catalog-digest': memory_digest,
            'source-catalog-digest': source_digest,
            'alignment-catalog-digest': alignment_digest,
            'provenance': {'primary-edition': primary, 'auxiliary-editions': settings['auxiliary-editions'],
                           'indirect': primary_doc.metadata['edition-role'] == 'translation', 'language': settings['language'],
                           'inheritance': settings['inheritance']},
            'instructions': 'Apply each memory rule only within its scope; supersedes overrides its parent only within that scope. Primary source controls meaning. Neighbor text is read-only context, not output. Preserve deliberate ambiguity and reveal timing. Hidden material is trusted context only, never publishable prose.'}
    if memory_input is not None:
        packet.update({'packet-version': 2, 'memory-input': memory_input})
    return packet
