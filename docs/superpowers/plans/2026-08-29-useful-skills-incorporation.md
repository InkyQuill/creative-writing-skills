# Useful Skills Incorporation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Curate the ru-text Russian editorial corpus and the jwynia core craft pack into the canonical plugin (editorial resources, deterministic typography findings, prose-shape metrics, one Python script port, craft and worldbuilding resources) and ship as 0.8.0.

**Architecture:** All content lands in authored skills under `plugins/creative-writing-skills/skills/`; deterministic typography findings and new metrics extend the existing `cw` prose checker inside `cwcli`; the generated `cw/` tree is refreshed only through `scripts/sync_claude_distribution.py --apply`. No new skills, no inventory changes, no vendoring-machinery changes.

**Tech Stack:** Python 3.10+ standard library only (CLI and skill scripts); Markdown resources; `unittest` test runner; repository sync/validation scripts.

**Spec:** `docs/superpowers/specs/2026-08-29-useful-skills-incorporation-design.md` (approved 2026-08-29)

## Global Constraints

- Python 3.10+ standard library only; no new dependencies, no TypeScript, no network imports.
- Never hand-edit `cw/`, root `marketplace.json`, or generated manifests; regenerate with `python3 scripts/sync_claude_distribution.py --apply`, verify with `--check`.
- The configured 31-skill inventory does not change; `config/distribution.json` is not modified.
- Skill resources use relative links only; every relative link must resolve (`scripts/validate_distribution.py` enforces this).
- Codex skill references use `$skill-name` outside fenced examples.
- No shipped file may reference a path inside `useful/` (it is a git-ignored reading stash).
- Full test command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` (all 742+ tests must pass at every task boundary).
- Curated resources are written in Russian where the source is Russian (editorial layer) or English (humor/craft/generators, matching their destination skills' language), in imperative model-instruction voice with examples.
- Commit messages follow the existing style (`feat:`, `docs:`, `test:`, `chore:`).

## File Structure Overview

Created (canonical plugin):
- `skills/creative-writing-craft/resources/prose/editorial/ru/{typography,punctuation,grammar,stop-words,anti-patterns,neuroslop}.md`
- `skills/creative-writing-craft/resources/{humor,dialogue,scene-sequencing,endings,character-arc}.md`
- `skills/creative-writing-craft/resources/dialogue_audit.py`
- `skills/story-planning/resources/key-moments.md`
- `skills/world-creation/resources/generators/{belief,economic,governance,settlement,metabolic,systemic,oblique}.md`
- `skills/project-maintenance/resources/cli/cwcli/checks/prose_typography.py`

Created (repo root / tests):
- `LICENSES/MIT-ru-text.txt`, `LICENSES/MIT-jwynia-agent-skills.txt`
- `tests/cw_cli/test_prose_typography.py`, `tests/cw_cli/test_prose_shape.py`, `tests/test_dialogue_audit.py`

Modified:
- `cwcli/checks/prose.py` (new metrics fields, typography wiring, `__all__`)
- `cwcli/checks/__init__.py` (no change expected — `check_prose` already registered)
- `skills/creative-writing-craft/SKILL.md` (prose-stack step + resource index)
- `skills/creative-writing-craft/resources/prose/languages/ru.md` (editorial pointer)
- `skills/story-planning/SKILL.md`, `skills/world-creation/SKILL.md` (resource pointers)
- `skills/creative-writing-muse/resources/workers/editor.md` (one sentence in `## Work`)
- `skills/project-maintenance/resources/command-reference.md` (typography finding family)
- `tests/test_language_prose_rules.py` (exact prose-resource tree gains 6 files)
- `THIRD_PARTY_NOTICES.md`, `CHANGELOG.md`
- Regenerated: `cw/` tree, `zips/` (via scripts only)

Source material (read-only inputs, git-ignored): `useful/ru-text/skills/ru-text/references/*.md`, `useful/ru-text/tools/measure-prose-shape.py`, `useful/creative/...`.

---

### Task 1: Attribution foundations

**Files:**
- Create: `LICENSES/MIT-ru-text.txt`
- Create: `LICENSES/MIT-jwynia-agent-skills.txt`
- Modify: `THIRD_PARTY_NOTICES.md` (append two sections after the `world-creation` section, before the final existing content ends; match its `## \`name\`` heading style)

**Interfaces:**
- Produces: license files and notice sections referenced by every later curation task's header comment.

- [ ] **Step 1: Create `LICENSES/MIT-ru-text.txt`** — verbatim MIT text (copy the format of `LICENSES/MIT-story-skills.txt`), line 3: `Copyright (c) 2026 Arseniy Kamyshev`.

- [ ] **Step 2: Create `LICENSES/MIT-jwynia-agent-skills.txt`** — verbatim MIT text, line 3: `Copyright (c) 2026 J Wynia`.

- [ ] **Step 3: Append notice sections to `THIRD_PARTY_NOTICES.md`**, following the `world-creation` local-derivative pattern at `THIRD_PARTY_NOTICES.md:33-47`:

```markdown
## Russian editorial layer

The `resources/prose/editorial/ru/` files in `creative-writing-craft` and
the Russian typography findings and prose-shape additions in the bundled
`cw` CLI are local InkyQuill-authored derivatives that incorporate and adapt
[`talkstream/ru-text`](https://github.com/talkstream/ru-text) (MIT; see
`LICENSES/MIT-ru-text.txt`), particularly `skills/ru-text/references/{typography,editorial-punctuation,editorial-grammar,info-style,anti-patterns,addenda}.md`
and the metric design of `tools/measure-prose-shape.py`. The UX-writing and
business-writing references, the scoring rubric, and the repository tooling
were not incorporated. Local modifications: curation for fiction-prose use,
imperative rewrite, and Python integration.

## Craft and worldbuilding resources

The `humor.md`, `dialogue.md` (with its ported `resources/dialogue_audit.py`,
a Python re-implementation of the deterministic core of the upstream
`dialogue` skill's TypeScript scripts), `scene-sequencing.md`, `endings.md`,
and `character-arc.md` resources in `creative-writing-craft`,
`key-moments.md` in `story-planning`, and the `resources/generators/` pack in
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
```

- [ ] **Step 4: Verify and commit**

Run: `git status --short` (only the three files above changed).
Run: `git add LICENSES/MIT-ru-text.txt LICENSES/MIT-jwynia-agent-skills.txt THIRD_PARTY_NOTICES.md && git commit -m "docs: add third-party attribution for ru-text and agent-skills derivates"`

---

### Task 2: Editorial resources I — typography, punctuation, grammar

