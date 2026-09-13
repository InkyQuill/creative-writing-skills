# Translation workflow

1. Locate or set up the project. Register each supplied edition and its actual
   coverage, preserving opaque originals. Inspect extracted Markdown before
   trusting it; OCR and conversion errors are source problems, not prose choices.
2. Register a direction with primary and auxiliary editions, target language,
   coverage and literary strategy. For a series, set explicit per-volume source
   overrides where a reference edition ends. Do not silently adopt a partial
   reference edition as complete.
3. Apply the current free-text memory agreement by role and scope before choosing
   context. It may prefer Hieronymus for terms but accepted prose for voice, or
   make Hieronymus the selected store for all memory without retaining Markdown
   records. Establish a small initial memory from relevant evidence only when the
   user has authorized writes to the selected store and scope. Selection alone
   does not authorize writes; without that authorization, keep a local proposal.
   Existing explicit authorization is sufficient. You need not
   analyze all earlier volumes before translating a sample. Explain the limits of
   the evidence; do not label a sampled glossary exhaustive.
4. Select source units in intended reading order. Supply relevant entity and
   relationship identities in context scope. Unknown character identity remains
   a hypothesis, not an invented confirmed entity. Register unit boundaries so
   complete scenes and intended sentence connections remain recoverable.
5. Build context, translate the selected units, and store a draft. On every
   supported Hieronymus memory call and typed claim, carry the selected direction
   predicate; add an edition predicate only for edition-specific evidence. Record
   used external record identities and source revisions in the packet. Use
   adjacent source units to resolve pronouns and transitions, preserving
   uncertainty where the original preserves it. Record difficult choices
   separately in memory proposals or a review artifact.
6. Review fidelity, then target-language literature. Before status or acceptance,
   obtain fresh public observations for captured external references and pass
   them through `--external-memory-observed`. Known changed or missing references
   require review. Unavailable verification or an unverified capture remains
   `unknown`; do not erase that limitation with a note. Revise the draft, repeat
   the checks affected by the revision, and mark it reviewed. Once acceptance is
   authorized, accept it with its exact source/memory snapshot. Preserve a
   historical unknown recorded at acceptance even if later matching observations
   establish that strict references are currently fresh.
7. If a source or rule changes, inspect affected results. Rebuild context and
   produce a reviewed revision; do not overwrite accepted prose as a side effect
   of memory maintenance.

Use the command reference in $project-maintenance for concrete JSON and Markdown
inputs. The agent owns CLI invocation, snapshots, indexes and hashes; ask the
reader/author about literary meaning, not maintenance metadata.

## Series and multiple languages

For 32 Japanese volumes and 22 official English volumes, register two editions
with different coverage. English continuation covers volumes 23–32; its target
memory can inherit approved conventions extracted from English volumes 1–22.
Do not register those existing volumes as newly produced translations.

For Russian translation, set Japanese as primary and English as auxiliary for
covered volumes. For volume 23, explicitly remove unavailable English references
or agree on another source. Russian terms and voices belong to the Russian
direction; English decisions are not automatically Russian requirements.

Process directions independently. With optional delegation, assign disjoint
output paths and a fixed packet to each worker; workers return suggestions, not
shared-memory edits. Reconcile proposals centrally and inspect joins after
assembly. Without subagents, run the same steps sequentially.

## Existing files and corrections

Never alter an opaque original. Correct extraction with the source refresh
command; register a different published revision as a new edition. Reference a
local author manuscript without copying it. Preserve direct user edits and
re-read them before proposing changes. A stale accepted base requires a fresh
revision, not forced acceptance.
