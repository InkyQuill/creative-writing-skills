"""Explicit source precedence, coverage and edition alignment."""
import hashlib
from ..documents import parse_document
from .catalog import find_record, load_catalog, make_plan, read_source, replacement
from .contract import project_settings, slug, strings


def resolve_unit(project, reference, *, catalog=None):
    if not isinstance(reference, str) or reference.count(':') != 1:
        raise ValueError(f'invalid unit reference: {reference}')
    edition, unit = reference.split(':')
    slug(edition)
    slug(unit)
    return find_record(project, 'unit-id', unit, prefix=f'sources/{edition}/', catalog=catalog)


def plan_direction(project, content):
    _, work, _ = project_settings(project.manifest.metadata)
    load_catalog(project)
    doc = parse_document(content)
    name = slug(doc.metadata.get('direction-id'))
    guards = {}
    volume = doc.metadata.get('volume-id')
    if volume is not None:
        slug(volume)
        if work != 'series':
            raise ValueError('volume override requires a series')
        root_path = f'translations/{name}/translation.md'
        root_bytes = read_source(project, root_path)
        root = parse_document(root_bytes)
        guards[root_path] = hashlib.sha256(root_bytes).hexdigest()
        if volume not in strings(root.metadata, 'coverage'):
            raise ValueError(f'direction does not cover {volume}')
        path = f'translations/{name}/volumes/{volume}/settings.md'
        allowed = {'direction-id', 'volume-id', 'primary-edition', 'auxiliary-editions', 'inheritance'}
        if set(doc.metadata) - allowed:
            raise ValueError('volume overrides may change only source and inheritance fields')
    else:
        path = f'translations/{name}/translation.md'
        if not isinstance(doc.metadata.get('language'), str) or not doc.metadata['language'].strip():
            raise ValueError('direction requires target language')
        if 'primary-edition' not in doc.metadata:
            raise ValueError('direction requires primary-edition')
        for item in strings(doc.metadata, 'coverage'):
            slug(item)
    for field in ('auxiliary-editions', 'inheritance'):
        strings(doc.metadata, field)
    editions = strings(doc.metadata, 'auxiliary-editions')
    if 'primary-edition' in doc.metadata:
        editions = [doc.metadata['primary-edition'], *editions]
    if len(editions) != len(set(editions)):
        raise ValueError('primary and auxiliary sources must be distinct')
    for edition in editions:
        find_record(project, 'edition-id', slug(edition))
    return make_plan(project, ('translation', 'direction'), [replacement(project, path, content)], {'read-guards': guards})


def effective_direction(project, direction, volume, *, catalog=None):
    slug(direction)
    path = f'translations/{direction}/translation.md'
    doc = parse_document(read_source(project, path)) if catalog is None else catalog[path]
    settings = dict(doc.metadata)
    _, work, _ = project_settings(project.manifest.metadata)
    if work == 'series':
        if volume not in strings(settings, 'coverage'):
            raise ValueError(f'direction does not cover {volume}')
        override = f'translations/{direction}/volumes/{slug(volume)}/settings.md'
        if (project.root / override).exists():
            metadata = (parse_document(read_source(project, override)) if catalog is None else catalog[override]).metadata
            for field in ('primary-edition', 'auxiliary-editions', 'inheritance'):
                if field in metadata:
                    settings[field] = metadata[field]
    elif volume:
        raise ValueError('book direction cannot select a volume')
    if not isinstance(settings.get('primary-edition'), str):
        raise ValueError('direction requires primary-edition')
    for edition in [settings['primary-edition'], *strings(settings, 'auxiliary-editions')]:
        _, doc = find_record(project, 'edition-id', edition, catalog=catalog)
        if work == 'series' and volume not in strings(doc.metadata, 'coverage'):
            raise ValueError(f'edition {edition} does not cover {volume}; set an explicit source override')
    for field in ('auxiliary-editions', 'inheritance', 'coverage'):
        settings[field] = strings(settings, field)
    return settings


def plan_alignment(project, content):
    doc = parse_document(content)
    name = slug(doc.metadata.get('alignment-id'))
    source, reference = strings(doc.metadata, 'source-units'), strings(doc.metadata, 'reference-units')
    relation = doc.metadata.get('relation')
    if doc.metadata.get('status') not in ('observed', 'accepted'):
        raise ValueError('alignment must be observed or accepted')
    if not source or relation not in ('equivalent', 'split', 'merge', 'reordered', 'omitted'):
        raise ValueError('alignment needs source units and a valid relation')
    if relation == 'omitted':
        if reference or not doc.body.strip():
            raise ValueError('omitted alignment needs an explanation and no reference units')
    elif not reference:
        raise ValueError('alignment needs reference units')
    for unit in [*source, *reference]:
        resolve_unit(project, unit)
    return make_plan(project, ('translation', 'alignment'), [replacement(project, f'kb/source-comparisons/{name}.md', content)])