**Files:**
- Create: `plugins/creative-writing-skills/skills/creative-writing-craft/resources/prose/editorial/ru/typography.md`
- Create: `plugins/creative-writing-skills/skills/creative-writing-craft/resources/prose/editorial/ru/punctuation.md`
- Create: `plugins/creative-writing-skills/skills/creative-writing-craft/resources/prose/editorial/ru/grammar.md`
- Modify: `plugins/creative-writing-skills/skills/creative-writing-craft/resources/prose/languages/ru.md` (add editorial pointer)
- Test: `tests/test_language_prose_rules.py` (update exact tree assertion)

**Interfaces:**
- Consumes: source `useful/ru-text/skills/ru-text/references/{typography,editorial-punctuation,editorial-grammar}.md`.
- Produces: `resources/prose/editorial/ru/` directory with the first three files; the exact-tree test at `tests/test_language_prose_rules.py:28-53` must list them.

Curation rules (apply to all three): write in Russian; imperative instructions ("Пиши…", "Ставь…"), keep the wrong/correct example tables verbatim in content (reformat freely); keep every rule and its carve-outs — the mechanical defaults are the point; drop upstream references to UI/product text where a rule is purely non-fictional (keep the rule itself if it applies to prose); no `$skill` references needed in these three; each file starts with one intro paragraph stating these are defaults the project's `project.md` conventions override.

- [ ] **Step 1: Write `typography.md`** from upstream `typography.md` (303 lines; sections A «Кавычки», B «Тире и дефис», C «Пробелы», D «Многоточие», E «Числа и даты»). Map every section and subsection 1:1. The resulting file must cover at minimum: ёлочки primary / лапки nested / forbidden quote kinds; em dash with NBSP before it, en dash in ranges, hyphen in compounds, minus sign; NBSP after single-letter words, in initials, in digit groups (thin), before units, before the dash; no space before punctuation; ellipsis character and its spacing; numerals, dates, №, ordinals, `т. д.` spacing.

- [ ] **Step 2: Write `punctuation.md`** from upstream `editorial-punctuation.md` (141 lines; sections A «Punctuation in complex sentences» A.1–A.5, B «Comma traps — reference table», «Sources»). Map A and B fully; drop the «Sources» section (attribution lives in `THIRD_PARTY_NOTICES.md`).

- [ ] **Step 3: Write `grammar.md`** from upstream `editorial-grammar.md` (501 lines; sections C «Capitalization», D «Agreement», E «Tautology and pleonasms», F «List homogeneity», G «Numbers in text», plus any later sections present in the file — read the whole file and map every top-level section). List-homogeneity rules about bullet lists apply to manuscript Markdown too; keep them.

- [ ] **Step 4: Add the editorial pointer to `languages/ru.md`** — append one section:

```markdown
## Редакционный слой вычитки

Для корректуры, построчного редактирования и рецензий на русские тексты
загрузи нужные файлы из `../editorial/ru/`: `typography.md` перед правкой
типографики, `punctuation.md` и `grammar.md` при редакторской проверке,
`stop-words.md` и `anti-patterns.md` при стилистической правке,
`neuroslop.md` при поиске машинных маркеров. Эти нормы — значения по
умолчанию; правила проекта в `project.md` их перекрывают.
```

- [ ] **Step 5: Update the exact-tree test.** Read `tests/test_language_prose_rules.py:28-53`; add the six paths (this task adds three, Task 3 adds the rest — add all six now and create the remaining files as part of Task 3; alternatively add three now and three in Task 3; choose one and keep the test green at each task boundary by adding only what exists):

```text
resources/prose/editorial/ru/typography.md
resources/prose/editorial/ru/punctuation.md
resources/prose/editorial/ru/grammar.md
resources/prose/editorial/ru/stop-words.md
resources/prose/editorial/ru/anti-patterns.md
resources/prose/editorial/ru/neuroslop.md
```

- [ ] **Step 6: Verify links, tests, regeneration, commit**

Run: `python3 scripts/validate_distribution.py` → passes (relative links resolve).
Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` → all pass.
Run: `python3 scripts/sync_claude_distribution.py --apply && python3 scripts/sync_claude_distribution.py --check` → in sync.
Run: `git add -A plugins/creative-writing-skills/skills/creative-writing-craft tests/test_language_prose_rules.py cw && git commit -m "feat: add Russian editorial resources for typography, punctuation, grammar"`

---

### Task 3: Editorial resources II — stop-words, anti-patterns, neuroslop

**Files:**
- Create: `plugins/creative-writing-skills/skills/creative-writing-craft/resources/prose/editorial/ru/stop-words.md`
- Create: `plugins/creative-writing-skills/skills/creative-writing-craft/resources/prose/editorial/ru/anti-patterns.md`
- Create: `plugins/creative-writing-skills/skills/creative-writing-craft/resources/prose/editorial/ru/neuroslop.md`

**Interfaces:**
- Consumes: `useful/ru-text/skills/ru-text/references/{info-style,anti-patterns,addenda}.md`.
- Produces: the remaining three files of the editorial layer (must match the paths asserted in Task 2's test update if deferred).

- [ ] **Step 1: Write `stop-words.md`** from upstream `info-style.md` (366 lines). Keep: §A «Философия» (condensed to one paragraph), §B «Каталог стоп-слов» in full with all its subsections (Канцелярит, Вода, Усилители, Оценки без доказательств, Штампы, Паразиты времени, Вводные конструкции, Неопределённость и модальность) and the inflected-form note, §B.2 «Оговорка о живом регистре» (its three-record limit — this is a carve-out, mandatory), §C «Усиление слабого текста» transformation examples, §E «Числа и факты», §F «Адаптация регистра» with the register scale. Drop: §D «Структура текста» and §G «Newsroom editorial workflow principles» (non-fiction workflow framing); the «Sources» section.

- [ ] **Step 2: Write `anti-patterns.md`** from upstream `anti-patterns.md` (187 lines) plus the dash-budget rules of `addenda.md` §AD-1. Keep all severity-grouped catalogs (Канцелярит и номинализация, Vague Adjectives, Passive Voice, Sentence Bloat, False Intensifiers, Tautology/Pleonasm, Anglicisms, Archaic, Overly Formal); drop the «Critical: Typography» group (duplicated by `typography.md` — note the pointer to it instead). From AD-1 incorporate: the one-to-two em dashes per paragraph budget, parallel rows counting as one, dialogue dashes counting as none, «edit a row whole or not at all». Drop the upstream «Summary» section.

- [ ] **Step 3: Write `neuroslop.md`** from upstream `addenda.md` (1163 lines) — the AD-1..AD-18 rules (heading lines 88–1079). For each rule keep: the trigger, the detection guidance, and **all carve-outs** (e.g. AD-6 «не X, а Y» with a real antecedent is ordinary prose; AD-7 single-statement «скажу честно» vs AD-10 honesty predicated of the piece; AD-14/AD-15 charged to the document as a whole; AD-17 direct speech and comma-before-main-clause constructions are never this rule; AD-18 one or two uppercase words are deliberate emphasis, abbreviations/status cells/headings don't count). Skip AD-1's dash budget (it moved to `anti-patterns.md` in Step 2) and the «Neuroslop index» + «Two rules that govern all the others» sections only if their content is fully absorbed into the rule bodies — otherwise keep them as the file's opening sections. The file must open with: «Эти правила находят машинные маркеры в русском тексте. Каждый триггер имеет исключения; правило без проверки исключений даёт ложные срабатывания, ради устранения которых этот файл существует.»

- [ ] **Step 4: Verify and commit**

Run: `python3 scripts/validate_distribution.py` → passes.
Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` → all pass (the exact-tree test now lists all six files).
Run: `python3 scripts/sync_claude_distribution.py --apply && python3 scripts/sync_claude_distribution.py --check` → in sync.
Run: `git add plugins/creative-writing-skills/skills/creative-writing-craft cw && git commit -m "feat: add Russian editorial resources for stop-words, anti-patterns, neuroslop"`

