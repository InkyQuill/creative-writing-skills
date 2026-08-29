# Useful Skills Incorporation Design

**Status:** Approved after brainstorming on 2026-08-29

## Summary

Three external sources stashed in the git-ignored `useful/` directory are
curated into the canonical plugin without adding skills to the inventory. The
ru-text Russian editorial corpus becomes the Russian editorial layer of the
prose stack plus deterministic typography findings in `cw check prose`. The
`joke-engineering` skill and a core craft pack from the jwynia creative bundle
become craft, planning, and world-creation resources. One deterministic script
(`dialogue_audit.py`) is ported to the Python standard library. The skill
inventory stays at 31, the story project contract is unchanged, and the
vendoring machinery is untouched; attribution lands in `THIRD_PARTY_NOTICES.md`
following the existing local-derivative pattern.

## Sources and Licensing

- **ru-text** — MIT, © 2026 Arseniy Kamyshev,
  `https://github.com/talkstream/ru-text`. The repository snapshot in
  `useful/ru-text/` is the pinned input; adapted excerpts are taken from
  `skills/ru-text/references/` and the metric design of
  `tools/measure-prose-shape.py`.
- **jwynia creative bundle** — MIT, author jwynia, skill version 1.0. The
  snapshot in `useful/creative/` is the pinned input; adapted content is taken
  from the skills named in this spec.

`useful/` stays git-ignored. No shipped skill, resource, or document may
reference a path inside it; it is a reading stash, not a distribution input.
Refreshes re-run the curation manually; there is no automated vendoring path
for these sources.

## Goals

- Give Russian-language projects a mechanical editorial floor: deterministic
  typography findings that are codepoint-verifiable and carry no literary
  conclusions.
- Give Russian editing workflows a curated editorial corpus: typography,
  punctuation, grammar, stop-words, anti-patterns, and neuroslop rules with
  their carve-outs.
- Extend the deterministic prose metrics with flattening detection so
  `targeted-editing` and `story-review` can compare before/after runs.
- Add humor, dialogue, scene sequencing, endings, character arc, and
  key-moments craft references, plus worldbuilding generator parameters, to
  authored skills.
- Port only deterministic script logic to the Python standard library and test
  it in the repository suite.

## Non-goals

- No new skills and no inventory growth; the configured 31-skill inventory is
  unchanged.
- No vendoring-machinery changes; the single pinned upstream for vendored
  skills stays as configured.
- No judgment scoring. The ru-text five-dimension 0–10 rubric is not adopted;
  the CLI continues to report metrics without literary conclusions, and
  judgment stays with `story-review`, workers, and the muse.
- No UX-writing or business-writing domains; those ru-text references are
  dropped.
- No English typography findings in this version; the ruleset structure admits
  a later `en` addition without schema or interface changes.
- No TypeScript runtime and no `deno.land` dependencies anywhere in shipped
  content.
- No changes to the story project contract, its schema, or its migration.
- Nothing from the deferred queue in the last section is implemented now.

## Russian Editorial Layer

### Resources

A new directory
`plugins/creative-writing-skills/skills/creative-writing-craft/resources/prose/editorial/ru/`
holds the curated corpus, in Russian, written as imperative model instructions
with examples, following the repository's writing conventions:

| File | Derived from | Curation |
|---|---|---|
| `typography.md` | `references/typography.md` | Near-full. Mechanical defaults: guillemets primary and lapki nested, em dash with NBSP, en dash for ranges, ellipsis character, digit grouping, decimal comma, №, ordinals, abbreviation spacing. |
| `punctuation.md` | `references/editorial-punctuation.md` | Full. |
| `grammar.md` | `references/editorial-grammar.md` | Full. |
| `stop-words.md` | `references/info-style.md` | The §B stop-word catalog (92 entries, inflected use noted) and the specificity rules; the SEO and content-marketing framing is dropped. |
| `anti-patterns.md` | `references/anti-patterns.md` and the dash-budget rules in `references/addenda.md` | Bureaucratic language, nominalization, passive overuse, tautology; the em-dash budget of one to two per paragraph with its parallel-row and dialogue carve-outs. |
| `neuroslop.md` | `references/addenda.md` | The AD-1..AD-18 AI-tell rules **with their carve-outs**. The carve-outs decide as many cases as the triggers and are mandatory content: a rule shipped without its carve-outs produces the false positives this corpus exists to prevent. |

`resources/prose/languages/ru.md` remains the language entry point and gains a
resolution pointer to the editorial layer. The prose stack resolution in the
`creative-writing-craft` SKILL.md gains one conditional step: for
`ru`-language projects, the editorial layer under
`resources/prose/editorial/ru/` loads for proofreading, line-editing, and
review passes; it is not loaded for initial drafting, where its size would
crowd context without improving generation.

Dropped from ru-text: `ux-writing.md`, `business-writing.md`, `scoring.md`,
the three SKILL.md wrappers (`ru-text`, `ru-check`, `ru-score`), and the
repository tooling and golden corpus. Golden cases may inspire test fixtures
but no ru-text tooling ships.

