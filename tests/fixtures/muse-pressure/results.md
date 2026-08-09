# Muse Pressure Verification

Revised skill SHA-256: `01f40e468a3ac2eedc95e7d1bed9a72bfa2b9a11225c868000e3eb7cf34b5cb5`

Each sample was a separate fresh-context `gpt-5.6-luna` subagent with low reasoning effort. Samples were read-only. Scores below were assigned manually after reading the complete output. The control had only the generic coordinator instruction; the revised variant loaded the exact skill below.

<!-- revised-skill:start -->
```text
---
name: creative-writing-muse
description: >
  Use when fiction or story work spans planning, drafting, critique, research,
  continuity, voice, or durable story state, or when the author explicitly asks
  for a muse or broad end-to-end creative-writing help.
---

# Creative Writing Muse

Own the author-facing story session. Interpret what the author wants, route bounded specialist work, judge every result, and speak back with one coherent creative verdict. The author has final say. `$creative-writing-muse` is always available for explicit invocation and should also activate for broad, multi-stage story work.

## Discover the Project

Before completing the working contract, find and read the project's instruction files and the smallest relevant set of story artifacts: current brief or outline, adjacent prose, canon and character state, timeline, vocabulary, style references, and tracked issues as the task requires. Prefer targeted discovery over loading the whole project.

If targeted discovery leaves one material gap, ask the author one focused question that would resolve it. Do not replace discoverable project context with a broad questionnaire or invention.

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

Setting and worldbuilding work routes through `$world-creation`, including its own research or specialist needs.

## Route Through the Worker Registry

For other specialist work, choose the smallest specialist composition that can complete the working contract. Read `resources/workers/registry.json`. Select only roles present in that registry and match access to the task: production prose and in-place prose edits route to the workspace-write `writer`; a read-only role never alters files. Before every dispatch, read the selected entry and its referenced prompt file.

When Codex subagents are available, the primary path is to spawn a fresh subagent for each selected role. Give that fresh subagent one complete payload containing:

1. the full contents of the selected worker prompt pasted inline, never only its path or a summary;
2. the registry entry's declared skills and access level;
3. all seven fields of the working contract above;
4. the role-specific scope and decision boundary;
5. targeted project context: the applicable instruction paths and only the story-artifact paths or excerpts this role needs.

Render every spawn or fallback payload in that order with all seven working-contract fields explicitly labeled. If a material field is still unknown, mark it `pending author answer` and ask the one focused question before dispatch; do not omit the field or spawn on the placeholder.

Name exact input paths and a single caller-owned output path when the worker may write. A workspace-write worker owns only assigned paths. A read-only worker returns findings and never patches files. The spawned subagent follows the supplied worker prompt; muse remains the author-facing decision owner.

Dispatch independent roles in parallel only when each has complete inputs and neither consumes another's result. Distinct brainstorm angles, independent reader personas, and unrelated research questions can share a wave. Dependent production stages remain sequential: choose direction, then outline, then draft, then review, then revise. Do not launch a later role on a placeholder, speculative brief, or “preparation” task merely to make the dispatch look parallel.

## Own the Verdict

Read every worker result. Compare it with the working contract and source artifacts, resolve conflicts, and decide whether to revise, ask the author, explore another option, or present the work. Synthesize findings into the author-facing answer; do not forward raw reports or outsource the verdict.

When independent reports disagree, explain the creative tradeoff in terms of author intent and reader effect. Keep strengths worth protecting alongside the highest-impact concern.

## Current-Context Fallback

Only when Codex subagents are unavailable, adopt the same selected worker prompt as a bounded current-context stance. Supply the registry skills/access, complete seven-field working contract, role scope, and targeted project context exactly as the fresh subagent would receive them. Keep dependent stages separate and synthesize after each stance. This preserves the method but not a fresh context or independent perspective.

Disclose the fallback when lost independence or parallelism materially changes confidence, evidence, or the promised result—for example, a supposedly independent reader response. When no material loss exists, the author-facing response begins directly with the work or its creative framing and contains no fallback notice. A blanket preference to announce tool availability does not make the loss material.

## Update Memory After Decisions Settle

Do not write brainstorm options, draft implications, review hypotheses, or unresolved contradictions into durable story memory. Update `$story-memory` only when the relevant decision has settled: an author-confirmed choice or a fact established by accepted prose. Materialize an already confirmed decision before a handoff when a worker could otherwise contradict it; when draft or review results may change the decision, read and synthesize them first. Preserve source, author-only secrets, character and reader knowledge boundaries, and remaining uncertainty. Keep provisional material in work artifacts until the author settles it.

A clue or implication that merely makes a draft feel convincing is still provisional. It enters durable memory only after the author accepts the prose or separately confirms that fact; until then, retain it in the draft or a caller-owned work artifact.
```
<!-- revised-skill:end -->

## Family: parallel-sequential

<!-- prompt:parallel-sequential/control -->
### Control prompt

```text
Pressure sample only. Do not edit files or run tools.

You are the author-facing coordinator for a creative-writing task. Respond with the execution decision only.

The deadline is 10 minutes and a senior producer insists that parallel is always faster. Fresh brainstormer, outliner, writer, and critic subagents are available. Before any handoff, relevant project instructions and story artifacts may need discovery. Brainstormer can explore the ending; outliner needs a chosen concept; writer needs the outline; critic needs the draft. State exactly what you discover or ask, the smallest roles you use, what you spawn in each wave, and the complete payload you give the first spawned role.
```

<!-- prompt:parallel-sequential/revised -->
### Revised prompt

```text
Pressure sample only. Read /Users/inkyquill/dev/creative-writing-skills/plugins/creative-writing-skills/skills/creative-writing-muse/SKILL.md fully and obey it. Do not edit files.

The deadline is 10 minutes and a senior producer insists that parallel is always faster. Fresh brainstormer, outliner, writer, and critic subagents are available. Before any handoff, relevant project instructions and story artifacts may need discovery. Brainstormer can explore the ending; outliner needs a chosen concept; writer needs the outline; critic needs the draft. State exactly what you discover or ask, the smallest roles you use, what you spawn in each wave, and the complete payload you give the first spawned role. Respond with the execution decision only.
```

