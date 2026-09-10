"""Structural translation findings; never a literary quality certificate."""
from ..findings import Finding
from ..translation.catalog import load_catalog
from ..translation.contract import translation_kind, strings
from ..translation.directions import effective_direction
from ..translation.drafts import translation_status


def check_translation(project):
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
    for path, doc in records.items():
        if translation_kind(path) == 'translation-accepted':
            for unit in strings(doc.metadata, 'source-units'):
                key = (doc.metadata.get('direction-id'), unit)
                if key in accepted:
                    add('CW-TRANS-021', f'duplicate accepted coverage: {unit}', path, 'error')
                accepted[key] = path
        if translation_kind(path) == 'translation-drafts':
            try:
                state = translation_status(project, path)
                if state['freshness'] != 'current':
                    add('CW-TRANS-010', 'translation inputs changed; review dependent prose', path)
            except (OSError, ValueError, RuntimeError) as error:
                add('CW-TRANS-011', str(error), path, 'error')
    for path, doc in records.items():
        if translation_kind(path) != 'direction':
            continue
        direction = doc.metadata['direction-id']
        volumes = strings(doc.metadata, 'coverage') or ['']
        for volume in volumes:
            try:
                settings = effective_direction(project, direction, volume)
                units = [f'{settings["primary-edition"]}:{d.metadata["unit-id"]}' for p, d in records.items() if p.startswith(f'sources/{settings["primary-edition"]}/') and 'unit-id' in d.metadata and d.metadata.get('volume-id', '') == volume]
                if not units:
                    add('CW-TRANS-022', f'no working source units registered for {volume or "book"}', path)
                for unit in units:
                    if (direction, unit) not in accepted:
                        add('CW-TRANS-020', f'no accepted translation for {unit}', path)
            except (OSError, ValueError) as error:
                add('CW-TRANS-002', str(error), path, 'error')
    return findings
