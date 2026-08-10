# Codex-Primary Creative Writing Plugin Design

## Summary

Rebuild this repository as a vanilla Codex plugin while preserving Claude as a
generated compatibility distribution. Remove Mars and Meridian from the
package architecture, development workflow, documentation, and CI.

The canonical installable plugin will live at
`plugins/creative-writing-skills/`. The repository will expose it through a
repo marketplace so a user can add `InkyQuill/creative-writing-skills` as a
Codex marketplace source. The plugin will retain the current multi-agent muse
experience, provide a single-agent fallback, and ship the complete current
runtime skill set plus the existing `world-creation` skill.

## Goals

- Make Codex the primary authoring and distribution target.
- Use only documented Codex plugin primitives: a plugin manifest, skills, skill
  resources, UI metadata, and a repo marketplace.
- Preserve muse-led delegation to fresh writer, critic, editor, reader,
  planner, research, style, and continuity contexts.
- Preserve a useful single-agent fallback when subagents are unavailable.
- Promote the complete 24-skill runtime currently assembled in `cw/skills/`
  into the canonical Codex plugin, sourcing the 14 creative-writing-specific
  skills from this repository and vendoring the remaining 10 generic skills
  from the pinned Apache-2.0-covered snapshot in
  `haowjy/creative-writing-skills` (see "Vendored generic skills" below).
- Add `world-creation` — the author's existing skill, currently at
  `~/Documents/writing/aria/.agents/skills/world-creation` and itself derived
  from the MIT-licensed `grill-me` in `mattpocock/skills` and `worldbuilding`
  in `danjdewhurst/story-skills` — as a standalone 25th canonical skill.
- Keep Claude Code, Cowork, and Claude.ai support through a deterministic
  generated compatibility distribution under `cw/`.
- Keep current story projects usable without automatic manuscript migration.
- Retain Apache-2.0 licensing and upstream attribution while making the
  InkyQuill fork the canonical repository and current developer identity.

## Non-goals

- Keep Mars or Meridian as a supported installation path.
- Preserve Mars source metadata, model aliases, CLI commands, environment
  variables, generated targets, or dependency resolution.
- Invent a neutral intermediate prompt schema between Codex and Claude.
- Hand-maintain duplicate Codex and Claude copies of every skill.
- Add an MCP server, app integration, or lifecycle hook without a concrete
  capability that requires one.
- Automatically reorganize an author's existing project or rewrite story
  prose during plugin installation or project setup.
- Submit the plugin to the universal public plugin directory in this rebuild.
  The package will be compatible with a later submission.

## Chosen Architecture

### Repository layout

```text
creative-writing-skills/
├── .agents/
│   └── plugins/
│       └── marketplace.json
├── plugins/
│   └── creative-writing-skills/
│       ├── .codex-plugin/
│       │   └── plugin.json
│       └── skills/
│           ├── creative-writing-muse/
│           │   ├── SKILL.md
│           │   └── resources/
│           │       └── workers/
│           ├── world-creation/
│           └── ...
├── cw/
│   ├── .claude-plugin/
│   ├── agents/
│   └── skills/
├── scripts/
├── tests/
├── docs/
└── README.md
```

This follows the documented repo-marketplace structure: the marketplace file
is rooted at `.agents/plugins/marketplace.json`, and its local source points to
`./plugins/creative-writing-skills`.

### Source of truth

`plugins/creative-writing-skills/` is the only canonical runtime source.
Codex-native skill files and worker resources are edited there first.

`plugins/creative-writing-skills/.codex-plugin/plugin.json` is the source of
truth for plugin name, version, description, license, repository URL, current
developer identity, and interface metadata. Derived Claude metadata must match
its version and identity fields.

The `cw/` directory is build output committed for Claude marketplace use and
release artifacts. A small, explicit compatibility ruleset may contain
Claude-only transformations, but `cw/` itself is not an independent prompt
source.

### Vendored generic skills

Ten of the twenty-four skills inherited from the previous `cw/skills/` runtime
are generic rather than creative-writing content: `information-hierarchy`,
`intent-modeling`, `knowledge-layers`, `llm-writing`, `qi-layer`, `reflect`,
`grill-with-docs`, `structured-artifact`, `md-validation`, and `zoom-out`.
Their licensed distribution source is the Apache-2.0-covered `cw/skills/`
snapshot in `haowjy/creative-writing-skills` commit
`fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3`.

`plugins/creative-writing-skills/skills/` vendors those ten pinned snapshots
through `scripts/vendor_generic_skills.py`. Apply mode reads the named source
checkout, normalizes frontmatter to plain Codex `name`/`description` metadata,
and writes the canonical plugin tree. Check mode proves the committed copies
still match that exact licensed snapshot. Vendoring runs only when deliberately
refreshing the pinned inputs; install and ordinary runtime use the committed
copies.

