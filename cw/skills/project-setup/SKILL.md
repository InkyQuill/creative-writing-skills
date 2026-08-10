---
name: project-setup
description: "One-time project setup for creative writing. Interviews the author about the project, discovers or confirms its file layout, collects provisional writing samples and voice goals, and creates or updates project instructions after the workspace plan is approved.\n"
---

# Project Setup

Guide the author through setting up their creative writing project. The goal is
a working `CLAUDE.md` and one coherent directory layout that future sessions
and delegated workers read for project-specific conventions. Preserve every
existing project file. Do not create or modify the workspace until the author
explicitly confirms the proposed structure and content.

## Discover the Project and Its Layout

Ask what kind of project this is, how far along it is, its POV and timeline
shape, and how much worldbuilding it needs. Before asking where files should
go, inspect existing indexes and populated directories for both supported
layouts. Read `CLAUDE.md` first when it exists. Look for `_index.md`,
`index.md`, `INDEX.md`, and `README.md` at the project root and inside likely
content directories, then inspect filenames and contents rather than treating
empty directory names as established convention.

Use these equivalent roles:

| Concern | Layout A | Layout B |
|---|---|---|
| World lore | `worldbuilding/` | `kb/world/` |
| Characters | `characters/` | `kb/characters/` |
| Canonical prose | `chapters/` | `story/` |
| Draft prose | `drafts/` | `work/drafts/` |
| Planning | `plot/` | `work/outline/` |

Select the layout before proposing any file path:

For each layout, calculate a population score as the ordered pair `(populated
core role directories, durable files)`. First count how many of its five core
role directories contain at least one nonempty regular project file, including
an index; then count all nonempty regular project files recursively within
those five directories. Compare the first count, then use the second count as
the tie-breaker. Root or parent indexes that explicitly map the roles are
layout evidence, but do not add to the population score.

- If only Layout A has indexes or populated role directories, use Layout A
  and extend it.
- If only Layout B has indexes or populated role directories, use Layout B
  and extend it.
- If both have evidence, use the layout with the higher population score and
  explain both counts. If both have the same population score, ask one focused
  choice between the two, with a recommendation grounded in the files already
  present, and wait for the author's answer.
- If neither layout has evidence, recommend one layout with a project-specific
  rationale and wait for explicit confirmation.

Do not propose paths or create files until a layout is selected from clear
existing evidence or explicitly confirmed by the author. Never create the
competing layout in an established project, and never migrate between layouts
silently.

## Writing Samples and Style

Ask whether the author has sample chapters, scenes, writing from other
projects, published style references, or voice goals. During discovery, keep
samples and voice goals provisional in the conversation. Do not save samples,
write style files, or capture voice goals in `CLAUDE.md` yet.

If there is enough material, propose analysis with the
`/creative-writing-craft` methodology as part of the workspace plan. If the
project is starting fresh, include voice goals in the proposed `CLAUDE.md`
content so style files can be derived from early drafts after approval.

## Propose and Iterate

After the layout is selected, draft project instructions for `CLAUDE.md` and
show them to the author. The proposal identifies the selected layout and lists
only paths from its matching section below. For an existing project, propose
extensions to its established indexes and populated directories; do not
reorganize existing files.

Cover:

- the project overview and current stage;
- where world lore, characters, canonical prose, drafts, and planning live;
- voice, style, naming, chapter, POV, timeline, and spoiler conventions;
- shared vocabulary, aliases, invented terms, and terms to avoid or
  distinguish;
- the exact missing directories or files proposed for creation; and
- any sample, style, vocabulary, index, or work-support path as a separate
  optional item requiring author confirmation.

Present the draft, let the author adjust it, and iterate until both its content
and every proposed path are approved.

## Create the Files

Once approved, preserve existing content and make only the agreed additions or
updates. Write or update `CLAUDE.md` with the agreed instructions. Create only
missing role paths from the selected layout and only when they were included in
the approved proposal. Auxiliary paths are created only when the author
confirmed their purpose and exact local name.

### Layout A paths

For selected Layout A, use `worldbuilding/`, `characters/`, `chapters/`,
`drafts/`, and `plot/` for the five core roles. Do not create a `kb/`, `story/`,
or `work/` counterpart. Add sample, style, or vocabulary paths only as
author-confirmed auxiliary paths consistent with local conventions—for example
an existing `samples/`, `style/`, `glossary/`, or `vocab.md` convention. Create
or update an index only when the folder has multiple durable files and the
author confirmed that index role.

### Layout B paths

For selected Layout B, use `kb/world/`, `kb/characters/`, `story/`,
`work/drafts/`, and `work/outline/` for the five core roles. Do not create a
`worldbuilding/`, `characters/`, `chapters/`, `drafts/`, or `plot/` counterpart.
Create `kb/samples/` and `kb/styles/` only as author-confirmed auxiliary paths.
Create `kb/vocab.md`, domain vocabulary files, `kb/index.md`, and additional
work support such as `work/critique-reports/` or `work/brainstorm/` only when
the author confirmed them and they match local conventions.

Save samples or produce initial style analysis only at the exact approved path
for the selected layout. Never infer approval for auxiliary files from approval
of the core layout.

## Existing Projects

If project instructions already contain creative-writing conventions, suggest
the smallest updates instead of overwriting them. Leave other instruction and
configuration files intact unless the author explicitly asks to change them.
When a local folder or index uses a more specific name than the table, preserve
that established name and record its role in `CLAUDE.md`.
