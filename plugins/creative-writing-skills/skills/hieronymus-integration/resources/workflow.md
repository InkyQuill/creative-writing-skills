# Agreement and discovery workflow

## Activate from intent and project evidence

Load the integration when the current user asks for Hieronymus, the nearest
project agreement or instructions mention it, or a project binding refers to
it. Do not make tool availability the only activation condition. A referenced
service that is unavailable still requires the agreement's fallback to be
interpreted. Do not request installation for a file-only user and do not create
`.hieronymus.json` during discovery.

Read the current user instruction and the nearest applicable project
instructions again for this task. Preserve the agreement as free-text: keep
its conditions, source roles, exceptions, and scopes in their original words.
Do not reduce it to primary/secondary fields, a trust score, or a global mode.
When the agreement is silent, files are primary and Hieronymus is supplemental.
A current user instruction may create a local exception for the stated task;
do not persist that exception unless the user separately requests a durable
agreement change.

Apply a new user instruction in its stated scope immediately. Persist a durable
change in the nearest project instructions, preserving independent conditions;
do not globalize a local exception. Changing trust does not prove old records
were transferred. Resolve and re-read the actual project-instruction entrypoint
through $project-bootstrap before a requested edit, use the existing recoverable
project workflow, and preserve unrelated instructions.

Discover only what this task needs. Read the current source files and the
smallest relevant memory artifacts. If the installed `hiero` CLI is accessible,
`hiero project-context --cwd /path/to/project --args
'{"direction_id":null}' --json` is an optional deterministic aid for root,
instruction, and binding discovery. `ready` and `unbound` are structurally
usable. Report or resolve `ambiguous`, `unsupported`, `not_found`, or `invalid`;
never choose the first candidate. Re-read the reported instruction path
separately. The command is not required for ordinary file discovery.

Validate an existing binding as technical identity only. Use the `cws` object,
check its binding and project-contract versions independently of the project's
schema version, and resolve real series identifiers through public tools. Do
not fall back to legacy outer language fields or infer a direction, language,
or series from a map key, filename, or directory. Binding creation or repair is
a separate authorized connection task: validate paths, re-read the current
file immediately before replacement, and preserve unrelated outer fields.

## Observe capabilities without changing them

Discover public tools in the current host and inspect their current advertised
schemas before making a call. When available, `hiero status --json` provides
authenticated live status nested under `status`. Read the actual status values
at `status.instance_id`, `status.semantic.state`, and `status.readiness`.
`status.instance_id` is the observed identity of the running process and may
change after a restart; do not treat it as a persistent database ID.

`running: true` is not proof that semantic retrieval or any provider is ready.
The aggregate `status.readiness` level is not a substitute for the requested
capability's state. The MCP `hieronymus_status` tool currently reports service
availability only; it does not establish semantic readiness, provider
readiness, or service identity. A status check does not start or repair the
service.

Gate each requested operation on its specific capability and actual tool
outcome. A degraded provider may prevent strict semantic RAG while ordinary
file reads, deterministic contracts, or other local work remain available. A
degraded provider must not block unrelated local reads. Preserve warnings from
mixed recall; do not describe lexical fallback or an empty result as successful
semantic retrieval.

## Apply the agreement to current evidence

For each candidate fact or rule, retain its current source reference, actual
provenance, actual status, scope, language, and revision or returned identifier
when exposed. Distinguish author-stated project text, `<AI>` suggestions,
`<hidden>` material, Hieronymus observations, candidates, and active rules. An
active internal rule remains an activated rule inside Hieronymus, but the
free-text agreement decides whether it governs this literary task. Trust does
not equal write authorization.

Apply each source only to the role and conditions the agreement assigns it. If
the agreement is silent, use files to settle project truth and treat
Hieronymus results as advisory. If it makes Hieronymus primary or permits it to
replace file memory, work without requiring a complete Markdown memory copy.
There is no mandatory mirror and no automatic migration or deletion. Write to
both destinations only when the current user instruction authorizes both.

For an authorized transfer, inventory the selected records and their provenance,
write through supported operations, retain returned IDs, then reconcile counts,
scopes, dispositions and unresolved conflicts. Report partial completion. Do not
delete originals or create an ongoing mirror unless that work was requested.
Transfer only the records and destinations the user selected; a new preference
does not authorize whole-project ingestion or transfer. A conflict stays explicit
rather than being resolved by choosing the newest record.

When applicable sources disagree, identify the exact fact, term, voice rule,
scope, or revision in conflict. Follow an explicit local exception for the
current task. Ask one focused content question only when the agreement and
current evidence do not settle a conflict that would materially change the
work. Do not rewrite either store merely to erase the disagreement.

Keep one leading workflow: the current muse, translation skill, or direct
Hieronymus workflow stays in control and calls only bounded capabilities from
the other system. Do not recursively orchestrate muse through Hieronymus or
Hieronymus through muse.

## Continue or fall back

When Hieronymus is absent or the requested operation fails, continue every
independent file-backed part of the task. Apply the fallback conditions written
in the agreement. If no fallback is stated and the missing result would
materially change the output, explain the unavailable dependency and ask one
focused question. Do not silently substitute a lower-trust source, request an
installation, create a binding, or repair/start a service as part of the
status check.
