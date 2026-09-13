"""Structural translation findings; never a literary quality certificate."""
from collections import defaultdict
from ..findings import Finding
from ..translation.catalog import load_catalog
from ..translation.contract import translation_kind, strings, slug
from ..translation.directions import effective_direction
from ..translation.drafts import translation_status


def check_translation(project):
    """Inspect one catalog snapshot, preserving diagnostics from independent records."""
    if project.manifest.metadata.get('schema-version') != 2:
        return []
    findings = []

    def add(code, message, path, severity='warning'):
        findings.append(Finding(code, severity, message, path=path, next_action='Inspect the affected translation record; preserve accepted prose.'))

    try:
        records = load_catalog(project)
    except (OSError, ValueError) as error:
        add('CW-TRANS-001', str(error), 'project.md', 'error')
        return findings
    accepted = {}
    units_by_edition_volume = defaultdict(list)
    # Caches belong to this invocation only; a later check must see user edits.
    cache = {}
    for path, doc in records.items():
        kind = translation_kind(path)
        if kind == 'source-unit':
            edition = path.split('/')[1]
            units_by_edition_volume[(edition, doc.metadata.get('volume-id', ''))].append(f'{edition}:{doc.metadata["unit-id"]}')
        if kind == 'translation-accepted':
            try:
                direction = slug(doc.metadata.get('direction-id'))
                for unit in strings(doc.metadata, 'source-units'):
                    key = (direction, unit)
                    if key in accepted:
                        add('CW-TRANS-021', f'duplicate accepted coverage: {unit}', path, 'error')
                    accepted[key] = path
            except (KeyError, TypeError, ValueError) as error:
                add('CW-TRANS-001', str(error), path, 'error')
        if kind == 'translation-drafts':
            try:
                state = translation_status(project, path, catalog=records, cache=cache)
                if state['freshness'] == 'unknown':
                    add('CW-TRANS-012', 'external memory unverified; obtain fresh public observations or inspect the recorded fallback', path)
                elif state['freshness'] == 'needs-review':
                    add('CW-TRANS-010', 'translation inputs changed; review dependent prose', path)
            except (KeyError, OSError, TypeError, ValueError, RuntimeError) as error:
                add('CW-TRANS-011', str(error), path, 'error')
    for path, doc in records.items():
        if translation_kind(path) != 'direction':
            continue
        try:
            direction = slug(doc.metadata.get('direction-id'))
            volumes = strings(doc.metadata, 'coverage') or ['']
        except (TypeError, ValueError) as error:
            add('CW-TRANS-002', str(error), path, 'error')
            continue
        for volume in volumes:
            try:
                settings = effective_direction(project, direction, volume, catalog=records)
                units = units_by_edition_volume[(settings['primary-edition'], volume)]
                if not units:
                    add('CW-TRANS-022', f'no working source units registered for {volume or "book"}', path)
                for unit in units:
                    if (direction, unit) not in accepted:
                        add('CW-TRANS-020', f'no accepted translation for {unit}', path)
            except (KeyError, OSError, TypeError, ValueError) as error:
                add('CW-TRANS-002', str(error), path, 'error')
    return findings
