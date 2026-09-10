"""Recoverable translated prose lifecycle, independent of input freshness."""
import uuid
from pathlib import PurePosixPath
from ..documents import parse_document
from ..drafts import _reject_hidden_material, _strip_balanced_ai_wrappers, _validate_accepted_manuscript
from ..transactions import TransactionStore
from .catalog import load_catalog, make_plan, read_source, render, replacement
from .contract import slug, strings, translation_kind
from .context import build_packet, digest
from .directions import resolve_unit


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
    if packet.get('direction') != direction or packet != build_packet(project, direction, tuple(packet.get('units', [])), packet.get('scope', {})):
        raise ValueError('translation packet is stale or has been modified')
    _, source = resolve_unit(project, packet['units'][0])
    volume = source.metadata.get('volume-id', '')
    path = f'translations/{direction}' + (f'/volumes/{volume}' if volume else '') + f'/drafts/{draft_id}.md'
    target = _target(path)
    before = read_source(project, target) if (project.root / target).exists() else None
    transaction_id = uuid.uuid4().hex
    metadata = {'direction-id': direction, 'draft-id': draft_id, 'source-units': packet['units'], 'packet-transaction': transaction_id, 'base-revision': digest(before) if before is not None else 'absent', 'status': 'draft'}
    return make_plan(project, ('translation', 'draft'), [replacement(project, path, render(metadata, content.decode('utf-8-sig')))], {'transaction-id': transaction_id, 'translation-packet': packet, 'read-guards': packet['dependencies']})


def translation_status(project, draft_path, *, catalog=None, cache=None):
    doc = _draft(project, draft_path)
    packet = _packet(project, doc)
    changed, diagnostics = [], []
    for path, expected in packet['dependencies'].items():
        try:
            if digest(read_source(project, path)) != expected:
                changed.append(path)
        except (OSError, ValueError):
            changed.append(path)
    try:
        current = build_packet(project, packet['direction'], tuple(packet['units']), packet['scope'], catalog=catalog, cache=cache)
        for key in ('memory-catalog-digest', 'source-catalog-digest', 'alignment-catalog-digest'):
            if packet.get(key) != current.get(key):
                diagnostics.append(key + ' changed')
    except (OSError, ValueError) as error:
        diagnostics.append(str(error))
    return {'status': doc.metadata['status'], 'freshness': 'needs-review' if changed or diagnostics else 'current', 'changed-dependencies': sorted(changed), 'diagnostics': diagnostics}


def plan_translation_status(project, path, status):
    doc = _draft(project, path)
    if status != 'reviewed' or doc.metadata.get('status') not in ('draft', 'reviewed'):
        raise ValueError('only an active draft can be marked reviewed')
    metadata = dict(doc.metadata, status='reviewed', **{'review-hash': digest(doc.body.encode())})
    return make_plan(project, ('translation', 'set-status'), [replacement(project, path, render(metadata, doc.body))])


def plan_translation_accept(project, draft_path):
    doc = _draft(project, draft_path)
    if doc.metadata.get('status') != 'reviewed' or doc.metadata.get('review-hash') != digest(doc.body.encode()):
        raise ValueError('draft must be reviewed after its last prose edit')
    if translation_status(project, draft_path)['freshness'] != 'current':
        raise ValueError('translation inputs changed; create and review a fresh draft')
    packet = _packet(project, doc)
    target = _target(draft_path)
    existing = read_source(project, target) if (project.root / target).exists() else None
    if (digest(existing) if existing is not None else 'absent') != doc.metadata['base-revision']:
        raise ValueError('accepted base changed; preserve the user edit and rebuild the draft')
    coverage_guard = {'direction': doc.metadata['direction-id'], 'target': target, 'units': packet['units']}
    validate_accepted_coverage(project, coverage_guard)
    _reject_hidden_material(doc.body.encode())
    body = _strip_balanced_ai_wrappers(doc.body)
    _validate_accepted_manuscript(body.encode())
    if not body.strip():
        raise ValueError('cannot accept empty translation')
    metadata = dict(doc.metadata, status='accepted')
    accepted = render(metadata, body)
    return make_plan(project, ('translation', 'accept'), [replacement(project, target, accepted), replacement(project, draft_path, render(metadata, doc.body))], {'accepted-coverage-guard': coverage_guard, 'translation-packet': packet, 'read-guards': packet['dependencies']})


def validate_accepted_coverage(project, guard):
    """Recheck uniqueness under the transaction lock before writing accepted prose."""
    for path, other in load_catalog(project).items():
        if (translation_kind(path) == 'translation-accepted' and path != guard['target']
                and other.metadata.get('direction-id') == guard['direction']
                and set(strings(other.metadata, 'source-units')) & set(guard['units'])):
            raise ValueError('duplicate accepted source coverage')