---

### Task 4: Typography scanner — warning rules

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/prose_typography.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/prose.py`
- Test: `tests/cw_cli/test_prose_typography.py`

**Interfaces:**
- Consumes: `Finding`, `Severity` from `cwcli.findings`; `_visible_document`, `_is_prose_path`, `_prose_language` from `cwcli.checks.prose` (import the underscore names — same package).
- Produces:
  - `prose_typography.TypographyHit` frozen dataclass: `line: int`, `code: str`, `severity: str`, `message: str`, `next_action: str`.
  - `prose_typography.scan_lines(lines: Iterable[tuple[int, str]]) -> tuple[TypographyHit, ...]` — pure, Russian rules, no language argument (the caller gates).
  - Constants `CW_PROSE_100` … `CW_PROSE_103` with values `"CW-PROSE-100"` … `"CW-PROSE-103"`.
  - In `prose.py`: inside `check_prose`, for each prose-path document whose `_prose_language(...)` normalizes to `"ru"`, translate hits into `Finding(code=hit.code, severity=hit.severity, message=hit.message, path=relative_id, line=hit.line, next_action=hit.next_action)`.

The scanner receives visible (frontmatter- and fence-excluded) lines with inline code spans and markdown link targets already removed per line by the caller (`_visible_document` yields `(line_no, text)`; strip `` `...` `` spans and `](...)` targets before matching).

- [ ] **Step 1: Write the failing tests** — `tests/cw_cli/test_prose_typography.py`:

```python
import unittest

from tests.cw_cli import helpers  # noqa: F401  (sets sys.path to the CLI root)

from cwcli.checks import prose_typography


def scan(text):
    return prose_typography.scan_lines([(1, text)])


class TypographyWarningRuleTests(unittest.TestCase):
    def test_straight_double_quote_is_warning(self):
        hits = scan('Он сказал "да" и ушёл.')
        self.assertEqual([h.code for h in hits], ["CW-PROSE-100"])
        self.assertEqual(hits[0].severity, "warning")

    def test_latin_span_in_straight_quotes_is_info(self):
        hits = scan('Флаг компиляции "warning" включён.')
        self.assertEqual([h.code for h in hits], ["CW-PROSE-100"])
        self.assertEqual(hits[0].severity, "info")

    def test_spaced_hyphen_is_warning(self):
        hits = scan("Это - не тире.")
        self.assertEqual([h.code for h in hits], ["CW-PROSE-101"])

    def test_line_start_hyphen_bullet_is_not_flagged(self):
        self.assertEqual(scan("- пункт списка"), ())

    def test_three_dot_ellipsis_is_warning(self):
        hits = scan("Он замолчал...")
        self.assertEqual([h.code for h in hits], ["CW-PROSE-102"])

    def test_breakable_space_after_single_letter_word_is_warning(self):
        hits = scan("Он шёл в школу, а она осталась.")
        self.assertEqual([h.code for h in hits], ["CW-PROSE-103"])

    def test_nbsp_after_single_letter_word_is_not_flagged(self):
        self.assertEqual(scan("Он шёл в\u00a0школу."), ())

    def test_compound_hyphen_is_not_flagged(self):
        self.assertEqual(scan("Где-то там был светло-жёлтый дом."), ())

    def test_direct_speech_comma_dash_is_not_flagged(self):
        self.assertEqual(scan("«Сроки поедут», — предупредила Петрова."), ())


if __name__ == "__main__":
    unittest.main()
```

Also add one integration test class in the same file, building a minimal project through the CLI app `check prose` (mirror the manual `tempfile.TemporaryDirectory()` + `project.md` + `story/chapters/ch-001.md` fixture pattern from `tests/cw_cli/test_prose_check.py:261-273`, with `language: ru`) asserting: a straight-quote chapter yields one `CW-PROSE-100` finding at `story/chapters/ch-001.md`; an `en` project (`language: en`) yields no typography findings; `--strict` makes the warning fail the command (exit 1) while the default run exits 0.

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_prose_typography -v`
Expected: FAIL/ERROR (`No module named 'cwcli.checks.prose_typography'` for unit tests; missing codes in integration).

- [ ] **Step 3: Implement `prose_typography.py`**

```python
"""Deterministic Russian typography findings for cw check prose."""

import re
from dataclasses import dataclass
from typing import Iterable, Tuple

CW_PROSE_100 = "CW-PROSE-100"  # straight double quote
CW_PROSE_101 = "CW-PROSE-101"  # hyphen with whitespace on both sides
CW_PROSE_102 = "CW-PROSE-102"  # literal three-dot ellipsis
CW_PROSE_103 = "CW-PROSE-103"  # breakable space after single-letter word

_EDIT_NEXT_ACTION = (
    "Confirm the project's typography conventions in project.md and apply "
    "the fix through a previewed edit."
)

_STRAIGHT_QUOTE_RE = re.compile(r'"([^"]*)"|"')
_THREE_DOTS_RE = re.compile(r"(?<!\.)\.\.\.(?!\.)")
_SPACED_HYPHEN_RE = re.compile(r"(?<=[\s\u00a0])-(?=[\s\u00a0])")
# A standalone single-letter word followed by an ordinary space.
_BREAKABLE_SINGLE_RE = re.compile(
    r"(?<![А-Яа-яЁёA-Za-z0-9])[вксоуиая] (?=[А-Яа-яЁёA-Za-z0-9«„\u2014])"
)
_LATIN_LETTER = re.compile(r"[A-Za-z]")


@dataclass(frozen=True)
class TypographyHit:
    line: int
    code: str
    severity: str
    message: str
    next_action: str


def _latin_span(content: str) -> bool:
    if not content:
        return False
    letters = [ch for ch in content if ch.isalpha()]
    return bool(letters) and all(_LATIN_LETTER.match(ch) for ch in letters)


def scan_lines(lines: Iterable[Tuple[int, str]]) -> tuple[TypographyHit, ...]:
    hits = []
    for line_no, text in lines:
        for match in _STRAIGHT_QUOTE_RE.finditer(text):
            content = match.group(1) or ""
            severity = "info" if _latin_span(content) else "warning"
            hits.append(TypographyHit(
                line_no, CW_PROSE_100, severity,
                "Straight double quote; use «» (primary) or „“ (nested).",
                _EDIT_NEXT_ACTION,
            ))
        if _SPACED_HYPHEN_RE.search(text):
            hits.append(TypographyHit(
                line_no, CW_PROSE_101, "warning",
                "Hyphen with whitespace on both sides; use an em dash — "
                "with a non-breaking space before it.",
                _EDIT_NEXT_ACTION,
            ))
        if _THREE_DOTS_RE.search(text):
            hits.append(TypographyHit(
                line_no, CW_PROSE_102, "warning",
                "Literal three-dot sequence; use the ellipsis character ….",
                _EDIT_NEXT_ACTION,
            ))
        if _BREAKABLE_SINGLE_RE.search(text):
            hits.append(TypographyHit(
                line_no, CW_PROSE_103, "warning",
                "Breakable space after a single-letter word; use a "
                "non-breaking space.",
                _EDIT_NEXT_ACTION,
            ))
    return tuple(hits)
```

