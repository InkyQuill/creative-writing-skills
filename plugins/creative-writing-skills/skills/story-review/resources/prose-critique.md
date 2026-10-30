---
name: story-review
description: >
  Passage-grounded diagnostic review of narrative fiction against author intent. Focus-area driven with dedicated resources per area. Use when reviewing drafts, evaluating prose quality, or assessing changes at any stage.
---

# Prose Critique

Determine whether the passage achieves the author's intended effect. Report
supported problems, working features revision must preserve, and material
uncertainties. “No substantial change needed” is a valid result. Use adversarial
stress-testing only when requested; do not manufacture objections to fill a report.

## Your Focus

Your prompt specifies a focus area. Go deep on the assigned focus rather than skimming everything. Each focus area has a dedicated resource with detailed guidance:

- [`resources/prose-critique/structure.md`](prose-critique/structure.md): plot logic, pacing, scene necessity, stakes, setup/payoff
- [`resources/prose-critique/character.md`](prose-critique/character.md): motivation coherence, arc progression, relationship dynamics
- [`resources/prose-critique/voice.md`](prose-critique/voice.md): dialogue quality, POV consistency, subtext, voice drift
- [`resources/prose-critique/prose.md`](prose-critique/prose.md): line-level quality, rhythm, clarity, repetition, show vs tell
- [`resources/prose-critique/continuity.md`](prose-critique/continuity.md): facts, timeline, geography, character state

Read the relevant resource when assigned that focus. If no focus is specified, assess the draft yourself: figure out which dimensions matter most for this piece, read those resources, and focus there.

Even with an assigned focus, flag issues outside it if they're clearly serious. A voice reviewer who notices a plot hole should say so.

## What Makes a Good Finding

Good findings share these qualities:

**Specific.** Reference the chapter, scene, paragraph, or line. "The pacing has issues" is not a finding.

**Reasoned.** Explain why it matters, not just that it exists. A POV break is only interesting if you can describe what it costs: reader trust, immersion, character distinction.

**Directable.** The writer should know what to do after reading your finding. If the fix isn't clear, say what investigation or decision is needed.

**Non-obvious.** Spell-check already caught the typos. You're here for things that require understanding context, intent, and interaction between story elements.

### What wastes everyone's time

- Vague "this could be stronger" without explaining how or why
- Restating what the prose says without identifying a problem
- Generic praise without identifying an effect or a feature revision should preserve
- Findings about established story decisions the author already committed to: critique the execution, not the premise

## Communicating Impact

Make it obvious which findings are serious and which are minor. The orchestrator or author triaging your findings has context you don't: they know what's intentional, what's set up for later, what's a known compromise. Give them a clear signal about severity.

Lead with the things that damage the reading experience: broken causation, character inconsistency, lost tension, confused POV. Let the smaller observations follow. Only flag issues you can tie to a concrete reader cost.

## Diagnostic Questions

Investigate what the passage does and whether that serves its intended form:

- **Motivation.** Does this character have a reason to do what they're doing here? Would they actually say this?
- **Causation.** Does this scene follow logically from the previous one? Is the character's reaction earned by what happened?
- **Tension.** Is the conflict real? Are stakes at risk? Does the scene resolve too easily?
- **POV discipline.** Does the narrator know things they shouldn't? Are other characters' internal states reported as fact?
- **Voice consistency.** Does the narrator sound like the same person throughout? Do characters maintain their distinct voices?
- **Reader experience.** Where would a reader's attention drift? Where would they feel confused, cheated, or talked down to?

Anchor strengths as precisely as problems. “The awkward pause makes the
reconciliation credible; preserve it” constrains revision. A lack of conflict,
change, or explicit motivation is not itself a defect; establish the reader
cost in this story before recommending an intervention.

## Calibrating to Stage

**Early draft**: focus on structural and character issues. Line-level prose quality doesn't matter if the scene shouldn't exist or the character motivation is broken.

**Mid-stage draft**: structural foundations should be solid. Focus on voice, pacing, and how scenes connect.

**Late draft**: focus on the requested polish; flag a supported larger issue
without treating stage as proof that structure is settled.

Don't spend time on prose-level polish of a scene that has structural problems. Fix the bones before the skin.

## Your Report

Open with a brief overall assessment: what's the big picture for this draft? Then walk through findings grouped by severity or by theme, whichever tells a clearer story. End with your verdict: what's the most important thing to address, and what's the one change that would improve this draft the most?

In multi-critic parallel lanes, keep your report focused on your assigned area. The orchestrator synthesizes across critics: you go deep, not broad.

## Optional: Mechanical Analysis

A bundled `$project-maintenance` check measures universal mechanical properties
such as sentence-length distribution and repetition, plus only the
language-sensitive signals supported for the manuscript language. These are
quantitative signals useful for comparing a draft against the project's own
same-language, same-scope baseline. Omitted language-sensitive metrics are not
zero and never justify an English fallback. Read-only agents (critic, continuity-checker) should
request this data from the orchestrator; agents with bash access can run the
canonical project check directly:

```bash
cw check prose [project]
```

## Resources

- [`resources/prose-critique/antipatterns.md`](prose-critique/antipatterns.md): AI writing antipatterns, categorized as research-backed vs community folklore
- [`resources/prose-critique/tells.md`](prose-critique/tells.md): named structural tells of machine-flavored prose with fiction fixes — flag clusters, never a single tell
- [`resources/prose-critique/baseline.md`](prose-critique/baseline.md): establishing a project baseline and comparing drafts against it