### Typography findings in `cw check prose`

The `prose` checker gains a typography finding family, emitted only when the
manifest language normalizes to `ru`. Every rule is a codepoint-level check
with a stable finding code, a suggested replacement, and a next action that
points at confirming conventions in `project.md` and applying fixes through a
previewed edit.

Warning severity:

- a straight double-quote character in prose text, where `«»` is primary and
  `„“` nested;
- a hyphen with whitespace on both sides, where a dash is meant;
- a literal three-dot sequence where `…` is expected;
- an ordinary breakable space after a single-letter word (`в`, `к`, `с`, `о`,
  `у`, `и`, `а`, `я`) mid-sentence, where a non-breaking space is expected.

Info severity:

- an unseparated run of five or more digits, where grouped digits are
  expected;
- a decimal point between digits, where a comma is expected;
- `No.` or `#` where `№` is expected;
- ordinals such as `1ый` where `1-й` is expected;
- closed-up abbreviations such as `т.д.` where `т. д.` is expected.

Exclusions and carve-outs:

- Findings are computed on the same stripped text the prose metrics use:
  frontmatter, fenced code, inline code, and link targets are excluded.
- Direct-speech punctuation (`«…», — сказала она`) and a comma closing
  homogeneous subordinate clauses before a dash are legitimate constructions
  and are never flagged.
- Nested Latin quotes inside Cyrillic text are reported at info severity, not
  warning, because mixed-script prose may carry them deliberately.

All typography findings are warnings or info, never errors: fiction may
deviate deliberately, `project.md` states the project's conventions, and the
author's stated style outranks the defaults, matching ru-text's own
style-priority rule. `--strict` treats warnings as failure exactly as it does
for existing warnings; ordinary runs report without failing. English-language
projects emit no typography findings; a test proves the gate.

### Prose-shape metrics

`ProseMetrics` and the `check prose` JSON output gain the measure-prose-shape
additions:

- `sentence_length_p90` and `sentence_length_step` (mean absolute difference
  between adjacent sentence lengths) — language-neutral;
- `em_dash_count` — language-neutral;
- subordination per sentence and `intensifier_count` — computed for `ru` from
  closed Russian word lists adapted from the upstream tool; `en` lists are a
  documented future extension point and the fields are null for `en` in this
  version.

The upstream tool's measured finding is preserved as design intent: CV
(sd/mean) is not a verdict metric, because chopping sentences divides sd and
mean proportionally; flattening is detected through p90, adjacent step, and
standard deviation compared between two runs. No new CLI command is added;
consumers diff two `check prose --format json` runs. The Russian abbreviation
guard the upstream splitter uses (`т. д.`, initials) is evaluated for the
existing sentence splitter during implementation; if adopted, existing
sentence-count expectations are updated in the same change with explicit test
coverage.

## Humor and Craft Resources

All resources are adapted, not copied: imperative instructions, examples,
`$skill` references where relevant, and the repository's confirmation
boundaries (provisional suggestions do not become canon; world-creation work
does not edit manuscript prose). Placement follows the existing flat-file
pattern beside `scene-construction.md`.

- **`creative-writing-craft/resources/humor.md`** — from `joke-engineering`:
  the nine system properties, the H1–H6 diagnostic states with symptoms and
  interventions, connection-density enhancement patterns, and compression
  guidance. It is diagnostic craft reference for the `editor`, `critic`, and
  `writer` workers; comedy production modes remain with
  `creative-writing-modes`.
- **`creative-writing-craft/resources/dialogue.md`** — from the bundle's
  `dialogue` skill: the three subtext layers, flat-dialogue and same-voice
  diagnosis, and the audit method. The deterministic measurements move to the
  ported script below.
