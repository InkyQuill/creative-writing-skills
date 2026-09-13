"""Recoverable translated prose lifecycle, independent of input freshness."""
import uuid
from pathlib import PurePosixPath
from ..documents import parse_document
from ..drafts import _reject_hidden_material, _strip_balanced_ai_wrappers, _validate_accepted_manuscript
from ..transactions import TransactionStore
from .catalog import load_catalog, make_plan, read_source, render, replacement
from .contract import slug, strings, translation_kind
from .context import rebuild_packet, digest
from .external_memory import external_freshness, validate_memory_input


def _draft(project, path):
    if translation_kind(path) != 'translation-drafts':
        raise ValueError('expected a translation draft path')
    doc = parse_document(read_source(project, path))
    if doc.metadata.get('direction-id') != PurePosixPath(path).parts[1]:
        raise ValueError('draft direction does not match path')
    if doc.metadata.get('status') not in ('draft', 'reviewed', 'accepted'):
        raise ValueError(f'missing or invalid draft status: {path}')
    return doc


def _packet(project, doc):
    identifier = doc.metadata.get('packet-transaction')
    manifest = TransactionStore(project).manifest(identifier)
    packet = manifest['metadata'].get('translation-packet')
    if not isinstance(packet, dict) or packet.get('direction') != doc.metadata.get('direction-id') or packet.get('units') != strings(doc.metadata, 'source-units'):
        raise ValueError('missing or mismatched translation packet')
    return packet


def _target(path):
    return str(PurePosixPath(path).parent.parent / 'accepted' / PurePosixPath(path).name)


def plan_translation_draft(project, direction, draft_id, packet, content):
    slug(direction)
    slug(draft_id)
    if not isinstance(packet, dict):
        raise ValueError('packet must be a JSON object')
    if packet.get('direction') != direction or packet != rebuild_packet(project, packet):
        raise ValueError('translation packet is stale or has been modified')
    volume = next(iter(packet['scope']['scope-volumes']), '')
    path = f'translations/{direction}' + (f'/volumes/{volume}' if volume else '') + f'/drafts/{draft_id}.md'
    target = _target(path)
    before = read_source(project, target) if (project.root / target).exists() else None
    transaction_id = uuid.uuid4().hex
    metadata = {'direction-id': direction, 'draft-id': draft_id, 'source-units': packet['units'], 'packet-transaction': transaction_id, 'base-revision': digest(before) if before is not None else 'absent', 'status': 'draft'}
    return make_plan(project, ('translation', 'draft'), [replacement(project, path, render(metadata, content.decode('utf-8-sig')))], {'transaction-id': transaction_id, 'translation-packet': packet, 'read-guards': packet['dependencies']})


def translation_status(project, draft_path, *, catalog=None, cache=None, external_memory_observed=None):
    doc = _draft(project, draft_path)
    packet = _packet(project, doc)
    external = external_freshness(packet.get('memory-input', {}), external_memory_observed)
    changed, diagnostics = [], []
    for path, expected in packet['dependencies'].items():
        try:
            if digest(read_source(project, path)) != expected:
                changed.append(path)
        except (OSError, ValueError):
            changed.append(path)
    try:
        current = rebuild_packet(project, packet, catalog=catalog, cache=cache)
        for key in ('memory-catalog-digest', 'source-catalog-digest', 'alignment-catalog-digest'):
            if packet.get(key) != current.get(key):
                diagnostics.append(key + ' changed')
        if current != packet and not diagnostics:
            diagnostics.append('translation packet data changed')
    except (OSError, ValueError) as error:
        diagnostics.append(str(error))
    freshness = 'needs-review' if changed or diagnostics else external
    if external != 'current':
        diagnostics.append('external memory ' + ('changed or missing' if external == 'needs-review' else 'unverified'))
    return {'status': doc.metadata['status'], 'freshness': freshness, 'changed-dependencies': sorted(changed), 'diagnostics': diagnostics}


def plan_translation_status(project, path, status):
    doc = _draft(project, path)
    if status != 'reviewed' or doc.metadata.get('status') not in ('draft', 'reviewed'):
        raise ValueError('only an active draft can be marked reviewed')
    metadata = dict(doc.metadata, status='reviewed', **{'review-hash': digest(doc.body.encode())})
    return make_plan(project, ('translation', 'set-status'), [replacement(project, path, render(metadata, doc.body))])


def plan_translation_accept(project, draft_path, *, external_memory_observed=None, external_fallback_note=None):
    doc = _draft(project, draft_path)
    if doc.metadata.get('status') != 'reviewed' or doc.metadata.get('review-hash') != digest(doc.body.encode()):
        raise ValueError('draft must be reviewed after its last prose edit')
    packet = _packet(project, doc)
    if packet['packet-version'] != 2 and (external_memory_observed is not None or external_fallback_note is not None):
        raise ValueError('external-memory acceptance options require packet-version 2')
    if external_fallback_note is not None and (not isinstance(external_fallback_note, str) or not external_fallback_note.strip()):
        raise ValueError('external fallback note must be nonempty UTF-8 text')
    freshness = translation_status(project, draft_path, external_memory_observed=external_memory_observed)['freshness']
    if freshness == 'needs-review':
        raise ValueError('translation inputs changed; create and review a fresh draft')
    if freshness == 'unknown' and external_fallback_note is None:
        raise ValueError('external memory is unverified; fresh observations or a task-specific fallback note are required')
    target = _target(draft_path)
    existing = read_source(project, target) if (project.root / target).exists() else None
    if (digest(existing) if existing is not None else 'absent') != doc.metadata['base-revision']:
        raise ValueError('accepted base changed; preserve the user edit and rebuild the draft')
    coverage_guard = {'direction': doc.metadata['direction-id'], 'target': target, 'units': packet['units']}
    if packet['packet-version'] == 2:
        coverage_guard['excluded-file-memory'] = packet['memory-input']['excluded-file-memory']
    validate_accepted_coverage(project, coverage_guard)
    _reject_hidden_material(doc.body.encode())
    body = _strip_balanced_ai_wrappers(doc.body)
    _validate_accepted_manuscript(body.encode())
    if not body.strip():
        raise ValueError('cannot accept empty translation')
    metadata = dict(doc.metadata, status='accepted')
    details = {'accepted-coverage-guard': coverage_guard, 'translation-packet': packet, 'read-guards': packet['dependencies']}
    if packet['packet-version'] == 2:
        # Historical acceptance evidence does not override later observations.
        metadata['external-memory-freshness'] = freshness
        details.update({'external-memory-freshness': freshness, 'external-memory-observed': external_memory_observed})
        if external_fallback_note is not None:
            details['external-fallback-note'] = external_fallback_note
    accepted = render(metadata, body)
    return make_plan(project, ('translation', 'accept'), [replacement(project, target, accepted), replacement(project, draft_path, render(metadata, doc.body))], details)


def validate_accepted_coverage(project, guard):
    """Recheck uniqueness under the transaction lock before writing accepted prose."""
    exclusions = validate_memory_input(project, slug(guard['direction']), {},
                                       {'excluded-file-memory': guard.get('excluded-file-memory', [])})['excluded-file-memory']
    for path, other in load_catalog(project, excluded_memory=exclusions).items():
        if (translation_kind(path) == 'translation-accepted' and path != guard['target']
                and other.metadata.get('direction-id') == guard['direction']
                and set(strings(other.metadata, 'source-units')) & set(guard['units'])):
            raise ValueError('duplicate accepted source coverage')
