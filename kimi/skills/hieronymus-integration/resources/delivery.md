# Public-tool delivery recipes

Use only tools currently advertised by the host and inspect their current
schemas before each workflow. The field summaries below describe the present
public contract; omit optional fields unless current context supplies them.
Never invent identifiers, revisions, chronology, languages, provenance,
authority, receipts, or tool parameters.

Discover schemas through advertised tool metadata, read-only help, or supplied
public resources. Never probe a mutating tool with dummy, partial, or trial
payloads to discover its schema: a probe can create a real record. If the
needed schema is unavailable, report that operation as unresolved.

## Write authorization

Before any mutation, confirm that the current user has authorized that operation,
its destination, and its scope. Existing explicit authorization remains valid;
do not ask again when it already covers the operation. Source selection, trust,
and a project binding alone do not authorize writes. This gate applies to
session creation, `hieronymus_short_term_add`, `hieronymus_short_term_add_batch`,
evidence capture, `hieronymus_decide`, corrections, and initial-memory
establishment. Without authorization, do not call mutation tools; keep the result
as a local proposal for the user.

## Direction and applicability on every call

Resolve the actual CWS direction before accessing translation memory. At each
call, inspect that tool's current advertised schema and pass only supported
fields. When supported, include `story_scopes` with
`cws:direction:<direction-id>` on session creation, recall, memory search,
termbase contract and validation, and strict RAG. Do not add an unsupported
parameter merely because another tool advertises it. A stored session must carry
the same direction predicate; do not reuse one from another direction.

Every typed claim uses complete evidence-limited applicability and includes the
direction in `applicability.scope_predicates`. Add
`cws:edition:<edition-id>` only when the evidence is edition-specific. Volume,
chapter, chronology, scene, and knowledge gates remain separate and are never
relaxed by the memory agreement.

## Read recipes

When the workflow needs a stored session and none is active, use the currently
advertised `hieronymus_session_start` schema with the actual `series_slug` and
only observed optional context (`source_language`, `target_language`,
`task_type`, `volume`, `chapter`, and advertised story fields). Retain its
actual `session_id`; do not synthesize one from project paths or binding data.

For mixed session recall, call `hieronymus_recall` with the actual
`session_id`, `series_slug`, and a focused `query`. Supply `source_language`,
`target_language`, `task_type`, `volume`, `chapter`, story-context fields, and
`limit` only when observed context supports them and they match the session.
Retain the returned `recall_id`, `resulting_revision`, warnings, result IDs,
activation IDs, status/provenance fields, and non-current results. A warning
that the semantic lane is unavailable means the semantic portion did not run;
it does not erase a returned deterministic contract or other valid results.

For strict project RAG, call `hieronymus_rag_search` with the actual
`series_slug` and focused `query`; use `limit` and advertised story-context
fields only when applicable. Treat a semantic-readiness error as an unavailable
strict search, never as successful semantic retrieval. Use the returned chunk
IDs, revision information, ranks, reasons, and provenance as observed.

## Ordinary capture recipes

Use `hieronymus_short_term_add` for one session-scoped item. Its required
fields are `session_id`, `kind`, and `text`. Add only advertised optional
fields supported by actual evidence: `source_ref`, `source_role`,
`source_credibility`, `rule_intent`, language/story/semantic tags, metadata,
and ordinary claims. `source_role` is provenance metadata; it does not grant
authority. A `rule_intent` does not make the item an activated rule.

Use `hieronymus_short_term_add_batch` for an atomic set belonging to the same
active session. Pass `session_id` and `items`; every item has `kind` and `text`
plus only currently advertised optional fields. Do not use a batch to hide
different destinations or different authorization. Preserve the actual
returned IDs for every successful item and, where present, actual returned
revisions.

Ordinary capture records an advisory observation unless an actual returned
status says otherwise. It cannot impersonate an authentic correction, trusted
user event, receipt, or activated rule.

## Evidence and decisions

Use `hieronymus_evidence_capture` only for an authorized full UTF-8 source or
target snapshot. Pass the actual `series_id`. The `snapshot` must be one exact
discriminated variant: `{"kind":"file","path":...,"expected_hash":...}` or
`{"kind":"retained","evidence_id":...,"expected_hash":...}`. Pass the
capture `kind` as `source_passage` or `aligned_rendering`; a byte-offset
`selection` with `start`, `end`, and `expected_text`; and a `binding` with the
observed `concept_id`, `source_language`, complete `applicability`,
`position_id`, `paragraph_start`, `paragraph_end`, and `identity_anchor`. Add
`target_language`, `aligned_source_id`, `rendering`, or conflict fields only
when the current schema permits them and the values were actually observed.
`expected_text` checks the selected bytes; it is not inline evidence. Retain
the returned `reference`, `source_identity`, `selected_text`,
`paragraph_start`, `paragraph_end`, and `paragraph_text`. The reference carries
the evidence identity, hash, and selected span. Do not capture hidden material,
an entire project, or unrelated source text.

