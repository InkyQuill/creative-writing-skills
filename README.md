# Creative Writing Skills

[![CI](https://github.com/InkyQuill/creative-writing-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/InkyQuill/creative-writing-skills/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

A Codex plugin for planning, drafting, reviewing, and maintaining fiction. A
muse coordinates focused specialist passes while shared skills preserve craft,
voice, continuity, and durable story context.

## Install for Codex

Add this repository as a marketplace source, then install the plugin from that
source:

```bash
codex plugin marketplace add InkyQuill/creative-writing-skills
codex plugin add creative-writing-skills@creative-writing-skills
```

Start naturally with a story request such as “Help me plan the next chapter.”
Broad creative-writing work activates the muse automatically. You can also
invoke it directly:

```text
$creative-writing-muse Help me turn these scene fragments into a chapter plan.
```

Specific skills remain directly available. For example:

```text
$world-creation Reconcile this river-based magic idea with the lore in kb/world/.
```

## How the Muse Works

The muse remains the author-facing partner. It identifies the smallest useful
specialist composition, prepares a bounded brief and worker prompt for each
pass, reads the returned work, resolves disagreements, and presents a
synthesized result. Available roles cover brainstorming, outlining, drafting,
critique, editing, reader simulation, continuity, character simulation, style,
and research.

Independent passes can run in parallel. Dependent work stays sequential: a
draft is completed before a fresh critic or editor reviews it, and revisions
follow the muse's synthesis rather than raw worker output. When Codex
subagents are unavailable, the muse applies the same worker prompts as bounded
stances in the current conversation. It preserves the workflow and tells the
author when the loss of fresh-context independence materially affects the
result.

## Claude Compatibility

Claude Code and Cowork use the generated compatibility plugin in `cw/`.

In Claude Code, add the marketplace and install the plugin:

```text
/plugin marketplace add InkyQuill/creative-writing-skills
/plugin install creative-writing-skills@creative-writing-skills
```

In Cowork, open **Customize → Personal plugins → + → Add marketplace → Add
from repository**, enter `InkyQuill/creative-writing-skills`, and install
**creative-writing-skills**. The generated Claude agents mirror the muse and
specialist roles.

### Claude.ai skill archives

Claude.ai can use the individual `.skill` archives attached to the
[latest GitHub release](https://github.com/InkyQuill/creative-writing-skills/releases/latest).
Upload them under **Customize → Skills**, enable `creative-writing-muse`, and
describe the writing task. Skills-only chat uses the muse's single-agent
fallback.

To build the same 25 archives locally:

```bash
python3 scripts/sync_claude_distribution.py --check
python3 scripts/create_skill_zips.py
```

The archives are written to `zips/` from the generated `cw/skills/` tree.

## Core Skills

| Skill | Purpose |
|---|---|
| `creative-writing-muse` | Author-facing orchestration, synthesis, and fallback workflow |
| `story-planning` | Brainstorming, outlining, and story architecture |
| `creative-writing-modes` | Fresh drafts, revisions, bridges, alternatives, and polish |
| `creative-writing-craft` | Prose, scene, style, voice, and genre technique |
| `story-review` | Critique, editorial review, line work, and reader-signal synthesis |
| `reader-sim` | Persona-bound first-time reader simulation |
| `character-sim` | In-character voice and relationship exploration |
| `world-creation` | Context-first worldbuilding with confirmation before canonization |
| `story-memory` | Durable facts, timeline, canon, terminology, and issue tracking |
| `writing-staffing` | Small, purpose-built specialist compositions |

All 25 installed skills are listed in `config/distribution.json`.

## Story Project Layout

The plugin adapts to existing projects. A typical project can use:

```text
my-story/
├── AGENTS.md
├── story/                  # Chapters and manuscript
├── work/                   # Plans, drafts, and review artifacts
└── kb/                     # Characters, world, timeline, canon, styles, issues
```

Project setup does not reorganize an existing manuscript or canonize
provisional ideas without confirmation.

## Contributing

The only canonical runtime source is
`plugins/creative-writing-skills/`. Edit skills and worker resources there;
never hand-edit `cw/`, which is committed generated compatibility output.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 scripts/validate_distribution.py
python3 scripts/sync_claude_distribution.py --check
python3 scripts/create_skill_zips.py
```

After changing canonical content, regenerate and revalidate:

```bash
python3 scripts/sync_claude_distribution.py --apply
python3 scripts/sync_claude_distribution.py --check
python3 scripts/validate_distribution.py
```

Release versioning reads and updates only the canonical plugin manifest, then
regenerates and verifies derived metadata:

```bash
python3 scripts/release.py patch
python3 scripts/release.py minor --push
```

Without `--push`, the release commit and tag remain local.

## License and Attribution

Apache License 2.0. See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for inherited work and
vendored-skill attribution.