Notes: bullets are not flagged because `_SPACED_HYPHEN_RE` requires preceding whitespace within the line and a line-initial `-` has none; the direct-speech comma-dash line contains no rule triggers («», —, NBSP are all correct forms). Then wire into `check_prose` per the Interfaces block, stripping inline code and link targets per visible line before calling `scan_lines` (reuse the regex shapes from `prose._strip_inline_code`; the caller prepares lines, the scanner stays pure). Add the four constants and `scan_lines`/`TypographyHit` to `prose.py`'s `__all__` is **not** required — they live in their own module; only update `cwcli/checks/prose.py` imports.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_prose_typography -v` → PASS.
Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` → all pass (no regression in existing prose tests).

- [ ] **Step 5: Regenerate and commit**

Run: `python3 scripts/sync_claude_distribution.py --apply && python3 scripts/sync_claude_distribution.py --check` → in sync.
Run: `git add plugins/creative-writing-skills/skills/project-maintenance tests/cw_cli/test_prose_typography.py cw && git commit -m "feat: add Russian typography warning findings to cw check prose"`

---

### Task 5: Typography scanner — info rules and documentation

**Files:**
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/prose_typography.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/command-reference.md`
- Test: `tests/cw_cli/test_prose_typography.py` (extend)

**Interfaces:**
- Produces: constants `CW_PROSE_110` … `CW_PROSE_114` (`"CW-PROSE-110"` … `"CW-PROSE-114"`), all info severity, emitted by the same `scan_lines`.

- [ ] **Step 1: Write the failing tests** (append to `tests/cw_cli/test_prose_typography.py`):

```python
class TypographyInfoRuleTests(unittest.TestCase):
    def test_long_unseparated_digit_run(self):
        hits = scan("Он выиграл 1000000 рублей.")
        self.assertEqual([h.code for h in hits], ["CW-PROSE-110"])
        self.assertEqual(hits[0].severity, "info")

    def test_four_digit_number_not_flagged(self):
        self.assertEqual(scan("Год 1937-й."), ())  # ordinal handled by CW-PROSE-113 only if suffix present

    def test_decimal_point(self):
        hits = scan("Почти 3.14 метра.")
        self.assertEqual([h.code for h in hits], ["CW-PROSE-111"])

    def test_numero_forms(self):
        hits = scan("Договор No. 5 и приказ #7.")
        self.assertEqual([h.code for h in hits], ["CW-PROSE-112", "CW-PROSE-112"])

    def test_ordinal_suffix(self):
        hits = scan("Это был 1ый раз.")
        self.assertEqual([h.code for h in hits], ["CW-PROSE-113"])

    def test_closed_up_abbreviation(self):
        hits = scan("и т.д., и т.п.")
        self.assertEqual(
            sorted(h.code for h in hits), ["CW-PROSE-114", "CW-PROSE-114"]
        )
```

