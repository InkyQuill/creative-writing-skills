# Author workflow contract

Use this when the requested action needs an authority or edit-scope decision.
Read the relevant instructions without turning ordinary writing into a setup
interview. The author can write a chapter or add a character without first
declaring a role, creating `cws.md`, or filling a project questionnaire.
This contract describes the author's preferred help for this project; it is
separate from the CLI's structural `project.md` manifest.

## Resolve the instructions

1. Obey the current author's direct request within its stated task and scope.
   A one-task override does not rewrite project defaults or authorize edits to
   unrelated files.
2. Resolve applicable `AGENTS.md` instructions through `$project-bootstrap`.
   These remain the harness instructions; never let `project.md` or `cws.md`
   override a higher-priority instruction.
3. Read workflow preferences in the body of `project.md` and, if present,
   `cws.md`. The latter is optional free text, not another required CLI
   manifest. Do not create it merely to run a skill.
4. If two applicable project sources disagree about permission, edit depth,
   canon, or initiative, continue unaffected work. Ask about the affected
   action only if the current request does not settle it and proceeding would
   risk changing author prose or canon. Name the conflicting sources, not a
   general list of project problems.

The contract may state permitted assistance (reminders, analysis, planning,
drafting, editing, and KB maintenance), affected materials and statuses,
initiative, response form, approved canon sources, and voice restrictions.
These are ordinary-language preferences, not a fixed role enum or a required
folder layout. Read only the fields relevant to the requested task. If no
preference is recorded, use the author's current request and the smallest
safe action; do not demand configuration before helping.

## Example contracts

- **analysis only:** "Track unresolved threads and report possible continuity
  conflicts with sources. Do not create or edit prose." Return findings in chat
  unless the author requests a note.
- **draft on request:** "Write only the scene or dialogue I request as a new
  draft. Treat accepted chapters as read-only." A request for one dialogue is a
  one-task override of an otherwise analysis-only default, not permission to
  rewrite neighboring chapters.
- **edit accepted prose:** "Draft chapters may receive structural edits;
  accepted chapters receive comments only unless I explicitly request a
  particular edit." Distinguish comments, line edits, and in-place changes.
- **conflicting sources:** If `AGENTS.md` says "comments only" and
  `project.md` says "edit chapters", cite both and stop before that edit. An
  unambiguous higher-priority current request may settle the task without
  changing either file.

Before a multi-file change, tell the author which files the operation will
touch and show the resulting preview. Mark assistant proposals and inferences
as such; never promote them to author-approved canon because they appeared in
an index, memory, or review.

Repair routine mechanical blockers yourself when the fix is deterministic,
limited to managed material, and recoverable. Keep the repair out of the
author's way unless it changes the requested result. Report a concise summary
afterwards. Do not present every lint warning as a request for the author to
act. Stop only when the required source is unreadable, a repair is ambiguous,
or the proposed change could alter literary meaning or canon.