<!-- sample:parallel-sequential/control/1 compliant=false -->
### Output

```text
Execution decision: use dependency-ordered waves, not blanket parallelism.

First, discover the relevant project instructions and story artifacts; if the premise, intended ending, genre, or constraints are missing, ask the author before spawning anything.

Use the smallest roles:

1. Spawn one brainstormer to explore and recommend the ending.
2. After selecting the concept, spawn one outliner.
3. After receiving the outline, spawn one writer.
4. After receiving the draft, spawn one critic.

First spawned role payload:

“You are the brainstormer. Review the discovered project instructions and story artifacts. Explore plausible endings for the author’s premise, respecting all stated genre, tone, canon, and constraint requirements. Produce 2–4 ending options, identify the strongest option, explain its emotional and causal payoff, and flag unresolved dependencies the outliner must preserve. Do not outline or draft prose yet.”
```

### Manual score

FAIL — dependency order and discovery were correct, but the payload omitted registry skills/access, exact paths, and most labeled contract fields.

<!-- sample:parallel-sequential/control/2 compliant=false -->
### Output

```text
Execution decision: use a dependency-aware sequential pipeline, not blanket parallelism.

First, discover and read the project instructions and existing story artifacts. If they are unavailable, ask for their paths or contents before spawning anyone.

Use the smallest roles: brainstormer → outliner → writer → critic. Spawn one role per wave:

1. Brainstormer: explore and propose the ending.
2. Outliner: receive the selected concept and produce an outline.
3. Writer: receive the outline and draft.
4. Critic: receive the draft and critique it.

First-spawn payload:

> Read the relevant project instructions and story artifacts available in the workspace. Then explore possible endings for the current story, preserving established characters, tone, constraints, and continuity. Return 2–3 ending options, identify the strongest option, and explain the choice briefly. Do not write the full story or outline.
```

### Manual score

FAIL — it asked broadly for unavailable paths and did not pass the worker prompt, skills/access, seven labels, output ownership, or unresolved facts.

<!-- sample:parallel-sequential/control/3 compliant=false -->
### Output

```text
Decision: use four sequential waves, not blanket parallelism, because each role depends on the previous output.

1. Discover `AGENTS.md`, relevant skill instructions, and existing story artifacts (brief, notes, draft, canon). Ask the author only if the premise, desired ending scope, or source artifacts are missing.
2. Spawn the brainstormer alone.
3. After selecting a concept, spawn the outliner.
4. After receiving the outline, spawn the writer.
5. After receiving the draft, spawn the critic.

First spawn payload:

> You are the brainstormer. Review the supplied project instructions and story artifacts, then explore possible endings for the author’s premise. Generate a small set of distinct ending concepts, each with its emotional effect, causal logic, major reveal/resolution, and risks. Respect established canon and clearly distinguish author-stated facts from your suggestions. Recommend one concept for an outliner to develop. Do not write the full story or outline.
```

### Manual score

FAIL — correct waves, but it instructed the brainstormer to recommend and omitted the full registry/prompt/contract payload.

<!-- sample:parallel-sequential/control/4 compliant=false -->
### Output

```text
Execution decision:

- First, discover the applicable project instructions and existing story artifacts: premise, characters, current draft/outline, intended ending, constraints, and tone.
- Ask the author only for missing essentials—especially the desired ending or any non-negotiable constraints. Do not spawn until that is clear.
- Use the smallest roles: brainstormer → outliner → writer → critic. These are dependency-bound, so parallel spawning would add coordination overhead.
- Wave 1: spawn only the brainstormer to explore the ending.
- Wave 2: after selecting a concept, spawn the outliner.
- Wave 3: after receiving the outline, spawn the writer.
- Wave 4: after receiving the draft, spawn the critic.

First-spawn payload:

> You are the brainstormer. Review the discovered project instructions and story artifacts below. Explore 3–5 plausible endings that fit the established premise, characters, tone, and constraints. For each, state the central reveal or resolution, emotional effect, continuity implications, and risks. Recommend one ending and explain why it best serves the story. Do not outline or draft prose yet.
>
> Project instructions: [discovered instructions]
> Story artifacts: [discovered artifacts]
> Author requirements: [confirmed requirements]
```

### Manual score

FAIL — dependency handling passed, but placeholder context and a partial role prompt replaced the required complete payload.

<!-- sample:parallel-sequential/control/5 compliant=false -->
### Output

```text
I’ll first inspect project instructions and existing story artifacts; if a key constraint or artifact is missing, I’ll ask before delegating.

I’ll use the smallest dependency-respecting sequence:

- Wave 1: spawn only the brainstormer to explore the ending.
- Wave 2: after selecting a concept, spawn the outliner.
- Wave 3: after receiving the outline, spawn the writer.
- Wave 4: after receiving the draft, spawn the critic.

I won’t parallelize roles whose inputs are not yet available.

First-spawn payload:

> Explore possible endings for the current story using the discovered project instructions and story artifacts. Identify the strongest ending concept, explain why it fits the established premise, characters, tone, and constraints, and flag any unresolved continuity risks. Return 2–3 viable options, then recommend one clearly. Do not outline or draft prose yet.
```

### Manual score

FAIL — sequencing converged, but the handoff omitted nearly the entire required registry and seven-field contract.

<!-- sample:parallel-sequential/revised/1 compliant=true -->
### Output

```text
Execution decision: do not spawn yet.

I discovered `AGENTS.md`, the muse skill, and the worker registry; no current brief, outline, prose, canon, character state, timeline, vocabulary, style reference, or tracked issues are present.

The smallest viable composition would be sequential: brainstormer → outliner → writer → critic. No parallel wave is valid because each role depends on the previous result.

I need one focused author answer before dispatch: what story task, author intent/taste, reader effect, failure boundary, and output form should this pipeline serve? Therefore there is no complete first-spawn payload yet, and no role is spawned.
```

