---
name: project-setup
description: "One-time project setup for creative writing. Interviews you about your project, collects writing samples, proposes kb structure, and creates or updates CLAUDE.md with project conventions after you confirm the workspace plan.\n"
---

# Project Setup

Guide the author through setting up their creative writing project. The goal
is a working `CLAUDE.md` and directory structure that future sessions and
delegated workers read for project-specific conventions, plus initial style
files if writing samples are available. Preserve every existing project file.
Do not create or modify the workspace until the author explicitly confirms the
proposed structure and content.

## Learn About the Project

Ask about:

- What kind of project: novel, short story collection, serial?
- How far along: starting fresh, or existing chapters and worldbuilding?
- Single POV or multiple? Linear or non-linear timeline? How much worldbuilding?
- Where do they keep their writing? What's the existing layout?

## Writing Samples and Style

Ask about writing samples: these are the foundation for style analysis:

- Do they have sample chapters or scenes already written?
- Do they have writing from other projects that captures the voice they want?
- Are there published works they want to draw style inspiration from?
- Voice goals: close third, omniscient, first person? Formal, colloquial?

During discovery, keep samples and voice goals provisional in the conversation.
Do not save samples, write style files, or capture voice goals in `CLAUDE.md`
yet. If the author has enough material, propose analysis with the
`/creative-writing-craft` methodology as part of the workspace plan. If they
are starting fresh, include their voice goals in the proposed `CLAUDE.md`
content so style files can be created from early drafts after approval.

## Propose and Iterate

Based on what you learn, draft an `CLAUDE.md` section and show it to the
author. Cover:

- **Project overview**: what the project is, one paragraph
- **Author's space**: where the author keeps their writing and how it's
  organized
- **KB structure**: what subdirectories exist under `kb/` and what they're
  for. Suggest based on project complexity:
  - Simple (short story, single POV): `characters/`, `canon/`, `styles/`, root `vocab.md`
  - Medium (novel, few POVs): add `timeline/`
  - Complex (series, large world): add `world/`, `issues/`, and domain vocab files such as `world/vocab.md`
- **Voice and style**: what style files exist, what samples they're derived
  from, voice goals not yet captured
- **Conventions**: anything project-specific: naming patterns, chapter
  numbering, POV tagging, spoiler handling
- **Shared vocabulary**: early canonical terms, aliases, invented words,
  genre terms with project-specific meanings, and terms the author wants
  agents to avoid or distinguish

Present the draft and let the author adjust. Iterate until they're satisfied.

## Create the Files

Once approved, preserve existing content and make only the agreed additions or
updates:

1. Write or update `CLAUDE.md` with the agreed content
2. Create the `kb/` directories referenced in `CLAUDE.md`
3. Create `kb/vocab.md` when the project has named concepts agents must use
   consistently; create domain vocab files when a domain already has enough
   distinct terms
4. Create `work/` with standard subdirectories (outline/, drafts/,
   critique-reports/, brainstorm/)
5. Save any writing samples to `kb/samples/`
6. If samples were provided and the author wants style analysis, produce
   initial style files in `kb/styles/`

## Existing Projects

If `CLAUDE.md` already has creative writing conventions, read it first and
suggest updates rather than overwriting. If the project has other instruction
or configuration files, leave them intact unless the author explicitly asks to
change them.