(Reconcile `test_four_digit_number_not_flagged` with CW-PROSE-113: `1937-й` is the correct form and must not be flagged by any rule; assert the empty tuple.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_prose_typography -v` → new class FAILS (codes undefined).

- [ ] **Step 3: Implement the info rules** — add to `prose_typography.py`:

```python
CW_PROSE_110 = "CW-PROSE-110"  # unseparated run of five or more digits
CW_PROSE_111 = "CW-PROSE-111"  # decimal point between digits
CW_PROSE_112 = "CW-PROSE-112"  # No. / # where № is expected
CW_PROSE_113 = "CW-PROSE-113"  # ordinal suffix like 1ый
CW_PROSE_114 = "CW-PROSE-114"  # closed-up abbreviation т.д.

_DIGIT_RUN_RE = re.compile(r"(?<!\d)\d{5,}(?!\d)")
_DECIMAL_POINT_RE = re.compile(r"(?<=\d)\.(?=\d)")
_NUMERO_RE = re.compile(r"\bNo\.\s*\d|#(?=\d)")
_ORDINAL_RE = re.compile(r"\d(?:ый|ой|ий|ая|ое|ые)\b")
_ABBREV_RE = re.compile(r"т\.(?:д|п|е|к)\.")
```

and extend `scan_lines` with the same append pattern, severity `"info"`, messages: 110 "Unseparated digit run; group digits with non-breaking spaces (1 000 000)."; 111 "Decimal point; Russian convention is a decimal comma (3,14)."; 112 "`No.`/`#`; use `№` with a non-breaking space."; 113 "Ordinal suffix; use the hyphenated form (1-й, 2-я)."; 114 "Closed-up abbreviation; use `т. д.` with a non-breaking space." — all with `_EDIT_NEXT_ACTION`. Emission granularity: rules 110, 111, and 113 use `.search()` (one hit per line, like the warnings); rules 112 and 114 use `.finditer()` (one hit per occurrence — `test_numero_forms` and `test_closed_up_abbreviation` expect two hits each on a single line).

- [ ] **Step 4: Document in `command-reference.md`.** In the `cw check prose` prose paragraphs (`skills/project-maintenance/resources/command-reference.md:30-35`), append one paragraph:

```markdown
Russian-language projects additionally receive deterministic typography
findings (`CW-PROSE-100`…`CW-PROSE-103` warnings for straight quotes,
spaced hyphens, three-dot ellipses, and breakable spaces after
single-letter words; `CW-PROSE-110`…`CW-PROSE-114` info findings for digit
grouping, decimal points, `№`, ordinals, and abbreviation spacing). They
report typographic norms as warnings the project's `project.md`
conventions may override; they never fail `check all` without `--strict`.
```

- [ ] **Step 5: Run all tests, regenerate, commit**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` → all pass.
Run: `python3 scripts/sync_claude_distribution.py --apply && python3 scripts/sync_claude_distribution.py --check` → in sync.
Run: `git add plugins/creative-writing-skills/skills/project-maintenance cw && git commit -m "feat: add Russian typography info findings and document the family"`

---

### Task 6: Prose-shape metrics

**Files:**
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/prose.py`
- Test: `tests/cw_cli/test_prose_shape.py`

**Interfaces:**
- Produces on `ProseMetrics` (append fields, keep dataclass frozen and field order after existing `skipped_metrics`):
  - `sentence_length_p90: int` (0 when no sentences; nearest-rank percentile index `sorted_values[max(0, min(n - 1, ceil(0.90 * n) - 1))]`),
  - `sentence_length_step: float` (mean absolute difference between adjacent sentence lengths in original order; 0.0 when fewer than two sentences),
  - `em_dash_count: int` (count of `U+2014` or `U+2013` with whitespace or `U+00A0` on both sides, on the stripped prose text),
  - `subordination_mean: float | None` (mean subordinating-conjunction/pronoun hits per sentence; `None` unless the normalized language is `ru`),
  - `intensifier_count: int | None` (`None` unless `ru`).
- Produces in the `CW-PROSE-090` details dict: the same five keys (`sentence_length_p90`, `sentence_length_step`, `em_dash_count`, `subordination_mean`, `intensifier_count`) alongside the existing keys.

Closed word lists (adapted from `useful/ru-text/tools/measure-prose-shape.py:67-97`):

```python
_RU_SUBORDINATION_RE = re.compile(
    r"(?<![\w-])(?:что|чтобы|который|которая|которое|которые|которых|которым|"
    r"которого|которой|если|когда|пока|потому|поскольку|так как|хотя|несмотря|"
    r"чем|будто|словно|ибо|дабы|кто|где|куда|откуда|зачем|почему|сколько|"
    r"насколько|пусть|раз)(?![\w-])",
    re.IGNORECASE,
)
_RU_INTENSIFIER_RE = re.compile(
    r"(?<![А-Яа-яЁё-])(?:честно|реально|правда|прямо|вообще|совсем|очень|крайне|"
    r"весьма|довольно|просто|буквально|разумеется|конечно|пожалуй|кажется|"
    r"похоже|скорее|вроде|наверное|видимо|как бы|всё же|всё-таки|как раз|"
    r"именно)(?![А-Яа-яЁё-])",
    re.IGNORECASE,
)
_SPACED_DASH_COUNT_RE = re.compile(r"(?<=[\s\u00a0])[\u2014\u2013](?=[\s\u00a0])")
```

**Abbreviation-guard decision (binds this task):** do NOT change `_SENTENCE_SPLIT_RE` or `_sentences`. The legacy whitespace-boundary semantics are pinned by `test_sentence_splitting_matches_legacy_whitespace_boundary` (`tests/cw_cli/test_prose_check.py:123-131`) and the module docstring contract at `prose.py:491`. The flattening use case compares two runs of the same text, so a constant «т. д.» split bias cancels in the delta — the upstream tool's own argument. Record this rationale as a comment above the new lists.

- [ ] **Step 1: Write the failing tests** — `tests/cw_cli/test_prose_shape.py`:

```python
import unittest

from tests.cw_cli import helpers  # noqa: F401

from cwcli.checks import prose


class ProseShapeMetricTests(unittest.TestCase):
    def test_p90_and_step_on_known_lengths(self):
        text = "Одно короткое. " + "Здесь предложение заметно длиннее, с оборотом. " * 4
        m = prose.analyze_prose(text, language="ru")
        lengths = sorted(m.sentence_lengths)
        n = len(lengths)
        self.assertEqual(m.sentence_length_p90, lengths[min(n - 1, int(0.9 * n))])
        step = sum(
            abs(m.sentence_lengths[i] - m.sentence_lengths[i + 1])
            for i in range(len(m.sentence_lengths) - 1)
        ) / (len(m.sentence_lengths) - 1)
        self.assertAlmostEqual(m.sentence_length_step, step)

    def test_single_sentence_has_zero_step(self):
        m = prose.analyze_prose("Одно целое предложение.", language="ru")
        self.assertEqual(m.sentence_length_step, 0.0)
        self.assertEqual(m.sentence_length_p90, m.sentence_lengths[0])

    def test_em_dash_count(self):
        m = prose.analyze_prose("Он сказал — и замолчал. Она ответила — и ушла.", language="ru")
        self.assertEqual(m.em_dash_count, 2)

    def test_ru_only_fields_are_none_for_english(self):
        m = prose.analyze_prose("He said that it was very odd. Really odd.", language="en")
        self.assertIsNone(m.subordination_mean)
        self.assertIsNone(m.intensifier_count)
        self.assertEqual(m.em_dash_count, 0)

    def test_ru_subordination_and_intensifiers(self):
        m = prose.analyze_prose(
            "Он знал, что она уйдёт, потому что очень устала. Честно, это было странно.",
            language="ru",
        )
        self.assertGreaterEqual(m.subordination_mean, 1.0)
        self.assertEqual(m.intensifier_count, 2)  # «очень» and «Честно»


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_prose_shape -v`
Expected: ERROR — `ProseMetrics` has no attribute `sentence_length_p90`.

- [ ] **Step 3: Implement** — add the five fields to `ProseMetrics` (with `None` defaults where nullable so all existing constructor sites keep working, then populate them in `analyze_prose`; note `sentence_length_p90: int = 0`, `sentence_length_step: float = 0.0`, `em_dash_count: int = 0` as defaulted fields appended after `skipped_metrics`), compute them in `analyze_prose` from `sentence_list`/`prose_text` per the Interfaces definitions, and add the five keys to the `CW-PROSE-090` details dict in `check_prose` (`prose.py:294-335`). Add the abbreviation-guard decision comment above the new regexes.

- [ ] **Step 4: Run tests, regenerate, commit**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` → all pass (existing `ProseMetrics` consumers unaffected; if any test constructs `ProseMetrics` positionally, update those call sites in the same change).
Run: `python3 scripts/sync_claude_distribution.py --apply && python3 scripts/sync_claude_distribution.py --check` → in sync.
Run: `git add plugins/creative-writing-skills/skills/project-maintenance tests/cw_cli/test_prose_shape.py cw && git commit -m "feat: add prose-shape flattening metrics to cw check prose"`

---

### Task 7: `dialogue_audit.py` port

**Files:**
- Create: `plugins/creative-writing-skills/skills/creative-writing-craft/resources/dialogue_audit.py`
- Test: `tests/test_dialogue_audit.py`

**Interfaces:**
- Produces (module is a standalone script, loaded by tests via `importlib.util.spec_from_file_location` from the skill resource path):

```python
@dataclass(frozen=True)
class DialogueStats:
    total_lines: int              # non-empty prose lines
    dialogue_lines: int           # lines detected as dialogue (ru dash or quotes)
    dialogue_ratio: float
    attribution_lines: int        # dialogue lines carrying an attribution tag
    attribution_ratio: float      # attribution_lines / dialogue_lines (0.0 if none)
    max_same_speaker_run: int     # longest run of consecutive attributed lines with one name
    speaker_overlap: tuple[tuple[str, str, float], ...]  # top Jaccard pairs, desc, max 5

def detect_language(text: str) -> str     # "ru" when Cyrillic letter share > 0.3, else "en"
def audit_dialogue(text: str, *, language: str) -> DialogueStats
def main(argv: list[str] | None = None) -> int   # 0 success, 2 usage/IO errors; no exit-1 path
```

Attribution patterns (deterministic core of the upstream TS scripts):

```python
# Attribution = verb + capitalized name at end of line; apply per line.
_RU_ATTRIBUTION_RE = re.compile(
    r"(?:сказал[а]?|спросил[а]?|ответил[а]?|произнёс|произнесла|"
    r"прошептал[а]?|добавил[а]?|заметил[а]?|выдохнул[а]?|"
    r"пробормотал[а]?)\s+([А-ЯЁ][А-Яа-яЁё-]+)\s*\.?\s*$")
_EN_ATTRIBUTION_RE = re.compile(
    r"(?:said|asked|replied|whispered|added|remarked|muttered)\s+"
    r"([A-Z][A-Za-z-]+)\s*\.?\s*$")
_RU_DIALOGUE_LINE_RE = re.compile(r"^\s*[—–]\s*\S|«[^»]+»")
_EN_DIALOGUE_LINE_RE = re.compile(r'^\s*"[^"]+"')
```

Speaker vocabulary for the overlap metric: lowercase words of length > 3 from each speaker's attributed lines; Jaccard = |intersection| / |union|; report only pairs where both speakers have at least 3 attributed lines; sort descending, cap at 5; ties broken by name pair alphabetical order.

- [ ] **Step 1: Write the failing tests** — `tests/test_dialogue_audit.py`:

```python
import importlib.util
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = (_REPO / "plugins/creative-writing-skills/skills/creative-writing-craft"
           / "resources/dialogue_audit.py")


def load_module():
    spec = importlib.util.spec_from_file_location("dialogue_audit", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DialogueAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()

    def test_ru_dialogue_counts_and_attribution(self):
        text = (
            "— Приходи вовремя, — сказал Иван.\n"
            "— Я никогда не опаздываю, — ответила Мария.\n"
            "Описание места действия без реплик.\n"
            "— Учти это, — добавил Иван.\n"
        )
        stats = self.mod.audit_dialogue(text, language="ru")
        self.assertEqual(stats.total_lines, 4)
        self.assertEqual(stats.dialogue_lines, 3)
        self.assertEqual(stats.attribution_lines, 3)
        self.assertEqual(stats.attribution_ratio, 1.0)
        self.assertEqual(stats.max_same_speaker_run, 1)

    def test_same_speaker_run(self):
        text = (
            "— Слушай, — сказал Иван.\n"
            "— Что? — спросил Иван.\n"
            "— Ничего, — ответил Иван.\n"
        )
        stats = self.mod.audit_dialogue(text, language="ru")
        self.assertEqual(stats.max_same_speaker_run, 3)

    def test_detect_language(self):
        self.assertEqual(self.mod.detect_language("Он пошёл домой"), "ru")
        self.assertEqual(self.mod.detect_language("He went home"), "en")

    def test_en_attribution(self):
        text = '"Come here," said John.\n"Why?" asked Mary.\n'
        stats = self.mod.audit_dialogue(text, language="en")
        self.assertEqual(stats.attribution_lines, 2)
        self.assertEqual(stats.max_same_speaker_run, 1)

    def test_main_returns_two_on_missing_file(self):
        self.assertEqual(self.mod.main([str(_REPO / "no-such-file.md")]), 2)
        self.assertEqual(self.mod.main([]), 2)

    def test_main_returns_zero_and_prints_json(self):
        target = _REPO / "test" / "_dialogue_fixture.md"
        target.parent.mkdir(exist_ok=True)
        target.write_text("— Привет, — сказал Иван.\n", encoding="utf-8")
        try:
            import contextlib, io, json
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = self.mod.main([str(target), "--format", "json"])
            self.assertEqual(code, 0)
            payload = json.loads(buffer.getvalue())
            self.assertEqual(payload["dialogue_lines"], 1)
        finally:
            target.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
```

(`test/` is git-ignored per `.gitignore:2`, so the fixture leaves no tree noise. If the `test/` directory does not exist in this checkout, the `mkdir(exist_ok=True)` creates it — untracked.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_dialogue_audit -v`
Expected: ERROR — file not found.

- [ ] **Step 3: Implement `dialogue_audit.py`** per the Interfaces block: stdlib only (`argparse`, `json`, `re`, `sys`, `dataclasses`, `pathlib`), UTF-8 reading, docstring stating it measures dialogue mechanics and renders no verdicts, `main` printing a compact human summary by default and JSON with `--format json`, exit 0/2 only.

- [ ] **Step 4: Run tests, regenerate, commit**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` → all pass.
Run: `python3 scripts/sync_claude_distribution.py --apply && python3 scripts/sync_claude_distribution.py --check` → in sync.
Run: `git add plugins/creative-writing-skills/skills/creative-writing-craft/resources/dialogue_audit.py tests/test_dialogue_audit.py cw && git commit -m "feat: add dialogue audit script to creative-writing-craft"`

---

### Task 8: `humor.md` craft resource

**Files:**
- Create: `plugins/creative-writing-skills/skills/creative-writing-craft/resources/humor.md`

**Interfaces:**
- Consumes: `useful/creative/humor/joke-engineering/SKILL.md` (316 lines, MIT, jwynia).
- Produces: English imperative craft reference; referenced later by Task 10's index wiring.

- [ ] **Step 1: Write `humor.md`** with this structure, porting all upstream content (nine system properties table with failure modes, states H1–H6 with symptoms/key question/intervention, the diagnostic process, density-enhancement patterns, compression guidance, anti-patterns, and the honest script-boundary note rewritten as "what deterministic tools cannot see"):

```markdown
# Humor Engineering

Diagnose and improve humor as an engineerable connection system... [intro:
humor emerges from creating and resolving connections; when a joke fails, a
system property is miscalibrated]

## The Nine System Properties
[table ported verbatim in content: Connection Distance, Connection Density,
Resolution Satisfaction, Specificity Optimization, Irony Layering, Audience
Co-Creation, Compression Optimization, Connection Resilience, Authenticity
Resonance — each with description and failure mode]

## Diagnostic States
### H1: Too Obvious ...
[H1 through H6, each: Symptoms / Key Question / Intervention]

## Diagnostic Process
[the 6-step listen-trace-measure-identify-recommend-verify process]

## Density and Compression Patterns
[connection-density enhancement patterns; compression-to-word-ratio guidance]

## Limits of Mechanical Detection
[what counts and scripts cannot see — ported from the upstream honesty notes;
cross-reference `$creative-writing-modes` for comedy production modes]
```

Keep examples; add one Russian-prose example of an H4 (over-explained) joke fix to match the plugin's bilingual audience.

- [ ] **Step 2: Verify links and commit**

Run: `python3 scripts/validate_distribution.py` → passes.
Run: `git add plugins/creative-writing-skills/skills/creative-writing-craft/resources/humor.md && git commit -m "feat: add humor engineering craft reference"` (regeneration happens in Task 10 with the index wiring; `--check` drift at this boundary is acceptable only if the repo's release gate is not invoked — prefer running `--apply` now and including `cw` in the commit).

---

### Task 9: `dialogue.md` craft resource

**Files:**
- Create: `plugins/creative-writing-skills/skills/creative-writing-craft/resources/dialogue.md`

**Interfaces:**
- Consumes: `useful/creative/fiction/character/dialogue/SKILL.md`.
- Produces: English imperative craft reference that points to `dialogue_audit.py` (Task 7) for the deterministic measurements.

- [ ] **Step 1: Write `dialogue.md`** porting: the three subtext layers (surface text / what characters actually want / what they hide), flat-dialogue and same-voice diagnosis with their diagnostic states, the audit method, and the improvement interventions. Replace the upstream TypeScript script instructions with:

````markdown
## Deterministic Measurements

Run the bundled audit for counts a reader can re-derive:

```bash
python3 resources/dialogue_audit.py story/chapters/ch-001.md --format json
```

It reports speaker-tag ratio, the longest same-speaker run, dialogue-line
ratio, and cross-speaker vocabulary overlap. High overlap between speakers
is a same-voice signal, not a verdict: interpret it against the scene's
intent. Subtext, timing, and voice authenticity require judgment.
````

- [ ] **Step 2: Verify links and commit**

Run: `python3 scripts/validate_distribution.py` → passes (the fenced `python3 resources/dialogue_audit.py` line is inside a fence; the backtick path checker ignores fenced content — confirm no unfenced relative paths to the script exist outside fences, or link it as `` `dialogue_audit.py``` plain text).
Run: `git add plugins/creative-writing-skills/skills/creative-writing-craft/resources/dialogue.md && git commit -m "feat: add dialogue craft reference with deterministic audit hook"` (include regenerated `cw` if applying now, as in Task 8).

---

### Task 10: scene-sequencing, endings, character-arc + craft index wiring

**Files:**
- Create: `plugins/creative-writing-skills/skills/creative-writing-craft/resources/scene-sequencing.md`
- Create: `plugins/creative-writing-skills/skills/creative-writing-craft/resources/endings.md`
- Create: `plugins/creative-writing-skills/skills/creative-writing-craft/resources/character-arc.md`
- Modify: `plugins/creative-writing-skills/skills/creative-writing-craft/SKILL.md:19-29` (prose-stack conditional step) and `:44-48` (resource index bullets)

**Interfaces:**
- Consumes: `useful/creative/fiction/structure/{scene-sequencing,endings}/SKILL.md`, `useful/creative/fiction/character/character-arc/SKILL.md`, and the resources from Tasks 2–3, 8–9.
- Produces: the completed `creative-writing-craft` resource index.

- [ ] **Step 1: Write `scene-sequencing.md`** porting Swain's framework: scene (goal → conflict → disaster) and sequel (reaction → dilemma → decision), pacing diagnosis via alternation, genre-dependent ratio guidance, and the state diagnostics. Add one note: scene records live in `kb/continuity/scenes/` per the project contract; this reference governs prose rhythm, not record keeping.

- [ ] **Step 2: Write `endings.md`** porting ending anatomy, resolution types, subplot-resolution diagnosis, and the improvement interventions. For setup/payoff tracking, state: promises are tracked structurally in `kb/continuity/promises.md` and checked by `cw check continuity`; this reference governs the literary design of payoff, not the bookkeeping.

- [ ] **Step 3: Write `character-arc.md`** porting lie/want/need, the positive/negative/flat arc polarities with their beat shapes, and the arc-troubleshooting states. Cross-reference `$character-sim` for testing an arc's voice consistency and `$reader-sim` for testing whether the arc lands.

- [ ] **Step 4: Wire the SKILL.md index.** In the "Load only the other resource needed for the task" bullet list (`SKILL.md:44-48`), append:

```markdown
- `resources/humor.md` — engineering jokes and comedic passages as connection systems.
- `resources/dialogue.md` — subtext layers, same-voice diagnosis, and the deterministic dialogue audit.
- `resources/scene-sequencing.md` — scene/sequel structure and pacing rhythm.
- `resources/endings.md` — ending anatomy, resolution types, and payoff design.
- `resources/character-arc.md` — arc polarities, lie/want/need, and arc troubleshooting.
```

And in the prose stack resolution (after the language step at `SKILL.md:19-29`), insert one numbered step: "for `ru`-language projects during proofreading, line editing, or review passes: the applicable files under `resources/prose/editorial/ru/`."

- [ ] **Step 5: Verify, regenerate, commit**

Run: `python3 scripts/validate_distribution.py` → passes.
Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` → all pass (the SKILL.md edit must not trip the worker-prompt or distribution contract tests).
Run: `python3 scripts/sync_claude_distribution.py --apply && python3 scripts/sync_claude_distribution.py --check` → in sync.
Run: `git add plugins/creative-writing-skills/skills/creative-writing-craft cw && git commit -m "feat: add scene-sequencing, endings, character-arc references and wire the craft index"`

---

### Task 11: `key-moments.md` planning resource

**Files:**
- Create: `plugins/creative-writing-skills/skills/story-planning/resources/key-moments.md`
- Modify: `plugins/creative-writing-skills/skills/story-planning/SKILL.md` (add one bullet to its resources list, mirroring how `brainstorming.md`/`story-architecture.md` are listed)

**Interfaces:**
- Consumes: `useful/creative/fiction/structure/key-moments/SKILL.md`.
- Produces: planning input for the `outliner` and `brainstormer` workers (both already load `story-planning`).

- [ ] **Step 1: Write `key-moments.md`** porting: the essential-emotional-moments method, the crossing with elemental genres, the worked example, and the selection states. Frame outputs as provisional planning artifacts for `work/plans/` subject to author confirmation.

- [ ] **Step 2: Wire and verify** — add the SKILL.md bullet; run `python3 scripts/validate_distribution.py`; run the full suite; `--apply`/`--check`; commit `git add plugins/creative-writing-skills/skills/story-planning cw && git commit -m "feat: add key-moments planning reference to story-planning"`.

---

### Task 12: Worldbuilding generators pack

**Files:**
- Create: `plugins/creative-writing-skills/skills/world-creation/resources/generators/{belief,economic,governance,settlement,metabolic,systemic,oblique}.md`
- Modify: `plugins/creative-writing-skills/skills/world-creation/SKILL.md` (add a generators pointer)

**Interfaces:**
- Consumes: `useful/creative/fiction/worldbuilding/{belief-systems,economic-systems,governance-systems,settlement-design,metabolic-cultures,systemic-worldbuilding,oblique-worldbuilding}/SKILL.md` (all prose-only).
- Produces: the generative side complementing world-creation's consequence-grilling; all outputs are provisional world knowledge pending author confirmation.

- [ ] **Step 1: Write the seven generator files**, one per upstream skill, each keeping: the core principle, the full parameter tables/categories, the typology or pattern inventory, the cliché-avoidance notes, and the worked example where present. Each file opens with the boundary note: "Generator output is provisional: proposals become world knowledge only after author confirmation, and world-creation work never edits manuscript prose." Specifics: `belief.md` keeps the 10 religion-design principles and parameter categories; `economic.md` the currency/trade/resource parameters; `governance.md` the polity design matrix and political behavior patterns; `settlement.md` the layered-development and spatial-logic method; `metabolic.md` the closed-loop culture axes and matter-as-identity framing; `systemic.md` the consequence-cascade method with its worked example; `oblique.md` the limited-documentary-perspective technique (epigraphs, in-world documents).

- [ ] **Step 2: Wire the SKILL.md pointer** — add to `world-creation/SKILL.md` near its existing `references/world-file-format.md` pointer: a line introducing `resources/generators/` as the parameter-level generators to draw on when proposing world structure, subject to the confirmation boundary.

- [ ] **Step 3: Verify, regenerate, commit**

Run: `python3 scripts/validate_distribution.py` → passes.
Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` → all pass.
Run: `python3 scripts/sync_claude_distribution.py --apply && python3 scripts/sync_claude_distribution.py --check` → in sync.
Run: `git add plugins/creative-writing-skills/skills/world-creation cw && git commit -m "feat: add worldbuilding generator references to world-creation"`

---

### Task 13: Worker wiring, CHANGELOG, full verification

**Files:**
- Modify: `plugins/creative-writing-skills/skills/creative-writing-muse/resources/workers/editor.md` (one sentence inside `## Work`)
- Modify: `CHANGELOG.md` (`## [Unreleased]` → Added bullets)

**Interfaces:**
- Consumes: all prior tasks.
- Produces: release-ready tree.

- [ ] **Step 1: Extend the editor worker prompt.** In `editor.md`'s `## Work` section, after the existing `$creative-writing-craft` mention, add: "For humor or dialogue passes, load the matching `creative-writing-craft` resource (`resources/humor.md`, `resources/dialogue.md` with its deterministic audit)." Constraints: the file must still start with `# Function` and contain exactly one each of `## Required inputs`, `## Return shape`, `## Access boundary` (`tests/test_distribution.py:192-207`); `registry.json` is NOT modified (its `(access, skills)` tuples are pinned by `EXPECTED_WORKER_CONFIG` at `tests/test_distribution.py:59-70`).

- [ ] **Step 2: Update the CHANGELOG.** Under `## [Unreleased]` add an `### Added` section:

```markdown
### Added

- Added the Russian editorial layer to `creative-writing-craft`: curated
  typography, punctuation, grammar, stop-word, anti-pattern, and neuroslop
  references adapted from ru-text, loaded for proofreading and line-editing
  passes on `ru`-language projects.
- Added deterministic Russian typography findings (`CW-PROSE-100`…`114`) to
  `cw check prose`, gated on the project language and reported as
  warnings/info that project conventions may override.
- Added prose-shape flattening metrics (sentence-length p90, adjacent step,
  em-dash count, Russian subordination and intensifier counts) to
  `cw check prose` output for before/after edit comparison.
- Added craft references to `creative-writing-craft`: humor engineering,
  dialogue (with the deterministic `dialogue_audit.py` script),
  scene sequencing, endings, and character arcs.
- Added the key-moments planning reference to `story-planning` and seven
  worldbuilding generator references to `world-creation`.
```

- [ ] **Step 3: Full verification loop**

Run all six, all must pass:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
python3 scripts/validate_distribution.py
python3 scripts/vendor_generic_skills.py --check
python3 scripts/sync_claude_distribution.py --apply
python3 scripts/sync_claude_distribution.py --check
python3 scripts/create_skill_zips.py
```

- [ ] **Step 4: Commit**

Run: `git add plugins/creative-writing-skills/skills/creative-writing-muse CHANGELOG.md cw zips && git commit -m "feat: wire editor worker to craft diagnostics and prepare 0.8.0 changelog"`

---

### Task 14: Release 0.8.0

**Files:**
- Modify: `CHANGELOG.md` (Unreleased → `## [0.8.0] - <release date>`)

**Interfaces:**
- Consumes: Task 13's verified tree.

- [ ] **Step 1: Merge to `main`** — the release command requires a clean `main` branch; merge/PR this branch first (the user performs or approves the merge).

- [ ] **Step 2: Prepare the changelog** — retitle `## [Unreleased]` to `## [0.8.0] - <date>` following the `## [0.7.0] - 2026-08-29` format (`CHANGELOG.md:5`), leaving a fresh empty `## [Unreleased]` above it; commit `docs: prepare 0.8.0 changelog`.

- [ ] **Step 3: Release**

Run: `python3 scripts/release.py minor` (regenerates derived metadata, runs tests and distribution checks, commits and tags; add `--push` only when explicitly requested).

---

## Self-Review Notes

- **Spec coverage:** editorial corpus (Tasks 2–3), typography findings (4–5), prose-shape metrics (6), dialogue port (7), humor (8), dialogue reference (9), scene-sequencing/endings/character-arc (10), key-moments (11), generators (12), attribution (1), wiring/docs (10–13), deferred queue (spec-only, no task needed), release (14). The abbreviation-guard evaluation is decided in Task 6 with rationale. No spec requirement is taskless.
- **Type consistency:** `TypographyHit(line, code, severity, message, next_action)` used identically in Tasks 4–5; `ProseMetrics` field names in Task 6 match the details-dict keys; `DialogueStats`/`audit_dialogue`/`main` signatures identical between definition and tests.
- **Known follow-ups folded in:** `tests/test_language_prose_rules.py` exact-tree update (Task 2), worker-registry test pinning (Task 13), `test/` git-ignore for the dialogue fixture (Task 7).
