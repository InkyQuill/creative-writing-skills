"""Reference resolution records what is known, independently of folder purpose."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Literal
from urllib.parse import unquote, urlsplit

from .documents import read_document
from .project import Project


@dataclass(frozen=True)
class SourceReference:
    kind: Literal['file', 'url', 'receipt', 'description']
    resolution: Literal['resolved', 'missing', 'unsafe', 'unverified', 'malformed']
    path: str | None = None
    authority: Literal['unknown', 'provisional', 'accepted', 'archived'] = 'unknown'
    reason: str | None = None


def resolve_source(project: Project, source: str) -> SourceReference:
    if not isinstance(source, str) or not source.strip():
        return SourceReference('description', 'malformed', reason='empty citation')
    source = source.strip()
    if source.startswith('note:'):
        return SourceReference('description', 'unverified' if source[5:].strip() else 'malformed', reason='descriptive citation is not machine verified')
    if source.startswith('decision:'):
        from .checks.journal import is_committed_decision
        exists = is_committed_decision(project, source[9:])
        return SourceReference('receipt', 'resolved' if exists else 'missing', reason='transaction receipt does not establish author approval')
    explicit = source.startswith('file:')
    raw = source[5:] if explicit else source
    try:
        parsed = urlsplit(raw)
        if not explicit and parsed.scheme.lower() in {'http', 'https'}:
            valid = bool(parsed.hostname) and not any(c.isspace() for c in raw)
            return SourceReference('url', 'unverified' if valid else 'malformed', reason='remote content was not fetched')
        if not explicit and (parsed.scheme or parsed.netloc) and '://' in raw:
            return SourceReference('url', 'malformed', reason='unsupported reference scheme')
        pathlike = explicit or '/' in raw or '\\' in raw or bool(Path(parsed.path).suffix)
        if not pathlike and not (project.root / raw).is_file():
            return SourceReference('description', 'unverified', reason='descriptive citation is not machine verified')
        if re.search(r'%(?![0-9a-fA-F]{2})', parsed.path):
            return SourceReference('file', 'malformed', reason='invalid percent escape')
        decoded = unquote(parsed.path, errors='strict')
        windows = PureWindowsPath(decoded)
        if not decoded or '\x00' in decoded or '\\' in decoded or Path(decoded).is_absolute() or windows.drive or '..' in Path(decoded).parts:
            return SourceReference('file', 'unsafe', reason='path escapes workspace or is malformed')
        relative = Path(decoded).as_posix()
        if not Path(relative).parts:
            return SourceReference('file', 'malformed', reason='workspace root is not a file citation')
        if Path(relative).parts[0] in {'.creative-writing', '.git'}:
            return SourceReference('file', 'unsafe', reason='protected service data')
        current = project.root
        for part in Path(relative).parts:
            current /= part
            if current.is_symlink():
                return SourceReference('file', 'unsafe', relative, reason='symlink is not followed')
            if current != project.root / relative and any((current / marker).is_file() for marker in ('project.md', '.cws-layout.json')):
                return SourceReference('file', 'unsafe', relative, reason='nested project boundary')
        if not current.is_file():
            return SourceReference('file', 'missing', relative)
        authority = 'unknown'
        reason = None
        if current.suffix.casefold() == '.md':
            read = read_document(current.read_bytes())
            if read.document is not None:
                status = read.document.metadata.get('status')
                if status in {'accepted', 'archived'}:
                    authority = status
                elif status in {'working', 'draft', 'review', 'ready', 'provisional', 'proposed'}:
                    authority = 'provisional'
            else:
                reason = 'metadata is unassessed'
        else:
            reason = 'file exists; content is unassessed'
        return SourceReference('file', 'resolved', relative, authority, reason)
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        return SourceReference('file', 'malformed', reason=str(error))
