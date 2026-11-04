"""Flat metadata contract for opt-in translation projects."""
import re
from pathlib import PurePosixPath

SCOPE_FIELDS = ('scope-volumes', 'scope-units', 'scope-entities', 'scope-relationships')


def project_settings(metadata):
    version = metadata.get('schema-version')
    if type(version) is not int or version not in (1, 2):
        raise ValueError('unsupported project schema')
    if version == 1:
        return 'authoring', 'book', False
    kind, work = metadata.get('project-kind'), metadata.get('work-kind')
    if kind not in ('authoring', 'translation') or work not in ('book', 'series') or metadata.get('translation-enabled') is not True:
        raise ValueError('v2 requires project-kind, work-kind and translation-enabled: true')
    return kind, work, True


def slug(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value):
        raise ValueError(f'invalid portable identity: {value!r}')
    return value


def strings(metadata, key):
    value = metadata.get(key, [])
    if value == '':
        return []  # The restricted frontmatter parser reads an empty list as an empty field.
    if not isinstance(value, list) or any(not isinstance(v, str) or not v for v in value):
        raise ValueError(f'{key} must be a list of nonempty strings')
    if len(set(value)) != len(value):
        raise ValueError(f'{key} contains duplicates')
    return value


def translation_kind(relative):
    p = PurePosixPath(relative)
    parts = p.parts
    if p.suffix != '.md' or 'originals' in parts:
        return None
    if relative in ('sources/_index.md', 'translations/_index.md', 'kb/entities/_index.md', 'kb/source-comparisons/_index.md'):
        return 'generated-index'
    if len(parts) == 3 and parts[0] == 'kb' and parts[1] in ('entities', 'source-comparisons'):
        return 'entity' if parts[1] == 'entities' else 'alignment'
    if len(parts) < 3 or parts[0] not in ('sources', 'translations'):
        return None
    if parts[0] == 'sources':
        if parts[2:] == ('edition.md',):
            return 'edition'
        rest = parts[2:]
        if len(rest) == 4 and rest[0] == 'volumes':
            rest = rest[2:]
        return 'source-unit' if len(rest) == 2 and rest[0] == 'text' else None
    rest = parts[2:]
    if rest == ('translation.md',):
        return 'direction'
    if rest == ('_index.md',):
        return 'generated-index'
    if rest == ('memory', 'style.md') or (len(rest) == 3 and rest[0] == 'memory' and rest[1] in ('terms', 'voices', 'decisions')):
        return 'translation-memory'
    if len(rest) >= 3 and rest[0] == 'volumes':
        rest = rest[2:]
        if rest == ('settings.md',):
            return 'direction-settings'
    if len(rest) == 2 and rest[0] in ('drafts', 'reviews', 'accepted'):
        return 'translation-' + rest[0]
    return None


def scope_matches(record, context):
    return all(not strings(record, field) or bool(set(strings(record, field)) & set(strings(context, field))) for field in SCOPE_FIELDS)


def scope_contains(general, specific):
    """Every point in specific scope is also inside general scope."""
    return all(not strings(general, field) or (bool(strings(specific, field)) and set(strings(specific, field)) <= set(strings(general, field))) for field in SCOPE_FIELDS)


def validate_scope_size(scope):
    """Bound memory selection to 4096 points; empty dimensions count as one."""
    size = 1
    for field in SCOPE_FIELDS:
        size *= max(1, len(strings(scope, field)))
        if size > 4096:
            raise ValueError('translation scope is too large (maximum 4096 combinations); split the context request')