`haowjy/meridian-base` commit
`d3c4b3313d38e18dd7970f1db34af15c25dbf238` is recorded only as the ten
skills' immediate development provenance. That repository has no declared
license, so it is not a distributable input and refreshes from it are
prohibited unless a compatible license is declared. `THIRD_PARTY_NOTICES.md`
records both the licensed source and the provenance boundary; the skills are
not described as original InkyQuill work.

### Rejected alternatives

1. A neutral `src/` schema generating both Codex and Claude was rejected
   because it would introduce another private package format and recreate the
   abstraction cost that Mars imposed.
2. Separate hand-maintained `codex/` and `cw/` trees were rejected because 25
   skills and the orchestration prompts would drift.
3. A plugin manifest at repository root was rejected for distribution because
   the documented Git-backed repo marketplace layout expects installable
   plugins under `plugins/<name>/`.

## Plugin Composition

### Canonical skill set

Promote all 24 skills currently bundled in `cw/skills/` into the canonical
Codex plugin — 14 sourced directly from this repository, 10 vendored per
"Vendored generic skills" above. Add `world-creation` for a total of 25
skills. Preserve resources that those skills need and remove harness-specific
metadata or instructions.

Each canonical skill must:

- use Codex-compatible `name` and `description` frontmatter;
- contain a specific description suitable for automatic activation;
- remain directly invocable through `$skill-name`;
- use relative links for its own resources;
- avoid Mars commands, Meridian environment variables, Claude agent syntax,
  and unsupported private package concepts;
- state its file-write and author-confirmation boundaries in the workflow when
  those boundaries matter.

Broad creative-writing requests automatically select `creative-writing-muse`.
Specific requests may select a narrower skill directly. Explicit
`$creative-writing-muse` invocation remains supported.

### Muse orchestration

`creative-writing-muse` owns the author-facing session. It:

1. discovers project instructions and relevant story artifacts;
2. captures intended reader effect, constraints, taste signals, uncertainty,
   and failure boundaries;
3. selects the smallest specialist composition appropriate to the task;
4. dispatches independent work to fresh Codex subagents when available;
5. reads and judges all returned work itself;
6. synthesizes conflicts and decides whether to revise, gather another view,
   update story memory, ask the author, or present the result;
7. updates durable story context only after decisions settle.

Muse must not forward a raw worker report as its final response. It remains
responsible for the verdict and for communication with the author.

### Worker prompts

Claude-style agent profile files are not a Codex plugin component. The former
agent roles therefore become reusable worker prompt resources owned by muse.
The initial role set is:

- brainstormer;
- character simulator;
- continuity checker;
- critic;
- editor;
- outliner;
- reader simulator;
- style creator;
- web researcher;
- writer.

Each worker resource defines:

- its bounded responsibility;
- the craft skills it must apply;
- the task brief fields it expects;
- the project files or context it needs;
- whether it may edit files;
- what it must return to muse;
- what it must not decide on the author's behalf.

Muse passes the selected worker prompt, relevant skill names, task brief, and
targeted project context to the spawned subagent. Independent tasks may run in
parallel. Dependent drafting and review stages remain sequential.

Read-only reviewers stay read-only by instruction. Writers and planners that
receive write access get narrow ownership of named files or directories and
must preserve concurrent edits.

### Single-agent fallback

If subagents are unavailable, disabled, or a spawn cannot complete, muse uses
the same worker prompt as a stance in its current context. It preserves the
same task boundaries and workflow sequence. Muse tells the author about the
fallback only when losing fresh-context independence materially affects the
expected result, such as an adversarial critique immediately after drafting.

## World Creation Integration

Add the author's existing `world-creation` skill as a standalone canonical
skill, not as a resource buried inside `story-planning`. Its starting point was
the local skill at `~/Documents/writing/aria/.agents/skills/world-creation`,
itself a modified derivative of Matt Pocock's `skills/productivity/grill-me`
at `mattpocock/skills` commit
`84fdeffd12f2ee307994d1eb6feb48173b6e0502` and Daniel Dewhurst's
`skills/worldbuilding` at `danjdewhurst/story-skills` commit
`c482d48f4eb9b488f033a77a51f9fae55cc0d75f`, both MIT-licensed. Their notices
are retained in `LICENSES/` and `THIRD_PARTY_NOTICES.md`.

The migration imports `SKILL.md` and moves `WORLD-FILE-FORMAT.md` to
`references/world-file-format.md`, preserving the source's read-only and
confirmation boundaries. It does not copy the local per-skill
`agents/openai.yaml`: the supported skill package surface does not include
that interface override, and the Claude generator excludes it as well. The
useful world-creation starter request from that file instead lives in the
plugin manifest's `interface.defaultPrompt`, where Codex supports plugin UI
prompt suggestions.