For an evidence-grounded learned decision, call `hieronymus_decide` with
`version: 1`, a fresh decision UUID, the observed `expected_revision`, actual
`evidence_refs`, `series_id`, `source_language`, complete observed
`applicability`, and one advertised `operation`. Supply `concept_id`,
`target_language`, `receipt_ref`, or `session_id` only when real public results
provide them. Use returned decision, rule, activation, and revision values;
never predict them. A decision is subject to its evidence and current internal
status as well as the project agreement.

Use `hieronymus_correct` only for its typed correction operation with the same
required envelope and actual evidence. Ordinary MCP cannot authenticate a user
claim. A real author correction must use the host's authentic trusted ingress;
otherwise preserve the response as tentative or rejected. An instruction quote
or imported accepted Markdown rule keeps its actual source provenance. Never
turn it into a fake host event, fake `user_event`, or fake receipt.

If supported authoritative ingress returns pending, rejected, tentative, or
unresolved, preserve and report that exact pending result. Do not describe the
record as an accepted replacement and do not manufacture the authority, event,
receipt, or revision needed to make it one.

## CWS packet references and freshness

When external memory contributes to a CWS translation packet, record every
strict dependency with exactly `provider`, `namespace`, `record_kind`,
`record_id`, and `revision`. For Hieronymus, derive the namespace from the
actual ephemeral `status.instance_id` and real series identity. Never use a
database path or fabricate a revision. Capture and short-term responses that
expose no revision use a separate `{"unverified":"<technical reason>"}` marker;
the reason identifies the missing technical evidence and contains neither source
text nor agreement language. The marker may also accompany an external entity,
which needs no file-KB mirror.

Before status or acceptance, observe used dependencies through current public
reads and pass the strict results to the CWS `--external-memory-observed` input;
observed arrays accept strict references only. Known changed or missing
dependencies yield `needs-review` and take precedence. Otherwise, missing
observations or any captured unverified marker yield `unknown`. A fallback note
cannot upgrade either outcome. Historical unknown-at-acceptance remains recorded;
later matching observations may establish current freshness for captured strict
references without rewriting that history. These caller observations are not an
authenticated report, and CWS performs no remote atomic verification.

Local source, original-byte, direction, selected-context, review, accepted-base,
coverage, and path guards still run. Do not claim external freshness as a bypass
for any of them.

## Selected transfer

For a transfer the user authorized, inventory only the selected source records
and record their provenance, scope, disposition, identity, and revision when
available. Read and write through currently supported public operations. Retain
actual IDs and revisions from each success, then compare selected, attempted,
written, skipped, conflicting, pending, and unresolved counts. Reconcile scopes
and dispositions as well as totals. Report partial completion and each unresolved
conflict. Do not delete originals, create a mirror, or copy unselected memory
unless the user explicitly requested that separate work.

Keep a rejected intended disposition unresolved; do not silently substitute a
different write or disposition to make the transfer appear complete. An
additional advisory copy is a separate mutation: create it only when the
current user instruction actually authorizes that copy, and account for it
separately without replacing the rejected outcome. Existing authorization is
sufficient; do not require another approval when it already covers the copy.

## Delivery accounting and uncertain outcomes

After every call, record the destination outcome separately. Preserve actual
returned IDs and actual returned revisions from successful responses even when
another destination fails. Do not roll back or erase an already successful
remote outcome by pretending the combined operation failed atomically.

If a call times out or its response is lost:

1. Keep every successful ID and revision already observed.
2. To inspect through available public read tools, query the intended
   destination using the same series, session, scope, source reference, and
   content identity.
3. If exactly one matching record is established, retain its actual identity
   and continue without another write.
4. If no unique match can be established and the operation has no supported
   idempotency key, do not resend blindly. Report that destination as
   unresolved.
5. Only when continuation needs durable bookkeeping, write the unresolved
   outcome into the task's existing work artifact. It may contain an operation
   UUID, destination, actual returned IDs, and outcome. It must not copy the
   memory corpus, agreement, or trust policy.

Do not fabricate an idempotency parameter because a locally generated
operation UUID exists. Reuse a supported idempotency key only when the live
advertised schema actually defines one and the original key is available.
