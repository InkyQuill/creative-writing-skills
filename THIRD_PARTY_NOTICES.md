# Third-Party Notices

## Scroll quill icon

The plugin icon is Delapouite's
[`Scroll quill`](https://game-icons.net/1x1/delapouite/scroll-quill.html) from
[game-icons.net](https://game-icons.net/), licensed under
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). The original artist
is [Delapouite](https://delapouite.com/). This plugin uses a recolored version
of the original artwork. The supplied recolored SVG and PNG were committed
without further modification.

The following skill snapshots are imported from the Apache-2.0 distribution at
[`haowjy/creative-writing-skills@fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3`](https://github.com/haowjy/creative-writing-skills/tree/fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3):

- `decision-grill` (distributed name; the pinned upstream snapshot is named
  `grill-with-docs`)
- `information-hierarchy`
- `intent-modeling`
- `knowledge-layers`
- `llm-writing`
- `md-validation`
- `qi-layer`
- `reflect`
- `structured-artifact`
- `zoom-out`

Their immediate development provenance is
`haowjy/meridian-base@d3c4b3313d38e18dd7970f1db34af15c25dbf238`. Refreshes from that repository are
prohibited until it declares a compatible license. These skills are not
original InkyQuill work.

## `world-creation`

The canonical `world-creation` skill is a local InkyQuill-authored derivative
that incorporates and adapts:

- Matt Pocock's `skills/productivity/grill-me` at
  [`mattpocock/skills@84fdeffd12f2ee307994d1eb6feb48173b6e0502`](https://github.com/mattpocock/skills/tree/84fdeffd12f2ee307994d1eb6feb48173b6e0502/skills/productivity/grill-me),
  particularly the reusable one-question-at-a-time grilling method it
  represents. See [`LICENSES/MIT-mattpocock-skills.txt`](LICENSES/MIT-mattpocock-skills.txt).
- Daniel Dewhurst's `skills/worldbuilding` at
  [`danjdewhurst/story-skills@c482d48f4eb9b488f033a77a51f9fae55cc0d75f`](https://github.com/danjdewhurst/story-skills/tree/c482d48f4eb9b488f033a77a51f9fae55cc0d75f/skills/worldbuilding).
  See [`LICENSES/MIT-story-skills.txt`](LICENSES/MIT-story-skills.txt).

The resulting integration is modified for this plugin, including its
dual-layout discovery and immutable prose boundaries.

## Russian editorial layer

The `resources/prose/editorial/ru/` files in `creative-writing-craft`, the
Russian typography findings and prose-shape additions in the bundled `cw`
CLI, and `resources/dialogue_audit.py` are local InkyQuill-authored
derivatives that incorporate and adapt
[`talkstream/ru-text`](https://github.com/talkstream/ru-text) (MIT; see
`LICENSES/MIT-ru-text.txt`), particularly `skills/ru-text/references/{typography,editorial-punctuation,editorial-grammar,info-style,anti-patterns,addenda}.md`
and the metric design of `tools/measure-prose-shape.py`. The UX-writing and
business-writing references, the scoring rubric, and the repository tooling
were not incorporated. Local modifications: curation for fiction-prose use,
imperative rewrite, and Python integration.

## Craft and worldbuilding resources

The `humor.md`, `dialogue.md`, `scene-sequencing.md`, `endings.md`, and
`character-arc.md` resources in `creative-writing-craft`, `key-moments.md`
in `story-planning`, and the `resources/generators/` pack in
`world-creation` are local InkyQuill-authored derivatives that incorporate
and adapt skills from
[`jwynia/agent-skills`](https://github.com/jwynia/agent-skills) (MIT; see
`LICENSES/MIT-jwynia-agent-skills.txt`): `joke-engineering`, `dialogue`,
`scene-sequencing`, `endings`, `character-arc`, `key-moments`, and the
worldbuilding generators `belief-systems`, `economic-systems`,
`governance-systems`, `settlement-design`, `metabolic-cultures`,
`systemic-worldbuilding`, and `oblique-worldbuilding` (skill version 1.0).
The upstream TypeScript scripts were not incorporated; deterministic logic
was re-implemented in Python where noted in the spec. Local modifications:
curation and imperative rewrite for this plugin's conventions.

## Continuity records, checker, beat sheets, tells, and preflight checks

The `story-memory` continuity-record formats and deterministic checker
(`resources/continuity-records.md`, `resources/continuity_check.py`), the
`story-planning` beat sheets (`resources/story-architecture/beat-sheets.md`),
and the `targeted-editing` post-edit ripple checklist are local InkyQuill
work that adapts the continuity-ledger model and edit-ripple checklist of
Daniel Dewhurst's
[`danjdewhurst/story-skills`](https://github.com/danjdewhurst/story-skills)
(MIT; see [`LICENSES/MIT-story-skills.txt`](LICENSES/MIT-story-skills.txt)).

The `story-review` structural-tell catalogue (`resources/prose-critique/tells.md`),
the cluster-density vocabulary policy in `resources/prose-critique/antipatterns.md`,
the line-edit structure checks and voice calibration, the proofreading
pasted-artifact checklist, the specificity ladder in `creative-writing-modes`,
and the punctuation-tell nuance in `writing-principles` adapt techniques from
Forjd's [`forjd/better-writing`](https://github.com/forjd/better-writing)
(MIT; see [`LICENSES/MIT-better-writing.txt`](LICENSES/MIT-better-writing.txt)).
All examples and prose in the adapted sections are original InkyQuill work.