Preserve its strongest behavior:

- map existing project context before substantive questions;
- interrogate one decision at a time;
- recommend an answer with every decision question;
- follow dependencies inward before expanding the lore tree;
- distinguish existing lore, story evidence, recommendation, and user
  decision;
- require confirmation before canonization;
- keep story prose read-only;
- update the smallest appropriate non-story file after confirmation;
- trace institutional, social, economic, political, and everyday
  consequences;
- update nearby indexes when discoverability changes.

Support both project layouts as equal first-class discovery conventions:

| Concern | Layout A | Layout B |
|---|---|---|
| World lore | `worldbuilding/` | `kb/world/` |
| Characters | `characters/` | `kb/characters/` |
| Canonical prose | `chapters/` | `story/` |
| Draft prose | `drafts/` | `work/drafts/` |
| Planning | `plot/` | `work/outline/` |

The skill discovers the actual project structure rather than preferring one
layout after it finds clear local conventions. Canonical prose and draft prose
remain read-only throughout this workflow.

As authored today, the source skill only implements Layout A
(`worldbuilding/`, `characters/`, `chapters/`, `drafts/`, `plot/`). Layout B
discovery is new work added during this integration, not an existing
capability being preserved.

Muse routes setting creation, reconciliation, expansion, and sanity-checking
to `world-creation`. The skill also remains independently auto-triggerable and
explicitly invocable as `$world-creation`.

## Project Setup and Story Compatibility

The canonical `project-setup` skill creates or updates `AGENTS.md` and the
chosen story workspace only after author confirmation. It must not assume that
a new project is empty, overwrite existing project instructions, or move
existing manuscript files.

Both the established layout (`kb/`, `story/`, `work/`) and the alternative
layout (`worldbuilding/`, `characters/`, `chapters/`, `drafts/`, `plot/`) are
supported. Setup detects existing conventions and extends them. For a new
project, it presents a recommended layout and receives confirmation before
creating it.

The generated Claude `project-setup` counterpart uses `CLAUDE.md` where Codex
uses `AGENTS.md`. Shared story facts remain in ordinary Markdown files rather
than being duplicated across harness instruction files.

## Claude Compatibility Distribution

Create `scripts/sync_claude_distribution.py` with apply and check modes.

The generator derives:

- `cw/skills/` from canonical Codex skills;
- `cw/agents/` from muse worker resources and declared skill mappings;
- `cw/.claude-plugin/plugin.json` from canonical plugin metadata;
- the legacy Claude marketplace metadata needed for GitHub installation;
- Claude.ai `.skill` release inputs.

Explicit transforms cover:

- frontmatter and activation conventions;
- Codex subagent language versus Claude agent invocation language;
- worker resources materialized as Claude agent files;
- `AGENTS.md` versus `CLAUDE.md` behavior;
- Codex-only tool or orchestration vocabulary;
- version, repository, developer, and license propagation.

The generator must fail instead of silently dropping an instruction it cannot
translate. Manual compatibility exceptions live in a named rules or overrides
area and are covered by tests. They do not authorize unrelated manual edits to
generated `cw/` files.

## Metadata and Distribution

The canonical repository is
`https://github.com/InkyQuill/creative-writing-skills`.

The plugin manifest uses:

- normalized name `creative-writing-skills`;
- strict semantic versioning;
- InkyQuill as the current developer identity;
- Apache-2.0 as the license;
- the fork URL for repository and homepage metadata unless a dedicated project
  site is added later;
- concise interface copy and no asset paths until real assets exist.

Retain upstream authorship and license notices in the repository documentation
and license materials. Do not present the fork as the original author of work
it inherited.

The repo marketplace entry uses:

- local source `./plugins/creative-writing-skills`;
- installation policy `AVAILABLE`;
- authentication policy `ON_INSTALL`;
- an appropriate writing or productivity category supported by validation.

Users add the GitHub repository as a marketplace source and then install the
plugin. The Git repository is the primary Codex distribution. A universal
public-directory submission is a later publishing step, not a prerequisite
for this rebuild.

Claude Code and Cowork continue using the generated Claude marketplace plugin.
Claude.ai skill archives continue to be attached to tagged GitHub releases.

## Validation and Testing

### Static validation

Repository validation must check:

- Codex plugin manifest schema and required metadata;
- marketplace schema, policies, and source path;
- all 25 canonical skill packages and UI metadata;
- vendored generic skills match their upstream source (vendoring drift);
- skill names, descriptions, and directory-name consistency;
- relative resource links;
- worker-to-skill mappings;
- dangling `$skill` and worker references;
- absence of Mars and Meridian vocabulary in canonical and generated runtime
  files;
