# Creative Writing Skills — Agent Skills Distribution

This folder is generated output. Do not edit it by hand; regenerate it with
`python3 scripts/sync_claude_distribution.py --apply` from the repository.

These skills run on agent platforms that load Agent Skills directories
directly instead of a plugin marketplace, currently Pi and Cursor.

## Install for Pi

Copy or symlink each directory under `skills/` into `~/.agents/skills/` for
all projects, or into `.agents/skills/` inside a writing project. Pi loads
each `SKILL.md` automatically and can force-load one with `/skill:<name>`.

## Install for Cursor

Copy the `skills/` entries into `~/.cursor/skills/` (or `.cursor/skills/`
inside a project, or the same `.agents/skills/` locations), and copy
`agents/*.md` into `~/.cursor/agents/` (or `.cursor/agents/`) to add the muse
and specialist subagents.

The muse orchestrates inline when subagents are unavailable, so the skills
tree alone also works on platforms without a subagent tool.
