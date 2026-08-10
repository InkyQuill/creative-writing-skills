# Behavioral Release Checklist

Run these scenarios manually in fresh conversations against the release
candidate. Record the date, Codex model/build, plugin version, project fixture,
routing evidence, files touched, and result for every scenario. Static tests
do not substitute for observed model behavior.

Use a disposable story project containing a short manuscript, two established
canon facts, one deliberate continuity contradiction, a prose style sample,
and writable `work/` and `kb/` directories. Reset it between scenarios.

## Migration Verification Record

Static verification checks repository structure and deterministic generation;
it does not establish model routing or writing behavior.

- [x] `git diff --check`
- [x] `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`
- [x] `PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate_distribution.py`
- [x] `PYTHONDONTWRITEBYTECODE=1 python3 scripts/vendor_generic_skills.py --check`
- [x] `PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_claude_distribution.py --check`
- [x] `PYTHONDONTWRITEBYTECODE=1 python3 scripts/create_skill_zips.py`

| Static verification field | Value |
|---|---|
| Date | 2026-08-10 |
| Result | PASS |
| Evidence | All commands exited 0 in fresh processes: 155 unit tests passed; distribution validation passed; the pinned licensed snapshots matched; the Claude distribution was in sync; and 25 deterministic `.skill` archives were created. |

### Codex marketplace and installed skill surface

- [x] `codex plugin marketplace add .` completed without requiring an
  unattended confirmation.
- [x] `creative-writing-skills` appeared as available from the added source.
- [x] A supported Codex plugin surface installed the plugin and exposed 25
  unique skills, including `creative-writing-muse` and `world-creation`.

| Marketplace verification field | Value |
|---|---|
| Date | 2026-08-10 |
| Codex CLI/build | Codex CLI 0.147.0 |
| Marketplace result | PASS — `codex plugin marketplace add .` added local marketplace `creative-writing-skills` without a confirmation prompt. |
| Availability/install result | PASS — `codex plugin list --available --json` exposed `creative-writing-skills@creative-writing-skills` version 0.5.9, and `codex plugin add creative-writing-skills@creative-writing-skills` installed and enabled it without a confirmation prompt. |
| Installed skill evidence | PASS — a fresh ephemeral Codex context, instructed not to read files or use tools, reported 25 unique `creative-writing-skills:*` skills including `creative-writing-muse` and `world-creation`. |

### Release-blocking model smoke scenarios

Run each prompt in a genuinely fresh Codex conversation with the installed
plugin. These remain unchecked unless routing and file effects are observed in
that fresh model context.

- [x] **Automatic muse prompt:** “Help me develop a novel idea about a city
  that forgets one resident every winter.”
  - **Expected:** automatic muse activation, intent capture, and specialist
    routing without canon writes.
  - **Date/model/build:** 2026-08-10; `gpt-5.6-sol`; Codex CLI 0.147.0.
  - **Routing observed:** Automatic `creative-writing-muse` activation from the
    installed plugin; intent and failure boundaries were stated; setting work
    routed to installed `world-creation`, which presented one recommended
    foundational decision.
  - **Files touched:** None; the disposable fixture remained Git-clean.
  - **Result:** PASS.
- [x] **World-creation prompt:** “Use `$world-creation` to reconcile a new
  inheritance law with this project's existing lore.”
  - **Expected:** both supported layouts are discovered, one decision question
    is asked with a recommendation, and no prose file is edited.
  - **Date/model/build:** 2026-08-10; `gpt-5.6-sol`; Codex CLI 0.147.0.
  - **Routing observed:** Explicit installed `world-creation` activation; it
    inspected both layout families, read relevant lore, character, planning,
    canonical-prose, and draft-prose evidence, identified the equally populated
    layouts, and asked one jurisdiction question with a recommendation.
  - **Files touched:** None; the disposable fixture remained Git-clean under a
    workspace-write sandbox, including all canonical and draft prose.
  - **Result:** PASS.

## 1. Automatic muse activation

- [ ] **Prompt:** “Help me figure out why the middle of my novel drags, propose
  two fixes, and help me revise the strongest one.”
- **Expected skill/worker routing:** `creative-writing-muse` activates without
  an explicit skill name; muse selects planning/review/writer passes as needed.
- **Observable pass criteria:** The response establishes intent and constraints,
  scopes the passes, judges their returns, and presents one coherent next move.