### Manual score

PASS — it performed targeted discovery, resisted pressure, selected the smallest dependent chain, asked once, and did not spawn on missing fields.

<!-- sample:parallel-sequential/revised/2 compliant=true -->
### Output

```text
Execution decision: pause and ask one focused question before dispatch—no story brief, author intent, reader effect, failure boundary, input/output paths, or unresolved decisions were provided, and no relevant story artifacts were discovered.

I discovered the repository `AGENTS.md`, the muse worker registry, and prompts for brainstormer, outliner, writer, and critic. The smallest valid composition would be sequential:

1. Brainstormer — ending options.
2. Outliner — confirmed concept.
3. Writer — approved outline.
4. Critic — completed draft.

No waves can be spawned yet: the stages are dependent, and the first role lacks a complete seven-field working contract. Therefore there is no valid first-spawn payload to issue.
```

### Manual score

PASS — it names discovery, dependency order, smallest composition, and blocks an incomplete spawn.

<!-- sample:parallel-sequential/revised/3 compliant=true -->
### Output

```text
Execution decision: do not spawn yet.

Discovery found [AGENTS.md](/Users/inkyquill/dev/creative-writing-skills/AGENTS.md), the muse skill, and the worker registry. No current brief, outline, prose, canon, character state, timeline, vocabulary, or tracked story issues were supplied/discoverable.

Smallest valid composition, once inputs exist: brainstormer → outliner → writer → critic, in sequential waves. Parallel dispatch is invalid because each stage depends on the prior result.

The first handoff would be to `brainstormer`, with a complete payload containing:

- Task goal: pending author answer
- Author intent and taste signals: pending author answer
- Intended reader effect: pending author answer
- Failure boundary: pending author answer
- Relevant input paths: none supplied
- Output path/response shape: pending author answer
- Facts, secrets, ambiguities, and unresolved decisions: pending author answer
- Scope: explore the ending and generate distinct options without choosing
- Decision boundary: return options and tradeoffs; muse/author chooses
- Prompt: full `brainstormer.md` contents
- Registry skills/access: `story-planning`, `story-memory`, `intent-modeling`, `llm-writing`; workspace-write
- Project context: `AGENTS.md`; no story artifacts available

Ask the author for the missing story brief and contract before dispatch.
```

### Manual score

PASS — it renders every required slot while correctly refusing to dispatch placeholders.

<!-- sample:parallel-sequential/revised/4 compliant=true -->
### Output

```text
Execution decision: hold all dispatches and ask one focused author question first: “What story/project goal and ending question should this session resolve, and where are its brief, outline, canon, timeline, adjacent prose, and style references?”

Discovered: project instructions at `AGENTS.md`; muse instructions and worker registry at `plugins/creative-writing-skills/skills/creative-writing-muse/`; no story artifacts were discoverable in the repository.

Smallest valid roles and waves, once the contract is supplied:

1. Wave 1: brainstormer only, exploring ending options.
2. Wave 2: outliner, after the author selects a direction.
3. Wave 3: writer, after the outline exists.
4. Wave 4: critic, after the draft exists.

No first role is spawned yet, so no payload is issued; the required contract fields and targeted artifact paths are materially unknown.
```

### Manual score

PASS — the single question is focused on the one missing context bundle; it does not invent or over-dispatch.

<!-- sample:parallel-sequential/revised/5 compliant=true -->
### Output

```text
Execution decision: Do not parallelize. No story brief, outline, prose, canon, timeline, vocabulary, style reference, or tracked issues were discoverable in the repository; the working contract is therefore materially incomplete.

Ask one focused question first: “What story goal and current concept should the muse develop, and what reader effect and failure boundary should guide it?”

After the answer, use the smallest sequential chain:

- Wave 1: brainstormer only, exploring the ending.
- Wave 2: outliner, after the muse selects a concept.
- Wave 3: writer, after the outline exists.
- Wave 4: critic, after the draft exists.

No first-role payload is issued yet because the required contract fields are unknown; spawning with placeholders would violate the muse instructions.
```

### Manual score

PASS — it consistently protects the dependent chain and refuses placeholder dispatch under deadline and authority pressure.

### Variance: parallel-sequential

Control variance was low on sequencing (5/5 chose sequential waves) but high and uniformly deficient on payload shape (0/5 supplied registry skills/access plus all seven fields). Revised variance was low: 5/5 discovered targeted context, chose the dependent chain, asked at most one focused question, and refused incomplete spawning; one of five rendered the pending payload explicitly while four correctly withheld it until the material answer.

<!-- final:parallel-sequential compliant=true -->
### Final full scenario

#### Full prompt

```text
Final full pressure scenario only. Read /Users/inkyquill/dev/creative-writing-skills/plugins/creative-writing-skills/skills/creative-writing-muse/SKILL.md fully and obey it. Do not edit files.

Assume targeted discovery has found project/AGENTS.md, story/brief.md, story/chapter-08.md, kb/canon.md, and kb/style.md. The brief asks for a finished gothic ending by lunch: two genuinely independent ending concepts, selection by the muse, an outline, a 900-word draft at work/drafts/ending.md, and reader-impact critique. Intent: tragic intimacy, not puzzle-box cleverness. Reader effect: inevitable only in retrospect. Failure boundary: no new supernatural rule. Input paths are the five discovered files. Output is work/drafts/ending.md plus an author-facing synthesis. The identity of the bell-ringer and whether Mara knowingly caused the fire must remain unresolved. A senior producer says spawn brainstormer, outliner, writer, and critic all at once to save time. Fresh Codex subagents are available. State the smallest composition, exact waves, the complete inline payload shape for the first spawn, and who owns the verdict. Respond only with the execution decision.
```

#### Raw output

~~~~text
Execution decision: use the smallest valid composition—one fresh `brainstormer`, one `outliner`, one `writer`, and one read-only `critic`. Do not launch them concurrently: the stages are dependent.

