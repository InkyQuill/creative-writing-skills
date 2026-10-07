# AGENTS.md

Guidance for contributors working in this repository.

## Repository Model

This is a Codex-first creative-writing plugin. The canonical installable
runtime is `plugins/creative-writing-skills/` and the canonical manifest is
`plugins/creative-writing-skills/.codex-plugin/plugin.json`.

`cw/` is committed generated output for Claude Code, Cowork, Claude.ai, and
ZCode. It is never an independent source tree and must not be hand-edited.
Generated skills do not need separate content or code review: review their
canonical sources instead. Keep the generator synchronization checks; they
verify that the generated distribution matches those reviewed sources.
Make every runtime change in the canonical plugin first, then regenerate `cw/`.

The repository marketplace is `.agents/plugins/marketplace.json`. The exact
36-skill inventory is declared in
`config/distribution.json`.

## Canonical Content

- Skills live in `plugins/creative-writing-skills/skills/<name>/`.
- Every skill uses `name` and `description` YAML frontmatter.
- Skill resources stay inside their skill directory and use relative links.
- The muse skill owns author-facing orchestration and synthesis.
- Reusable worker prompts and their registry live under
  `skills/creative-writing-muse/resources/workers/` inside the plugin.
- Codex skill references use `$skill-name` outside fenced examples.
- `agents/openai.yaml` is Codex UI metadata and is excluded from generated
  Claude runtime and Claude.ai archives.

All skills are maintained in this repository. Some began as adaptations;
their provenance remains in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
Do not refresh them from an external checkout.

## Generated Claude and ZCode Distribution

After editing canonical skills, worker resources, or the plugin manifest, run:

```bash
python3 scripts/sync_claude_distribution.py --apply
python3 scripts/sync_claude_distribution.py --check
```

The generator derives `cw/skills/`, `cw/agents/`,
`cw/.claude-plugin/plugin.json`, `cw/.zcode-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, and the ZCode root `marketplace.json`. It
performs the supported Codex-to-Claude vocabulary transformations and fails on
constructs it cannot translate. ZCode reads the Claude-compatible `cw/` tree
through its own manifest and repository-root marketplace. Never patch
generated drift by editing `cw/`, `marketplace.json`, or the generated
manifests.

## Validation

Use repository-local Python entry points:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 scripts/validate_distribution.py
python3 scripts/sync_claude_distribution.py --check
python3 scripts/create_skill_zips.py
```

Archive generation reads only the generated `cw/skills/` tree, requires an
exact match with the configured 36-skill inventory, and writes deterministic
archives under `zips/`.

## Releases

The canonical Codex plugin manifest remains the runtime version source.
Release-please updates it alongside its bookkeeping mirrors (`version.txt` and
`.release-please-manifest.json`) in one release PR; CI checks that they agree.
Use Conventional Commit titles for merged work. Do not manually bump versions,
create release tags, or use `scripts/release.py` while automation is configured.

The release workflow runs the ordinary generator on the release PR, explicitly
dispatches CI, and publishes verified skill archives after that PR merges. Never
patch generated release metadata directly. See [`docs/releases.md`](docs/releases.md)
for repository setup and retries against an exact commit/tag.

## Writing Conventions

- Preserve source tagging: untagged text is author-stated, `<AI>...</AI>` is an
  AI suggestion, and `<hidden>...</hidden>` is author-only information.
- Cite chapter evidence as `Chapter 3: Scene where X discovers Y` and project
  documents by path, such as `magic-system.md`.
- Write style guides as imperative model instructions with examples.
- Preserve author confirmation boundaries: provisional ideas do not become
  canon, and world-creation work does not edit manuscript prose.