- absence of leaked Codex-only orchestration vocabulary in Claude output;
- version and identity consistency across derived artifacts.

The repository must contain its own repeatable validation entry point rather
than depending on a developer's globally installed skill package.

### Generator tests

The Claude sync check generates into a temporary directory, compares the
result with committed `cw/`, and reports actionable drift. Fixture tests cover:

- frontmatter lowering;
- worker prompt to Claude agent conversion;
- `AGENTS.md` to `CLAUDE.md` adaptations;
- version and repository metadata propagation;
- unsupported transformation failures;
- both project-layout aliases used by `world-creation`.

### Build and platform checks

CI runs:

1. canonical Codex plugin and marketplace validation;
2. canonical skill and reference linting;
3. vendored generic-skill drift check (`scripts/vendor_generic_skills.py`
   check mode);
4. unit and fixture tests;
5. Claude distribution drift and leak checks;
6. Claude plugin validation when the Claude CLI is available in CI;
7. Claude.ai skill archive generation;
8. release tag and canonical plugin version consistency.

### Behavioral release checklist

Model-backed behavior is checked manually in representative new conversations
because it requires credentials and can vary by model. The release checklist
covers:

- automatic muse activation for broad creative-writing work;
- explicit `$creative-writing-muse` activation;
- brainstorming and outlining;
- fresh drafting and revision;
- focused critique and holistic editorial review;
- reader simulation;
- continuity checking;
- character simulation;
- world creation and confirmed canon updates;
- story-memory updates after settled decisions;
- multi-agent orchestration;
- single-agent fallback.

## Failure Handling

- Missing project files lead to targeted discovery or one author question, not
  invented context.
- Conflicting lore is surfaced before edits. The author chooses whether to
  revise, narrow, or preserve the conflict in-world.
- Provisional brainstorming never becomes canon without confirmation.
- `world-creation` never patches canonical or draft prose.
- A failed specialist spawn may be retried or handled through the single-agent
  fallback according to whether fresh context is important.
- Generator errors identify the source file and unsupported construct.
- Validation rejects missing resources, invalid metadata, dangling references,
  and silent distribution drift.
- No migration step deletes Mars or Meridian files until both the canonical
  Codex plugin and generated Claude plugin validate from the new source.

## Migration Sequence

1. Add the repo marketplace, canonical plugin manifest, repository-local
   validator, and initial tests.
2. Promote the 14 creative-writing-specific skills from this repository into
   the canonical plugin and port them to vanilla Codex conventions; stand up
   `scripts/vendor_generic_skills.py` and vendor the 10 generic skills from
   their confirmed upstream source.
3. Convert muse and the former agent profiles into Codex orchestration plus
   worker prompt resources.
4. Import `world-creation` from
   `~/Documents/writing/aria/.agents/skills/world-creation` into the canonical
   plugin and add both project-layout conventions (Layout A is already
   implemented there; Layout B is new).
5. Implement deterministic Claude generation and regenerate `cw/`.
6. Update project setup, README, architecture documentation, release tooling,
   and CI for the Codex-primary workflow.
7. Validate both distributions and build Claude.ai archives.
8. Remove Mars and Meridian manifests, source metadata, commands, dependencies,
   generated hook remnants, documentation, and CI paths.
9. Run the complete static suite and behavioral release checklist.

Each stage keeps changes reviewable. The removal stage occurs only after the
new primary and compatibility paths pass their validation gates.

## Acceptance Criteria

- `codex plugin marketplace add InkyQuill/creative-writing-skills` recognizes
  the repo marketplace, and the plugin can be installed from it on a supported
  Codex surface.
- The installed plugin exposes 25 valid skills with automatic and explicit
  activation.
- Vendored generic skills reproducibly match their upstream source and
  validate identically to hand-authored skills.
- Muse delegates to fresh Codex subagents for specialist work and provides a
  functioning single-agent fallback.
- `world-creation` works directly and through muse without editing story prose.
- Both supported story layouts are discovered correctly.
- `cw/` is reproducibly generated from the Codex-primary source and validates
  as a Claude plugin.
- Claude.ai skill archives build successfully.
- No active runtime, build, validation, release, or user documentation path
  depends on Mars or Meridian.
- CI fails on distribution drift, invalid manifests, dangling references,
  forbidden platform vocabulary, or version mismatch.
- The repository credits inherited upstream work while identifying InkyQuill
  as the current fork developer.

## Reference

The package structure and marketplace layout follow OpenAI's current plugin
packaging documentation:
<https://developers.openai.com/plugins/build/plugins>.