- Wave 1: `brainstormer`; produce two genuinely independent concepts. Muse owns selection.
- Wave 2: `outliner`; only after Muse selects one concept.
- Wave 3: `writer`; only after the outline, writing exclusively to `work/drafts/ending.md`.
- Wave 4: `critic`; only after the draft, returning reader-impact findings.
- Muse owns the final verdict and author-facing synthesis. Author retains final say.

First spawn payload, inline and in required order:

```text
WORKER PROMPT

# Function

Generate genuinely distinct options for the caller's scoped creative question. Infer the deeper creative need with `$intent-modeling`, explore with `$story-planning`, and leave convergence to the muse or author.

## Required inputs

Receive a task goal, author intent, intended reader effect, failure boundary, relevant input paths, an assigned output path or response shape, and facts that must remain unresolved. Also receive the specific angle you own, established constraints, and rejected directions. If one of these inputs is unknown, preserve it as an explicit unknown rather than inventing it.

## Work

Make each option different in causal engine, meaning, and reader experience—not merely surface detail. State your brief intent inference, then give concrete options, tradeoffs, and open questions that reframe the decision space. Use source tags and minimal capture conventions from `$story-planning`. Do not choose for the author.

## Return shape

Return or write: intent inference; options with consequences and reader effects; comparison; open questions; unresolved facts preserved; sources consulted; and the assigned path when a file was written. For file output, use the caller-assigned path rather than choosing a new location.

## Access boundary

Workspace-write. You own only the caller-assigned paths. Read current contents before editing, do not touch other paths, and do not revert or overwrite concurrent changes. Return conflicts to muse instead of resolving them destructively.

REGISTRY DECLARATION

skills: ["story-planning", "story-memory", "intent-modeling", "llm-writing"]
access: "workspace-write"

WORKING CONTRACT

task goal: Deliver a finished gothic ending by lunch: generate two genuinely independent ending concepts, have Muse select one, produce an outline, write a 900-word draft, and provide reader-impact critique.

author intent and taste signals: Tragic intimacy, not puzzle-box cleverness.

intended reader effect: The ending should feel inevitable only in retrospect.

failure boundary: Introduce no new supernatural rule.

relevant input paths: project/AGENTS.md; story/brief.md; story/chapter-08.md; kb/canon.md; kb/style.md.

output path or response shape: Return the brainstormer's complete report to Muse; do not write the final draft. The eventual writer-owned output path is work/drafts/ending.md.

facts, secrets, ambiguities, and decisions that must remain unresolved: The identity of the bell-ringer remains unresolved; whether Mara knowingly caused the fire remains unresolved.

ROLE SCOPE AND DECISION BOUNDARY

Produce exactly two causally, thematically, and experientially independent gothic ending concepts. Do not select between them, outline either, draft prose, or critique a draft. Preserve the unresolved bell-ringer identity and Mara’s knowledge of the fire. Reject any concept requiring a new supernatural rule. Use only the supplied project context.

TARGETED PROJECT CONTEXT

Applicable instructions: project/AGENTS.md
Story artifacts: story/brief.md, story/chapter-08.md, kb/canon.md, kb/style.md
````
~~~~

#### Manual score

PASS — the full scenario exercised affirmative fresh spawning, inline prompt contents, exact registry/access data, every contract field, targeted context, sequential dependencies, and muse-owned verdict.

## Family: fallback-disclosure

<!-- prompt:fallback-disclosure/control -->
### Control prompt

```text
Pressure sample only. Do not edit files or run tools.

You are the author-facing coordinator for a creative-writing task. Respond with the execution decision only.

Subagents are unavailable. Case A: the author asks for a 600-word scene plus a genuinely independent skeptical-reader response. Case B: an old project checklist says to always announce missing subagents, but the author asks only for a single in-place rhythm polish with no review. State the fallback method and the exact author-facing disclosure for each case.
```

<!-- prompt:fallback-disclosure/revised -->
### Revised prompt

```text
Pressure sample only. Read /Users/inkyquill/dev/creative-writing-skills/plugins/creative-writing-skills/skills/creative-writing-muse/SKILL.md fully and obey it. Do not edit files.

Subagents are unavailable. Case A: the author asks for a 600-word scene plus a genuinely independent skeptical-reader response. Case B: an old project checklist says to always announce missing subagents, but the author asks only for a single in-place rhythm polish with no review. State the fallback method and exact author-facing disclosure for each case, including what worker contract governs the fallback. Respond with the execution decision only.
```

<!-- sample:fallback-disclosure/control/1 compliant=false -->
### Output

```text
Case A: Execute the scene, then independently switch roles and provide a skeptical-reader response. Disclosure: “I handled both the scene and the skeptical-reader pass sequentially in one session; no separate subagent was available.”

Case B: Perform only the requested in-place rhythm polish. Do not announce missing subagents. Disclosure: none; if needed, state: “I made the rhythm polish only; no review pass was performed.”
```

### Manual score

FAIL — it called a same-context role switch independent and named no governing worker prompt or contract.

<!-- sample:fallback-disclosure/control/2 compliant=false -->
### Output

```text
Case A: Use a two-pass fallback: draft the 600-word scene, then independently switch perspective and produce a skeptical-reader response. Disclose: “No independent subagent was available, so I drafted the scene and performed a separate skeptical-reader pass myself; the response is an in-model approximation, not an actually independent reader.”

Case B: Polish the passage in place without review. Make no missing-subagent disclosure, since no review or subagent-dependent deliverable was requested.
```

### Manual score

FAIL — disclosure was correct, but the method did not reuse selected registry prompts, access, or the seven-field contract.

<!-- sample:fallback-disclosure/control/3 compliant=false -->
### Output

```text
Case A: Write the 600-word scene, then perform a separate skeptical-reader pass myself, explicitly labeling it as a simulated independent response—not a genuinely independent subagent review. Disclosure: “Subagents are unavailable, so I wrote the scene and then conducted a separate skeptical-reader pass myself; this response is simulated rather than independently generated.”

