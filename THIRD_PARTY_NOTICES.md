# Third-Party Notices

## Scroll quill icon

The plugin icon is Delapouite's
[`Scroll quill`](https://game-icons.net/1x1/delapouite/scroll-quill.html) from
[game-icons.net](https://game-icons.net/), licensed under
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). The original artist
is [Delapouite](https://delapouite.com/). The committed SVG and PNG retain the
colors supplied for this plugin.

The following skill snapshots are imported from the Apache-2.0 distribution at
[`haowjy/creative-writing-skills@fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3`](https://github.com/haowjy/creative-writing-skills/tree/fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3):

- `grill-with-docs`
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
