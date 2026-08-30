# Agent Workflows

## Establish the mechanical floor

1. Resolve the nearest `project.md` from the material the user placed in scope.
2. Run the bundled `resources/cli/cw.py` directly with Python; `cli-doctor`
   will also try to install or refresh its managed launcher without making that
   launcher a prerequisite.
3. Run `check all` or the checker relevant to the task and inspect its
   structured findings.
4. Preview each unambiguous repair, confirm the diff stays in scope, then use
   `--apply`. Run the affected check again.

Exit 0 continues. Exit 1 means inspect findings and continue unrelated
creative work; repairable mechanical warnings never block prose review or
unrelated creative work. Exit 2 routes to the `cli-doctor` workflow for
agent-owned runtime setup.

## Prepare review context

Use `context draft`, `context chapter`, or `context kb` with the appropriate
trusted, reader, or character role. Context planning is read-only. Treat
unresolved references as warnings to inspect, not permission to invent
context. Restricted `context --snapshot` writes derived cache without
`--apply`. Preview and apply `clean-context` only to remove derived cache; it
does not enter transaction history.

## Manage a draft

Create the working copy with `draft create`, change lifecycle state through
`draft set-status`, and run checks before requesting author acceptance. If the
target changed, preview `draft rebase`; do not overwrite it. Preview
`draft accept` only after the author confirms acceptance. KB synchronization is
a separate transaction, not automatically a separate confirmation: re-read the
accepted prose and preview a recoverable KB transaction for facts it directly
and unambiguously establishes. Ask only about ambiguity, inference, conflict,
retcon, uncertain source tags, or uncertain character and reader knowledge
boundaries. Use `draft abandon` for a rejected draft so it moves to archive
without becoming canon.

For bonus prose, target `story/side-stories/<name>.md` and retain required
`after: <accepted-manuscript-path>` placement metadata plus any optional
lower-case `subtype`. Review the aggregate neighbors with `context chapter`.
Do not assign the side story a chapter number or renumber main chapters.

## Migrate an older layout

Run `migrate --plan --format json` from the legacy project and save its output
as an agent working file. Inspect every object in `unresolved`. Ask the author
only for a semantic decision when a source's role or merged meaning is
ambiguous; the agent edits the plan and manages its hash.

For each resolved item that belongs in the canonical project, remove it from
`unresolved` and add one or more strict operations. Use only these JSON shapes
and canonical schema-v1 destinations:

```json
{"source": "chapters/one.md", "destination": "story/chapters/one.md", "action": "move"}
{"source": "story/chapters/one.md", "destination": "story/chapters/one.md", "action": "preserve"}
{"source": "side-stories/omake.md", "destination": "story/side-stories/omake.md", "action": "move"}
{"sources": ["kb/timeline/a.md", "kb/timeline/b.md"], "destination": "kb/continuity/timeline.md", "action": "merge", "content": "# Reviewed merged content\n"}
```

A `move` has one source and a different destination. A `preserve` has identical
source and destination. A `merge` has a non-empty unique `sources` list and
the exact reviewed UTF-8 output in `content`; it does not ask the CLI to invent
the merge.

The planner treats legacy `inspiration/` as one opaque author-owned corpus. It
adds an in-place `preserve` operation for every regular file, including Pocket
Editor binders and review sidecars, images, documents, hidden metadata, and
unknown binary files. Do not remove those operations or reinterpret the files
as Markdown roles. Inspect any `unsafe-inspiration-entry` separately; the CLI
does not follow links, special entries, or nested project boundaries.

An `unknown-role` item with no canonical destination may intentionally remain
unmanaged. In that branch, remove the item from `unresolved` and add no
operation; leave its source file untouched. For another unmanaged path, do not
invent a `preserve` operation: migration validation accepts it only at a
canonical schema-v1 destination or for an in-place file below the recognized
`inspiration/` corpus.

Assign every managed source once, keep destinations unique, preserve unknown
files, and never reinterpret ambiguous material as canon automatically. Do not
continue until every item is resolved and the plan contains `"unresolved": []`.

After any plan edit, recompute and update `plan-hash` with the bundled canonical
function. This agent-only snippet accepts the CLI package directory and plan
path as its two arguments:

```bash
python3 - <project-maintenance-skill>/resources/cli <plan.json> <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from cwcli.migration import canonical_plan_hash

path = Path(sys.argv[2])
payload = json.loads(path.read_text(encoding="utf-8"))
payload["plan-hash"] = canonical_plan_hash(payload)
path.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
```

Copy the resulting lowercase hash exactly into both commands:

```text
migrate --preview <plan.json> --expect-plan-hash <hash>
migrate --apply <plan.json> --expect-plan-hash <hash>
```

Run apply only after preview validates the same file and shows the intended
full diff. Any further plan edit requires another rehash and preview.

## Correct a mistake or interrupted write

Use `history` and `history show <transaction-id>` to inspect exact recorded
changes. Preview `undo <transaction-id>` and apply it only while its after-state
still matches; never rewrite history or overwrite newer work. For an
interrupted prepared/applying transaction, inspect `doctor`, preview
`recover <transaction-id>`, and apply rollback only when the CLI reports it as
recoverable. Preserve conflicted bytes and journal evidence for manual agent
diagnosis.

The agent owns hashes, tags, indexes, base revisions, repair-command selection
and execution, runtime setup, and optional launcher setup. Ask the author for
semantic choices and approval boundaries, not mechanical maintenance.
