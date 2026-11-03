"""Operation-local external memory selections; no service access or trust policy."""
from dataclasses import asdict, dataclass
from .contract import slug, strings


@dataclass(frozen=True)
class ExternalMemoryRef:
    provider: str
    namespace: str
    record_kind: str
    record_id: str
    revision: str

    def __post_init__(self):
        for field, value in asdict(self).items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'external memory {field} must be a nonempty string')


def _indexed(refs):
    result = {}
    for ref in refs:
        if not isinstance(ref, ExternalMemoryRef):
            raise ValueError('expected a validated external memory reference')
        key = (ref.provider, ref.namespace, ref.record_kind, ref.record_id)
        if key in result and result[key] != ref.revision:
            raise ValueError('conflicting external memory revisions for one logical identity')
        result[key] = ref.revision
    return result


def assess_external_memory(captured: tuple[ExternalMemoryRef, ...],
                           observed: tuple[ExternalMemoryRef, ...] | None) -> str:
    """Return current, needs-review, or unknown; never access a service."""
    expected = _indexed(captured)
    actual = None if observed is None else _indexed(observed)
    if not expected:
        return 'current'
    if actual is None:
        return 'unknown'
    return 'needs-review' if any(actual.get(key) != revision for key, revision in expected.items()) else 'current'


def _references(value, *, allow_unverified=False):
    if not isinstance(value, list):
        raise ValueError('external memory references must be a JSON array')
    result = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError('external memory reference must be a JSON object')
        if allow_unverified and set(item) == {'unverified'}:
            reason = item['unverified']
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError('unverified external memory needs a nonempty technical reason')
            result.append({'unverified': reason})
        else:
            if set(item) != set(ExternalMemoryRef.__dataclass_fields__):
                raise ValueError('invalid external memory reference fields')
            result.append(asdict(ExternalMemoryRef(**item)))
    _indexed(tuple(ExternalMemoryRef(**item) for item in result if 'unverified' not in item))
    return result


def validate_memory_input(project, direction, scope, value):
    """Validate and copy the three documented selections before any catalog scan."""
    if not isinstance(value, dict) or set(value) - {'external-memory-refs', 'excluded-file-memory', 'external-entities'}:
        raise ValueError('invalid memory-input object or unknown selection key')
    refs = _references(value.get('external-memory-refs', []), allow_unverified=True)
    exclusions = value.get('excluded-file-memory', [])
    if not isinstance(exclusions, list):
        raise ValueError('excluded-file-memory must be a JSON array')
    prefix = f'translations/{direction}/memory'
    for path in exclusions:
        if (not isinstance(path, str) or not path or
                (path.rstrip('/') != prefix and not path.startswith(prefix + '/')) or
                any(part in ('', '.', '..') for part in path.rstrip('/').split('/'))):
            raise ValueError('exclude only file or directory selectors under this direction memory/')
        project.resolve(path, for_write=True)
    entities = value.get('external-entities', {})
    if not isinstance(entities, dict):
        raise ValueError('external-entities must be a JSON object')
    selected_entities = {}
    for entity, references in entities.items():
        if slug(entity) not in strings(scope, 'scope-entities'):
            raise ValueError('external entity must be in the task scope-entities')
        selected_entities[entity] = _references(references, allow_unverified=True)
        if not selected_entities[entity]:
            raise ValueError('external entity needs at least one reference')
    result = {'external-memory-refs': refs, 'excluded-file-memory': list(exclusions),
              'external-entities': selected_entities}
    # An identity may occur in several entity lists or in the general references.
    _indexed(captured_references(result)[0])
    return result


def captured_references(memory_input):
    items = list(memory_input.get('external-memory-refs', []))
    for references in memory_input.get('external-entities', {}).values():
        items.extend(references)
    return (tuple(ExternalMemoryRef(**item) for item in items if 'unverified' not in item),
            any('unverified' in item for item in items))


def external_freshness(memory_input, observed):
    """Observations are caller reports, not authenticated remote verification."""
    actual = None if observed is None else tuple(ExternalMemoryRef(**item) for item in _references(observed))
    refs, unverified = captured_references(memory_input)
    state = assess_external_memory(refs, actual)
    return 'unknown' if unverified and state != 'needs-review' else state