- **`creative-writing-craft/resources/dialogue_audit.py`** — stdlib-only
  Python port of the deterministic core of the bundle's dialogue scripts. It
  measures, per file: speaker-tag ratio for Russian and English attribution
  verbs, longest run of consecutive same-speaker turns, dialogue-line ratio
  (reusing the prose capability's dialogue detection), and content-vocabulary
  overlap between the most frequent speakers as a same-voice signal. It
  reports numbers, not verdicts; interpretation stays with the agent.
  Interface: `python3 dialogue_audit.py <file> [--format json]`, UTF-8 in,
  exit 0 on success and 2 on execution failure; there is no exit-1 path
  because the script is a measurement, not a check.
- **`creative-writing-craft/resources/scene-sequencing.md`** — from
  `scene-sequencing`: Swain's scene/sequel structure
  (goal–conflict–disaster, reaction–dilemma–decision), pacing diagnosis, and
  alternation guidance. No script port: scene-boundary detection is not
  deterministic on schema v1, whose scene-record columns are deliberately
  unconstrained.
- **`creative-writing-craft/resources/endings.md`** — from `endings`: ending
  anatomy, resolution types, and subplot-resolution diagnosis. No setup-payoff
  script port: promise tracking is already the `promises.md` checker in
  `cw check continuity`, and a second mechanism would compete with the
  project contract.
- **`creative-writing-craft/resources/character-arc.md`** — from
  `character-arc`: lie/want/need, positive/negative/flat arc polarities, and
  arc-troubleshooting states. Prose-only upstream; no script.
- **`story-planning/resources/key-moments.md`** — from `key-moments`:
  building stories from essential emotional moments crossed with elemental
  genres. It is planning input for the `outliner` and `brainstormer`
  workers.
- **`world-creation/resources/generators/{belief,economic,governance,settlement,metabolic,systemic,oblique}.md`**
  — from the bundle's prose-only worldbuilding generators: belief systems,
  economic systems, governance systems, settlement design, metabolic
  cultures, systemic consequence cascades, and oblique documentary
  worldbuilding. Each keeps its parameter tables and cliché-avoidance notes,
  adapted to the world-creation confirmation boundaries. They supply the
  generative side that complements world-creation's existing
  consequence-grilling.

The `creative-writing-craft` SKILL.md technique index and the
`world-creation` and `story-planning` skill bodies gain the corresponding
resolution pointers. Worker prompt files are updated only where a pointer is
insufficient; the `editor` and `critic` workers already load
`creative-writing-craft`, and `outliner` and `brainstormer` already load
`story-planning`, so most wiring is through resource resolution rather than
registry changes.

## Attribution

`LICENSES/` gains `MIT-ru-text.txt` and `MIT-jwynia-creative.txt` containing
the respective upstream license texts.
`THIRD_PARTY_NOTICES.md` gains two sections in the existing local-derivative
style used by `world-creation`: pinned source locations, and a file-by-file
derivation map from each new resource to its upstream file. Because the
content is adapted rather than copied verbatim, the notice states what was
incorporated and what was dropped.

## Testing

- Typography findings: Russian fixture chapters covering each rule (clean
  control, straight quotes, hyphen-as-dash, three-dot ellipsis, breakable
  space after single-letter words, each info rule), golden finding codes for
  text and JSON output, exclusion cases (fenced code, inline code, direct
  speech with comma-dash), and an English-project regression proving the
  language gate.
- Prose-shape metrics: unit tests for p90, adjacent step, em-dash count, and
  the Russian subordination and intensifier lists on crafted texts; null
  fields for `en`; any abbreviation-guard change to the sentence splitter
  updates existing sentence-count expectations in the same change.
- `dialogue_audit.py`: unit tests for each measurement, mixed-language
  fixtures, malformed-input behavior.
- Behavioral: typography warnings do not fail `cw check all`; `--strict`
  does; findings carry next actions pointing at previewed edits.
- Resource validation: the full repository suite,
`scripts/validate_distribution.py`,
`scripts/sync_claude_distribution.py --check`, and
`scripts/create_skill_zips.py` pass with the new resources present.

## Distribution and Rollout

The canonical inventory, `config/distribution.json`, the vendored partition,
and the marketplace do not change. New resources travel through the existing
generation flow: edit canonical skills, run
`scripts/sync_claude_distribution.py --apply`, and verify with `--check`.
`resources/command-reference.md` documents the new finding family. The
CHANGELOG records the capability, and the work ships as a `0.8.0` minor
release via `scripts/release.py minor` from a clean `main`.

Implementation proceeds in dependency order, each stage leaving the suite
green:

1. ru editorial resources and attribution;
2. typography findings and tests;
3. prose-shape metrics and tests;
4. craft resources, `dialogue_audit.py`, and the worldbuilding generators;
5. skill-body and worker wiring, command-reference and CHANGELOG updates,
   regeneration, and release.

## Deferred Queue

The following `useful/` content is documented as a revisit queue and is not
implemented: `character-naming` (strongest future candidate; needs its
culture-name data pools shipped and a Python port of the generators),
`cliche-transcendence`, `statistical-distance`, `memetic-depth`,
`sensitivity-check`, `book-marketing`, `flash-fiction`, the structure-pattern
generators (`moral-parallax`, `positional-revelation`, `identity-denial`,
`perspectival-constellation`, `underdog-unit`), the music pair
(`lyric-diagnostic`, `musical-dna`), the tabletop trio (`game-facilitator`,
`table-tone`, `world-fates`), `sleep-story`, `paradox-fables`,
`interactive-fiction`, the adaptation triple (`dna-extraction`,
`adaptation-synthesis`, `media-adaptation`), `multi-order-evolution`,
`list-builder`, `reverse-outliner`, and the `chapter-drafter` closed-loop
scoring pattern. The overlapping skills listed in the brainstorming triage
(story-analysis, drafting, revision, novel-revision, prose-style, story-sense,
the coach/collaborator and outline pairs, shared-world, story-zoom,
genre-conventions, story-idea-generator, and the worldbuilding router) are
rejected rather than deferred: they duplicate capabilities the plugin already
owns with project-contract integration.
