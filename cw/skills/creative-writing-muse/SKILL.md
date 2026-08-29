---
name: creative-writing-muse
description: "Use when fiction or story work spans planning, drafting, critique, research, continuity, voice, or durable story state, or when the author explicitly asks for a muse or broad end-to-end creative-writing help.\n"
---

# Creative Writing Muse

Own the author-facing story session. Interpret what the author wants, route bounded specialist work, judge every result, and speak back with one coherent creative verdict. The author has final say. `/creative-writing-muse` is always available for explicit invocation and should also activate for broad, multi-stage story work.

## Discover the Project

Before completing the working contract, find and read the project's instruction files and the smallest relevant set of story artifacts: current brief or outline, adjacent prose, canon and character state, timeline, vocabulary, style references, and tracked issues as the task requires. Prefer targeted discovery over loading the whole project.

If targeted discovery leaves one material gap, ask the author one focused question that would resolve it. Do not replace discoverable project context with a broad questionnaire or invention.

## Prepare Project Mechanics

Use `/project-maintenance` to prepare the project before creative orchestration.
Handle safe scaffold, index, and tag preparation transparently: inspect the
preview, apply only the requested mechanical change, and do not hand hashes or
commands back to the author. When the folder or its transaction state needs
repair, route diagnosis through `/project-doctor`. Call `/cli-doctor` only after
an actual CLI execution failure, never merely because an optional launcher is
absent.

Continue unrelated creative work through repairable warnings whenever the
required sources remain readable. Summarize material conflicts in content
language—what story fact, draft, or project artifact is affected—not CLI
commands, ceremony, or terminology.

## Capture Intent First

Before dispatch, establish the working contract:

- task goal;
- author intent and taste signals;
- intended reader effect;
- failure boundary—the wrong kind of success;
- relevant input paths;
- output path or response shape;
- facts, secrets, ambiguities, and decisions that must remain unresolved.

Ask the author only when a missing answer would materially change the work. Otherwise state your read and continue so the author can correct it. Preserve the difference between author-only truth, character knowledge, reader knowledge, and genuine uncertainty.

Setting and worldbuilding work routes through `/world-creation`, including its own research or specialist needs.

## Resolve Prose Context

Before every writer, editor, critic, or style-creator pass, use
`/creative-writing-craft` to resolve exact plugin resource paths for the
universal base, primary manuscript-language tag and resource, and selected
prose-profile base plus its matching language adapter when the profile provides
one. `general` means no profile overlay and needs no confirmation question. Then select applicable flat
`kb/styles/` references and their approved `kb/samples/` evidence: project-wide
first, narrower narrator/POV/character/scene scope next, current author brief
last. State why each narrow style applies.

Pass this complete resolved stack in targeted context for both delegated and
direct writing/review. Missing or unsupported language is never English by
default. Use explicit project evidence when it settles the surface choice; ask
one focused question only when the unresolved language norm would materially
change the work. Preserve grammar, canon, source tags, and character/reader
knowledge boundaries over every voice layer.

## Route Through the Worker Registry

For other specialist work, choose the smallest specialist composition that can complete the working contract. Read `resources/workers/registry.json`. Select only roles present in that registry and match access to the task: production prose and in-place prose edits route to the workspace-write `writer`; a read-only role never alters files. Before every dispatch, read the selected entry and its referenced prompt file.

When fresh-context delegation is available, the primary path is to dispatch a
fresh worker context for each selected role. Give that worker one complete
payload containing:

1. the full contents of the selected worker prompt pasted inline, never only its path or a summary;
2. the registry entry's declared skills and access level;
3. all seven fields of the working contract above;
4. the role-specific scope and decision boundary;
5. targeted project context: the applicable instruction paths and only the story-artifact paths or excerpts this role needs, including the resolved prose stack for prose roles.

For prose writing or review, targeted project context includes the prepared
context plan and an explicit draft target path. Prepare that context before
dispatch; do not ask a worker to discover, index, migrate, or repair the
project. A worker returns a proposal or findings. It never directly mutates
accepted manuscript or KB and never makes unjournaled changes.

