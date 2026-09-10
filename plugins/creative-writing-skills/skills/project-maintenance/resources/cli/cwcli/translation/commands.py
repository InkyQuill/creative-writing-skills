"""Translation command adapters. Planning never mutates project files."""
import argparse
from dataclasses import replace
from ..documents import Document, render_document
from ..project import discover_project
from ..schema import required_paths
from ..transactions import Change, TransactionEngine, TransactionPlan, TransactionError, TransactionConflict
from .contract import project_settings


def add_commands(subparsers, error_stream):
    parser = subparsers.add_parser('translation', error_stream=error_stream)
    commands = parser.add_subparsers(dest='translation_command', required=True)
    enable = commands.add_parser('enable', error_stream=error_stream)
    enable.add_argument('--work-kind', choices=('book', 'series'), default='book')
    enable.add_argument('--apply', action='store_true')
    enable.add_argument('--format', choices=('text', 'json'), default=argparse.SUPPRESS)


def plan_enable(project, work_kind):
    kind, _, enabled = project_settings(project.manifest.metadata)
    if enabled:
        raise ValueError('translation already enabled; preserve existing settings')
    for name in ('sources', 'translations', 'kb/entities', 'kb/source-comparisons'):
        path = project.resolve(name, for_write=True)
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            raise ValueError(f'populated translation path requires explicit registration: {name}')
    metadata = dict(project.manifest.metadata, **{'schema-version': 2, 'project-kind': kind, 'work-kind': work_kind, 'translation-enabled': True})
    manifest = replace(project.manifest, metadata=metadata)
    changes = [Change('project.md', (project.root / 'project.md').read_bytes(), render_document(manifest))]
    _, files = required_paths(metadata)
    for path in files:
        if path.endswith('_index.md') and not (project.root / path).exists():
            changes.append(Change(path, None, render_document(Document({'generated': True}, '# Index\n', '\n', False))))
    from .catalog import make_plan
    return make_plan(project, ("translation", "enable"), changes)


def run_translation(args, *, cwd, stdout, stderr):
    from ..app import _preview_or_apply, _write_command_error
    try:
        project = discover_project(cwd)
        plan = plan_enable(project, args.work_kind)
        return _preview_or_apply(TransactionEngine(project), plan, apply=args.apply, output_format=args.format, stdout=stdout)
    except (OSError, ValueError, TransactionError) as error:
        return _write_command_error(error, conflict=isinstance(error, TransactionConflict), output_format=args.format, stdout=stdout, stderr=stderr)