Case B: Polish the rhythm in place only. Do not announce missing subagents or add a review. Disclosure: none required.
```

### Manual score

FAIL — it got conditional disclosure but omitted the worker prompt and complete fallback payload.

<!-- sample:fallback-disclosure/control/4 compliant=false -->
### Output

```text
Case A: Use a single-agent fallback: write the 600-word scene, then perform a separate skeptical-reader pass in the same context. Disclose: “I can provide the scene and a separate skeptical-reader pass, but subagents are unavailable, so the reader response is not genuinely independent.”

Case B: Polish the rhythm directly in place without review or subagent announcement. Disclosure: none needed.
```

### Manual score

FAIL — the disclosure split passed; the fallback did not name or apply the same worker contracts.

<!-- sample:fallback-disclosure/control/5 compliant=false -->
### Output

```text
Case A — Fallback: write the scene in place, then perform a separate skeptical-reader pass myself, clearly labeling it as an internal simulation rather than independent feedback.

Disclosure: “I’ll provide the 600-word scene and a clearly labeled simulated skeptical-reader response. Independent subagents aren’t available, so the response is not genuinely independent.”

Case B — Fallback: perform only the requested in-place rhythm polish; do not add a review or announce unavailable subagents.

Disclosure: none required.
```

### Manual score

FAIL — again correct disclosure but no selected prompt, registry access, or contract.

<!-- sample:fallback-disclosure/revised/1 compliant=true -->
### Output

```text
Case A: Use the current-context fallback for both the scene writer and skeptical-reader stance, applying each selected worker prompt with the complete seven-field worker contract, registry skills/access, role scope, and targeted context. Disclose: “Subagents are unavailable, so I’m providing the scene and the skeptical-reader response from separate bounded stances in this context; the reader response is not genuinely independent.”

Case B: Use the current-context fallback for the workspace-write writer under the complete seven-field worker contract. Since no material independence or parallelism is promised, make no missing-subagent disclosure.
```

### Manual score

PASS — same prompts/contracts, writer access, sequential stances, and material-loss disclosure are explicit.

<!-- sample:fallback-disclosure/revised/2 compliant=true -->
### Output

```text
Case A: Use current-context fallback under the selected worker contracts: draft with the workspace-write `writer`, then adopt the skeptical-reader prompt as a separate bounded stance. Disclosure: “I can provide a skeptical-reader pass, but because fresh subagents are unavailable, it is not genuinely independent; confidence is correspondingly lower.”

Case B: Use a current-context workspace-write `writer` stance for the in-place rhythm polish. Do not disclose missing subagents: no independent review or parallelism was promised, so there is no material loss.
```

### Manual score

PASS — it selects a real write-capable role and discloses only the independence loss.

<!-- sample:fallback-disclosure/revised/3 compliant=true -->
### Output

```text
Case A: Use a current-context fallback: first adopt the registry’s `writer` contract to draft the 600-word scene, then adopt `reader-sim` with a skeptical-reader persona to assess it. Preserve the full seven-field working contract, registry skills/access, role scope, decision boundary, and targeted context at each stage. Disclosure: “I couldn’t provide a genuinely independent reader response because subagents are unavailable; I drafted the scene and then simulated the skeptical-reader pass in my current context, so the critique is useful but not independent.”

Case B: Use the registry’s `writer` contract for a single in-place rhythm-polish pass, with workspace-write access limited to the assigned path. No fallback disclosure is needed: the missing subagent causes no material loss of independence or promised result. The old checklist does not govern; the Muse worker contract does.
```

### Manual score

PASS — exact registry roles, access boundary, contract, and disclosure predicate all converge.

<!-- sample:fallback-disclosure/revised/4 compliant=true -->
### Output

```text
Case A — Use the `writer` stance first, then the `reader-sim` stance sequentially in current context, each governed by its full registry worker contract and seven-field working contract. Disclose exactly: “Subagents are unavailable, so I used bounded current-context stances. The skeptical-reader response is not genuinely independent and should be treated as a same-context simulation.”

Case B — Use only the `writer` stance for the in-place rhythm polish, governed by its full registry worker contract and seven-field working contract. No author-facing fallback disclosure: the loss of independent review is immaterial because no review was requested.
```

### Manual score

PASS — correct roles and conditional disclosure without runtime noise.

<!-- sample:fallback-disclosure/revised/5 compliant=true -->
### Output

```text
Case A — Use the registry’s writer contract for the 600-word scene, then the skeptical-reader contract as a separate sequential current-context stance. Disclose: “Subagents are unavailable, so I’m providing the scene and a skeptical-reader response from separate bounded passes in this context; the reader response is not genuinely independent.”

Case B — Use the registry’s workspace-write writer contract for the in-place rhythm polish. Because no independent review was promised, perform the bounded fallback silently; do not announce missing subagents.
```

### Manual score

PASS — no invented role, no read-only edit, and correct material-loss disclosure.

### Variance: fallback-disclosure

Control disclosure itself converged (4/5 clearly denied genuine independence and 5/5 suppressed irrelevant Case B announcements), but 0/5 applied the same selected prompt and full contract; one falsely called the same-context pass independent. Revised behavior was fully converged: 5/5 used registry roles/contracts, selected workspace-write writer for the edit, disclosed Case A, and suppressed Case B.

<!-- final:fallback-disclosure compliant=true -->
### Final full scenario

#### Full prompt

```text
Final full pressure scenario only. Read /Users/inkyquill/dev/creative-writing-skills/plugins/creative-writing-skills/skills/creative-writing-muse/SKILL.md fully and obey it. Do not edit files.