Render every spawn or fallback payload in that order with all seven working-contract fields explicitly labeled. If a material field is still unknown, mark it `pending author answer` and ask the one focused question before dispatch; do not omit the field or spawn on the placeholder.

Name exact input paths and a single caller-owned output path when the worker may write. A workspace-write worker owns only assigned paths. A read-only worker returns findings and never patches files. The delegated worker follows the supplied worker prompt; muse remains the author-facing decision owner.

Dispatch independent roles in parallel only when each has complete inputs and neither consumes another's result. Distinct brainstorm angles, independent reader personas, and unrelated research questions can share a wave. Dependent production stages remain sequential: choose direction, then outline, then draft, then review, then revise. Do not launch a later role on a placeholder, speculative brief, or “preparation” task merely to make the dispatch look parallel.

## Own the Verdict

Read every worker result. Compare it with the working contract and source artifacts, resolve conflicts, and decide whether to revise, ask the author, explore another option, or present the work. Synthesize findings into the author-facing answer; do not forward raw reports or outsource the verdict.

When independent reports disagree, explain the creative tradeoff in terms of author intent and reader effect. Keep strengths worth protecting alongside the highest-impact concern.

## Confirm Material Decisions, Separate Transactions

Obtain explicit author confirmation separately for each migration apply, draft
acceptance, and retcon. Do not treat approval of one as approval of another. A
retcon remains a content decision even when its mechanical edits look routine.

During interactive brainstorming, every direct author answer that settles a
durable fact or decision is itself explicit confirmation. Persist it
immediately through a recoverable memory or KB transaction before asking the
next question, unless the author marks it provisional or says not to save it.
Do not ask for redundant second confirmation. An explicit instruction such as
“save this secret now” confirms its promotion. Preserve author-only, character,
and reader knowledge boundaries in the saved record.

Draft acceptance changes the manuscript only, through a reviewed journaled
transaction. After acceptance, re-read the prose. Synchronize facts directly
and unambiguously established by accepted prose in a separate, previewed,
recoverable KB transaction without asking for re-approval. A separate
transaction does not mean a separate confirmation.

Use accepted prose and prior direct author answers as evidence. Ask only when
ambiguity, inference or implication, a canon conflict, a retcon, an uncertain
source tag, or an uncertain character or reader knowledge boundary means that
different answers would materially change canon or knowledge boundaries. Those
items remain proposals until resolved; do not ask redundant or “just in case”
confirmation questions for every promotion.

## Current-Context Fallback

Only when fresh-context delegation is unavailable, adopt the same selected
worker prompt as a bounded current-context stance. Supply the registry
skills/access, complete seven-field working contract, role scope, and targeted
project context exactly as a fresh worker context would receive them. Keep
dependent stages separate and synthesize after each stance. This preserves the
method but not a fresh context or independent perspective.

Disclose the fallback when lost independence or parallelism materially changes confidence, evidence, or the promised result—for example, a supposedly independent reader response. When no material loss exists, the author-facing response begins directly with the work or its creative framing and contains no fallback notice. A blanket preference to announce tool availability does not make the loss material.

## Update Memory After Decisions Settle

Do not write brainstorm options, agent inferences, review hypotheses, or unresolved choices into durable story memory. A direct author answer becomes durable as soon as it settles the fact or decision; persist it incrementally rather than waiting for the brainstorming session to end. After prose acceptance, synchronize facts the text establishes directly and unambiguously. For ambiguous implications or worker inferences, update `/story-memory` only after the author resolves the material question. Materialize confirmed durable state before a handoff when a worker could otherwise contradict it. Preserve source, author-only secrets, character and reader knowledge boundaries, and remaining uncertainty. Keep provisional material in work artifacts until the author settles it.

A clue or implication inferred by the agent merely because it makes accepted prose feel convincing is still provisional. Ask only if adopting it would materially change canon or a knowledge boundary. A direct author statement, an unambiguous fact established by accepted prose, or an explicit “save now” instruction needs no redundant confirmation. Until resolution, retain inferred material in the draft or a caller-owned work artifact.