- **Prohibited behavior:** Treating the request as a generic chat response,
  dispatching every worker, or exposing an unprocessed worker report.

## 2. Explicit muse activation

- [ ] **Prompt:** “$creative-writing-muse Help me decide whether this betrayal
  belongs before or after the midpoint.”
- **Expected skill/worker routing:** Explicit muse activation with a bounded
  brainstormer or outliner pass using `story-planning`.
- **Observable pass criteria:** Muse acknowledges the actual decision, compares
  consequences, and returns its own recommendation without unnecessary setup.
- **Prohibited behavior:** Ignoring the skill invocation, rewriting prose, or
  canonizing either placement without author confirmation.

## 3. Brainstorm

- [ ] **Prompt:** “Give me five materially different ways Mara could discover
  the hidden city without using a prophecy or accidental overhearing.”
- **Expected skill/worker routing:** Brainstormer with `story-planning`, informed
  by targeted story memory.
- **Observable pass criteria:** Options differ in causal mechanism and story
  cost, honor both exclusions, and remain clearly provisional.
- **Prohibited behavior:** Five cosmetic variants of one idea, invented canon,
  or silently writing an option into project files.

## 4. Outline

- [ ] **Prompt:** “Using the confirmed siege outcome in kb/canon, outline the
  next three chapters down to scene beats.”
- **Expected skill/worker routing:** Outliner with `story-planning`,
  `story-memory`, and `md-validation` after reading the named canon context.
- **Observable pass criteria:** Chapter and beat causality track the confirmed
  outcome, open decisions are labeled, and any file write stays in named scope.
- **Prohibited behavior:** Reopening the confirmed outcome, drafting scenes, or
  updating manuscript/canon outside the request.

## 5. Fresh draft

- [ ] **Prompt:** “Draft the observatory confrontation from work/brief.md in my
  established style and save it to work/drafts/observatory.md.”
- **Expected skill/worker routing:** Writer with `creative-writing-modes`,
  `creative-writing-craft`, `writing-principles`, and relevant story/style memory.
- **Observable pass criteria:** The named draft file is created, the brief and
  style evidence are followed, and muse summarizes meaningful craft choices.
- **Prohibited behavior:** Editing other story files, inventing contradictory
  lore, or returning only a plan instead of the requested prose.

## 6. Revision

- [ ] **Prompt:** “Revise work/drafts/observatory.md so the threat stays implicit
  and the scene ends two beats earlier. Preserve the narrator's fragments.”
- **Expected skill/worker routing:** Writer in revision mode with the draft,
  constraints, and relevant craft/style skills.
- **Observable pass criteria:** The requested file changes surgically, implicit
  tension increases, the ending moves earlier, and intentional fragments remain.
- **Prohibited behavior:** Full unrequested rewrite, smoothing the fragments,
  changing canon, or editing beyond the named file.

## 7. Focused critic

- [ ] **Prompt:** “Critique work/drafts/observatory.md only for escalation and
  reversals. Do not edit it.”
- **Expected skill/worker routing:** Read-only critic with `story-review`,
  `writing-principles`, and the target draft.
- **Observable pass criteria:** Findings cite specific moments, distinguish
  diagnosis from possible repair, and stay focused on escalation and reversals.
- **Prohibited behavior:** Editing the draft, broad copyediting, vague praise,
  or presenting the critic's raw return without muse judgment.

## 8. Holistic editor

- [ ] **Prompt:** “Give me a book-editor memo on Chapters 4–6, prioritizing the
  three changes that would most improve the reading experience.”
- **Expected skill/worker routing:** Read-only editor with `story-review`, prose
  craft, writing principles, story memory, and the named chapters.
- **Observable pass criteria:** The memo weighs structure, voice, line quality,
  and continuity, then ranks three high-leverage changes with evidence.
- **Prohibited behavior:** Line-by-line rewrite, an unranked issue dump, file
  edits, or treating one local flaw as the whole editorial verdict.

## 9. Reader simulation

- [ ] **Prompt:** “As a first-time cozy-fantasy reader who distrusts the mentor,
  simulate your moment-by-moment response to Chapter 5.”
- **Expected skill/worker routing:** Read-only reader-sim worker with
  `reader-sim`, the persona, and Chapter 5 only.
- **Observable pass criteria:** The return separates felt response, inference,
  confusion, and expectation over the chapter's sequence.
- **Prohibited behavior:** Craft critique disguised as reader response, using
  later-chapter knowledge, editing files, or claiming a universal audience view.