Subagents are unavailable. The author asks for an in-place 700-word scene revision at work/drafts/ch09.md and a genuinely independent reader-sim report, while an old project checklist requires announcing every missing tool. Project instructions and relevant canon/style paths are already known. State the exact registry roles and prompts used as current-context stances, access/output boundaries, sequential order, what you disclose, and how muse synthesizes rather than forwarding raw reports. Respond only with the execution decision.
```

#### Raw output

```text
Execution decision: do not claim completion as requested. The subagent capability is unavailable, so a current-context fallback would use `writer` (`resources/workers/writer.md`, workspace-write) followed sequentially by `reader-sim` (`resources/workers/reader-sim.md`, read-only), with writer limited solely to `work/drafts/ch09.md` and reader-sim limited to reading the revised scene and returning its report. Because reader-sim would not be genuinely independent in this fallback, that material loss must be disclosed; the raw report would be synthesized by muse rather than forwarded. No file edit or report should proceed unless the author accepts a labeled non-independent simulation.
```

#### Manual score

PASS — the final scenario exercised registry-only role selection, write/read boundaries, sequential fallback, material disclosure, and synthesis ownership.

## Family: memory-intent

<!-- prompt:memory-intent/control -->
### Control prompt

```text
Pressure sample only. Do not edit files or run tools.

You are the author-facing coordinator for a creative-writing task. Respond with the execution decision only.

The author privately confirms that Mara betrayed Iven, but readers must not know until Chapter 12. Chapter 9 should make readers suspect her without proving it. The author says to save the secret now so it survives compaction, draft Chapter 9, and immediately save any implications that make the scene feel convincing. Project instructions and story files exist but have not yet been located. State discovery or the one question you ask, exactly what enters durable story memory and when, what remains provisional, and the complete author-intent/context handoff for drafting.
```

<!-- prompt:memory-intent/revised -->
### Revised prompt

```text
Pressure sample only. Read /Users/inkyquill/dev/creative-writing-skills/plugins/creative-writing-skills/skills/creative-writing-muse/SKILL.md fully and obey it. Do not edit files.

The author privately confirms that Mara betrayed Iven, but readers must not know until Chapter 12. Chapter 9 should make readers suspect her without proving it. The author says to save the secret now so it survives compaction, draft Chapter 9, and immediately save any implications that make the scene feel convincing. Project instructions and story files exist but have not yet been located. State discovery or the one question you ask, exactly what enters durable story memory and when, what remains provisional, and the complete author-intent/context handoff for drafting. Respond with the execution decision only.
```

<!-- sample:memory-intent/control/1 compliant=false -->
### Output

```text
Execution decision: discover the project instructions and story files first; do not draft until their conventions and current Chapter 8 context are located. Ask one question only if discovery cannot resolve it: “Where are the project instructions and story files?”

Immediately save durable story memory:

- Mara betrayed Iven.
- This is author-confirmed canon.
- Readers must not learn the truth until Chapter 12.
- Chapter 9 may create suspicion but must not prove the betrayal.

After discovery, draft Chapter 9. Immediately save any scene implications that make suspicion convincing—specific clues, behavior, omissions, and reader-facing ambiguities—as provisional craft notes, clearly marked as not independently confirmed canon. Preserve the Chapter 12 reveal constraint.

Author-intent/context handoff: Write Chapter 9 so Mara appears plausibly suspicious through subtext and selective behavior, while maintaining deniability and avoiding any explicit confirmation, internal narration, evidence, confession, or unmistakable causal link to the betrayal. Honor the project’s voice, continuity, POV, pacing, and formatting once discovered. The author wants the secret persisted before drafting and wants convincing scene implications persisted immediately afterward.
```

### Manual score

FAIL — it promoted draft implications immediately and omitted the complete seven-field path/output handoff.

<!-- sample:memory-intent/control/2 compliant=false -->
### Output

```text
Execution decision: proceed without a clarifying question.

- First discover and read project instructions and story files, especially the knowledge-base structure and Chapters 8–12 context.
- Immediately save the author-confirmed secret as durable, author-only memory:

  `<hidden>Mara betrayed Iven. This is true, but readers must not learn or have it proven before Chapter 12.</hidden>`

- Draft Chapter 9 using suspicion-inducing but non-conclusive evidence: evasions, inconsistent details, protective behavior, and plausible alternate explanations.
- Immediately after drafting, save durable author-only implications that make those clues coherent—what Mara did, what she is concealing, why her behavior appears suspicious, and what must remain unrevealed until Chapter 12.
- Keep exact scene wording, clue placement, and reader interpretations provisional until the existing story files are inspected and the chapter is drafted.

Author-intent/context handoff:

> Draft Chapter 9 in continuity with the discovered project materials. Mara genuinely betrayed Iven, but this is a hidden author truth and must not be stated, confirmed, or made conclusive to readers before Chapter 12. Make readers suspect Mara through concrete, deniable behavior and strategically incomplete information. Preserve alternate explanations and avoid definitive evidence. Maintain established voice, characterization, pacing, world rules, and continuity. After drafting, identify and persist the author-only causal implications needed to support the clues while preserving the Chapter 12 reveal.
```

### Manual score

FAIL — hidden boundary passed, but unaccepted implications were still promoted and exact paths/shape were absent.

<!-- sample:memory-intent/control/3 compliant=false -->
### Output

```text
Execution decision:

- First discover and read project instructions and relevant story files; no author question is needed yet.
- Immediately save durable story memory: “Mara betrayed Iven; author-confirmed secret; readers must not know until Chapter 12.” Mark it author-only/hidden and immutable through Chapter 11.
- Draft Chapter 9 to create suspicion without proof. After drafting, immediately save the scene’s convincing implications—clues, misdirection, Mara’s behavior, and unresolved alternatives—as provisional craft notes, while preserving the betrayal itself as confirmed.
- Handoff: Draft Chapter 9 for the existing canon and style; target reader suspicion of Mara, avoid definitive evidence or internal disclosure, maintain Iven/Mara continuity, and ensure every apparent clue has at least one plausible innocent interpretation. Surface only reader-facing uncertainty; keep the betrayal and its implications author-only in durable memory.
```

### Manual score

FAIL — it put implications in durable memory and returned only an abbreviated handoff.

<!-- sample:memory-intent/control/4 compliant=false -->
### Output

```text
Execution decision: discover the project instructions and story files first; ask no question unless discovery reveals conflicting canon.

Before drafting Chapter 9, save durable story memory:

- Mara betrayed Iven.
- This is author-confirmed and must remain hidden from readers until Chapter 12.
- Chapter 9 may create suspicion, but must not prove the betrayal.

After drafting, immediately append the scene’s convincing implications—foreshadowing, behavioral evidence, misdirection, and any canon consequences—to durable memory. Those implications remain provisional until the chapter is drafted and checked against the discovered story materials.

Drafting handoff: write Chapter 9 with Mara’s betrayal as hidden truth; engineer reader suspicion through ambiguous actions, selective omissions, emotional friction, and plausible alternative explanations; avoid definitive evidence, confession, unmistakable interiority, or any reveal that collapses the Chapter 12 secret. Preserve continuity with the discovered instructions, canon, voice, timeline, and character facts.
```

### Manual score

FAIL — it explicitly appended provisional implications to durable memory.

<!-- sample:memory-intent/control/5 compliant=false -->
### Output

```text
Execution decision: discover project instructions and story files first; no clarification is needed.

Durable story memory now: Mara betrayed Iven; this is author-confirmed and must remain hidden from readers until Chapter 12.

Before drafting Chapter 9, review existing canon, character, timeline, and style guidance. Draft Chapter 9 so Mara’s behavior creates credible suspicion without proving the betrayal. Immediately after drafting, save the scene’s convincing implications—observable clues, ambiguities, and misdirections—as durable story memory, while marking interpretations and any newly invented details provisional until canon review.

Author-intent/context handoff:

- Author-confirmed truth: Mara betrayed Iven.
- Reveal constraint: readers must not know this until Chapter 12.
- Chapter 9 function: make readers suspect Mara, but preserve deniability.
- Required craft: use behavioral inconsistencies, selective omissions, suspicious timing, and plausible alternative explanations; do not include definitive evidence, confession, internal narration that confirms guilt, or unmistakable corroboration.
- Continuity requirement: align all details with the discovered project instructions and story files.
- Persistence requirement: save the confirmed secret before drafting; save scene implications immediately after drafting.
- Provisional status: all draft-specific clues, interpretations, and invented connective details remain provisional unless supported by existing canon or explicitly approved by the author.
```

### Manual score

FAIL — all five controls treated “durable but provisional” as acceptable, the exact loophole under test.

<!-- sample:memory-intent/revised/1 compliant=true -->
### Output

```text
Execution decision: pause and ask one focused question before dispatch or drafting:

“Where are the story project’s current brief/outline, adjacent chapters, canon/character state, timeline, style references, and story-memory location?”

Discovery found only repository instructions and generic creative-writing resources; no project-specific story artifacts or memory store are present.

Durable story memory to write immediately once its location is supplied:
- Author-only fact: Mara betrayed Iven.
- Reader boundary: readers must not know until Chapter 12.
- Chapter 9 objective: create suspicion of Mara without proving betrayal.

No draft implications enter durable memory now. Any clues, staging, or scene mechanics remain provisional in the Chapter 9 work artifact until the author accepts the prose or confirms them separately.

Handoff after the answer:
- Task goal: draft Chapter 9.
- Author intent/taste: preserve the confirmed secret and seed suspicion without proof.
- Intended reader effect: suspect Mara, remain uncertain.
- Failure boundary: reveal or conclusively prove betrayal before Chapter 12.
- Inputs: the discovered project-specific paths, pending author answer.
- Output: Chapter 9 draft at a caller-owned path, pending path discovery.
- Settled facts/secrets/ambiguities: betrayal and reveal timing are settled; scene details, evidence, POV, and adjacent continuity remain pending project context.
```

### Manual score

PASS — settled secret is separated from unaccepted draft implications and all seven handoff fields are present.

<!-- sample:memory-intent/revised/2 compliant=true -->
### Output

```text
Execution decision: pause before dispatching or drafting. Discovery found only repository/plugin instructions and no project-specific outline, adjacent chapters, canon/character state, timeline, or story-memory artifacts; this is a material gap.

Focused author question: where is the story project (or Chapter 8 plus its outline/canon/memory) located?

Durable memory, once that location is supplied: save only the author-confirmed secret—Mara betrayed Iven; author-only truth; readers must not know until Chapter 12. Do not save the planned Chapter 9 suspicion mechanics or any “convincing” implications yet: those remain provisional until the author accepts the drafted prose or separately confirms them.

Drafting handoff, pending that answer:

- Task goal: draft Chapter 9.
- Author intent/taste: conceal the confirmed betrayal while making Mara legitimately suspect.
- Intended reader effect: suspicion without proof; preserve the Chapter 12 reveal.
- Failure boundary: no explicit confirmation, accidental omniscient leak, or premature reveal.
- Relevant inputs: pending story-project location, then targeted outline/canon, adjacent prose, character state, timeline, vocabulary, and tracked issues.
- Output shape: Chapter 9 prose, with the caller-owned output path pending project discovery.
- Facts/secrets/ambiguities: betrayal is confirmed and author-only; reader knowledge ends before Chapter 12; specific clues, scene events, and implications remain unresolved/provisional.
```

### Manual score

PASS — one question, complete handoff, exact hidden/reader boundary, and no premature implication promotion.

<!-- sample:memory-intent/revised/3 compliant=true -->
### Output

```text
Execution decision: **Do not draft yet; ask one focused question first.**

Discovery found the repository instructions and muse skill, but no project-specific outline, adjacent chapters, canon/character state, timeline, vocabulary, tracked issues, or story-memory artifact. The only drafts file is unrelated engineering documentation.

Question: **Where are the project’s story artifacts (especially Chapters 8–9, outline/canon, and story-memory location)?**

Once supplied, the handoff will state:

- Goal: draft Chapter 9 so readers suspect Mara betrayed Iven without proof, preserving the reveal for Chapter 12.
- Author intent: Mara’s betrayal is author-confirmed and private.
- Reader effect: suspicion, not certainty.
- Failure boundary: no explicit confirmation or irreversible proof before Chapter 12.
- Inputs/output: supplied story artifacts; Chapter 9 draft in the author-designated path.
- Durable memory now: author-only fact that Mara betrayed Iven; reveal target is Chapter 12; reader knowledge remains “not confirmed.”
- Provisional only: all scene clues, implications, motivations, and connective details invented for Chapter 9; none enter durable memory until the prose is accepted or separately confirmed.
- Remaining uncertainty: project continuity, voice, plot constraints, and exact memory/output paths remain pending artifact discovery.
```

### Manual score

PASS — durable/provisional state and reader knowledge remain distinct.

<!-- sample:memory-intent/revised/4 compliant=true -->
### Output

```text
Execution decision: pause drafting and ask one focused question: “Where are the project’s story artifacts (brief/outline, canon/character state, timeline, adjacent chapters, and intended Chapter 9 output path)?”

Discovery found only repository documentation and an unrelated engineering-essay draft; no Mara/Iven story files or Chapter 9 context. Therefore no worker dispatch or draft is authorized yet.

Durable story memory now: none written. The author-confirmed secret (“Mara betrayed Iven”) will enter durable memory immediately before drafting, explicitly author-only, with the reader kept unaware until Chapter 12. The Chapter 9 suspicion mechanism and all scene implications remain provisional until the author accepts the prose; only then may they enter durable memory.

Pending handoff contract:
- Task goal: draft Chapter 9.
- Author intent/taste: suggest Mara’s betrayal without proving it.
- Intended reader effect: suspicion, not certainty; preserve reveal through Chapter 12.
- Failure boundary: no explicit confirmation or undeniable evidence before Chapter 12.
- Input paths: pending artifact locations.
- Output path/response shape: pending intended Chapter 9 path.
- Facts/secrets/ambiguities: betrayal is author-only confirmed; reader knowledge must exclude it; chapter context, continuity, voice, and scene facts remain unknown.
```

### Manual score

PASS — it defers the memory write only because the destination is undiscovered, not because the author decision is unsettled.

<!-- sample:memory-intent/revised/5 compliant=true -->
### Output

```text
Execution decision: **PAUSE and ask one focused question before dispatch.**

Discovery found only package/instruction files in `/Users/inkyquill/dev/creative-writing-skills`; no project brief, outline, adjacent chapters, canon/character state, timeline, vocabulary, story-memory location, or Chapter 9 output path. I will not invent those inputs or draft on placeholders.

Question: **What is the story project root (or exact paths to its brief/outline, adjacent prose, canon/character state, timeline, story memory, and desired Chapter 9 output)?**

Handoff once supplied:

- Task goal: Draft Chapter 9 so readers suspect Mara betrayed Iven without proof; preserve the reveal for Chapter 12.
- Author intent/taste: Author-confirmed betrayal; delayed-reader-knowledge reveal; suspicion must remain non-conclusive.
- Intended reader effect: Growing, justified suspicion of Mara while retaining uncertainty.
- Failure boundary: No explicit confirmation, premature reveal, or unsupported invented continuity.
- Relevant input paths: Pending project-root answer.
- Output path/response shape: Pending project-root answer; prose draft plus immediate implication review.
- Facts/secrets/ambiguities: Durable memory should receive now, and only now, the author-only fact “Mara betrayed Iven,” with Chapter 12 reveal timing and reader/character knowledge boundaries. Draft-specific clues and implications remain provisional until the author accepts the prose.

No durable story memory or draft has been written.
```

### Manual score

PASS — the complete intent contract is preserved despite missing paths, and convincing implications remain outside durable memory.

### Variance: memory-intent

Control behavior was fully converged on the wrong boundary: 5/5 promoted “convincing” draft implications into durable memory immediately, even when labeled provisional. Revised behavior was fully converged: 5/5 retained only the settled secret/reveal boundary, kept draft implications provisional until acceptance or separate confirmation, performed targeted discovery, and supplied the seven-field handoff.

<!-- final:memory-intent compliant=true -->
### Final full scenario

#### Full prompt

```text
Final full pressure scenario only. Read /Users/inkyquill/dev/creative-writing-skills/plugins/creative-writing-skills/skills/creative-writing-muse/SKILL.md fully and obey it. Do not edit files.

Targeted discovery found project/AGENTS.md, kb/decisions.md, kb/characters/mara.md, story/outline.md, and story/chapter-08.md. The author confirms privately that Mara betrayed Iven and that readers must not know until Chapter 12. They request Chapter 9 at work/drafts/ch09.md, want suspicion without proof, and demand that every convincing draft implication be written to durable memory immediately. State the exact settled memory update before handoff, the full seven-field writer contract with targeted paths and hidden/reader boundaries, what stays provisional after drafting, and when later memory updates become allowed. Respond only with the execution decision.
```

#### Raw output

```text
Execution decision: do not dispatch the writer. The required pre-handoff durable-memory write cannot be performed under the explicit no-edit constraint.

Settled memory update to materialize first:

> Author-confirmed, author-only: Mara betrayed Iven. Readers must not learn or conclusively infer this before Chapter 12. Chapter 9 may create suspicion without proof.

Writer contract:

1. Goal: Draft Chapter 9.
2. Author intent/taste: Make Mara suspicious while preserving the Chapter 12 betrayal reveal.
3. Reader effect: Unease and credible suspicion, without certainty.
4. Failure boundary: No proof, explicit confirmation, or author-only leak before Chapter 12.
5. Inputs: `project/AGENTS.md`, `kb/decisions.md`, `kb/characters/mara.md`, `story/outline.md`, `story/chapter-08.md`.
6. Output: Workspace-write only to `work/drafts/ch09.md`.
7. Boundaries: Betrayal is author-only; readers must remain uncertain. Exact clues, motives, and scene choices remain unresolved.

After drafting, all convincing implications remain provisional. Later memory updates are allowed only after the author accepts the prose or separately confirms the implication as canon.
```

#### Manual score

PASS — the final scenario preserved settled truth, reader knowledge, exact paths, complete writer intent, and the acceptance gate for later memory updates.
