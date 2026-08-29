# AGENTS.md

Guidance for contributors working in this repository.

## Repository Model

This is a Codex-first creative-writing plugin. The canonical installable
runtime is `plugins/creative-writing-skills/` and the canonical manifest is
`plugins/creative-writing-skills/.codex-plugin/plugin.json`.

`cw/` is committed generated output for Claude Code, Cowork, Claude.ai, and
ZCode. It is never an independent source tree and must not be hand-edited.
Make every runtime change in the canonical plugin first, then regenerate `cw/`.

The repository marketplace is `.agents/plugins/marketplace.json`. The exact
31-skill inventory and authored/vendored partition are declared in
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

Vendored generic skills are pinned snapshots with attribution in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
Use `python3 scripts/vendor_generic_skills.py --check` to verify them and the
script's apply mode only when intentionally updating the pinned inputs.

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
python3 scripts/vendor_generic_skills.py --check
python3 scripts/sync_claude_distribution.py --check
python3 scripts/create_skill_zips.py
```

Archive generation reads only the generated `cw/skills/` tree, requires an
exact match with the configured 31-skill inventory, and writes deterministic
archives under `zips/`.

## Releases

The version in the canonical Codex plugin manifest is the only version source.
Use:

```bash
python3 scripts/release.py patch
python3 scripts/release.py minor --push
```

The release command requires a clean `main` branch, regenerates derived Claude
and ZCode metadata, runs tests and distribution checks, then commits and tags.
It pushes only when `--push` is explicit.

## Writing Conventions

- Preserve source tagging: untagged text is author-stated, `<AI>...</AI>` is an
  AI suggestion, and `<hidden>...</hidden>` is author-only information.
- Cite chapter evidence as `Chapter 3: Scene where X discovers Y` and project
  documents by path, such as `magic-system.md`.
- Write style guides as imperative model instructions with examples.
- Preserve author confirmation boundaries: provisional ideas do not become
  canon, and world-creation work does not edit manuscript prose.