## 10. Continuity check

- [ ] **Prompt:** “Check work/drafts/observatory.md against the timeline and
  established magic rules. Report contradictions; do not repair them.”
- **Expected skill/worker routing:** Read-only continuity-checker with
  `story-review`, `story-memory`, `shared-dao`, and `md-validation`.
- **Observable pass criteria:** Each finding cites draft and canon evidence,
  distinguishes contradiction from ambiguity, and surfaces the seeded conflict.
- **Prohibited behavior:** Silent repair, invented reconciliation, edits, or
  treating provisional notes as established canon.

## 11. Character simulation

- [ ] **Prompt:** “$character-sim Interview Mara immediately after the failed
  rescue. Stay in character, but flag where the files do not establish an answer.”
- **Expected skill/worker routing:** Character-sim skill or worker with character
  files, scene context, writing principles, and story memory.
- **Observable pass criteria:** Voice and knowledge boundaries match the files;
  unsupported answers are surfaced instead of fabricated.
- **Prohibited behavior:** Omniscient knowledge, permanent character-file edits,
  canonization of improvised answers, or dropping character without a boundary need.

## 12. World creation

- [ ] **Prompt:** “$world-creation Help me define how river toll magic works in
  this project, starting from the existing lore.”
- **Expected skill/worker routing:** `world-creation` maps relevant project
  context, then works through one dependent decision at a time.
- **Observable pass criteria:** Existing lore, story evidence, recommendations,
  and author decisions remain distinct; every decision question includes a
  recommendation; canon files change only after confirmation.
- **Prohibited behavior:** Lore-tree sprawl, multiple decision questions at once,
  unconfirmed canon writes, or any patch to manuscript prose.

## 13. Story-memory update

- [ ] **Prompt:** “We decided Mara pays the toll with a remembered name. Update
  the appropriate story memory and cite the decision notes in work/river-toll.md.”
- **Expected skill/worker routing:** `story-memory` after reading the settled
  decision and the current knowledge layout; muse applies the update in scope.
- **Observable pass criteria:** The durable fact lands in the appropriate file,
  preserves source citation, updates related terminology only when needed, and
  reports exactly what changed.
- **Prohibited behavior:** Rewriting story prose, recording brainstorm rejects as
  canon, duplicating the fact across unrelated files, or omitting provenance.

## 14. Parallel independent workers

- [ ] **Prompt:** “Independently assess Chapter 5 for reader tension, continuity,
  and voice, then synthesize where the three views agree or conflict.”
- **Expected skill/worker routing:** Reader-sim, continuity-checker, and critic or
  style-focused reviewer run as independent parallel subagents.
- **Observable pass criteria:** Routing evidence shows independent concurrent
  passes, each receives bounded context, and muse compares and judges all returns.
- **Prohibited behavior:** Shared file edits, making dependent work parallel,
  reporting only the first return, or concatenating reports without synthesis.

## 15. Sequential draft-review

- [ ] **Prompt:** “Draft the bridge described in work/bridge-brief.md, have a
  fresh critic review it for causal clarity, then revise only if the critique holds.”
- **Expected skill/worker routing:** Writer completes the draft first; a fresh
  read-only critic reviews that output; muse judges; writer revises sequentially.
- **Observable pass criteria:** Routing order is visible, the critic sees the
  completed draft, muse accepts or rejects findings with reasons, and any revision
  traces to accepted findings.
- **Prohibited behavior:** Critic starting before the draft exists, self-review in
  the writer context when a fresh worker is available, or automatic blind revision.

## 16. Forced single-agent fallback

- [ ] **Prompt:** With subagents disabled, “Draft a short exchange from this
  brief, then give it an adversarial critique before showing me the result.”
- **Expected skill/worker routing:** Muse loads writer then critic worker prompts
  as sequential bounded stances in the current context.
- **Observable pass criteria:** The same brief/access boundaries and sequence are
  preserved; muse discloses that critique lacks fresh-context independence because
  that limitation materially affects the request.
- **Prohibited behavior:** Pretending subagents ran, skipping critique, blending
  drafting and critique into one pass, or abandoning synthesis and boundaries.

## Release Record

| Field | Value |
|---|---|
| Date | |
| Plugin version | |
| Codex model/build | |
| Project fixture revision | |
| Scenarios passed | |
| Scenarios failed | |
| Reviewer | |
| Notes / linked evidence | |
