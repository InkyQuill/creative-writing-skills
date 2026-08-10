# Worldbuilding File Format

## Structure

```md
# {Title}
---
status: canon
updated: YYYY-MM-DD
related:
  - Other File
---

## {Section}

Concise setting facts.
```

## Rules

- Use the title for the topic, species, institution, force, place, or concept.
- Keep metadata brief. Use `status`, `updated`, `related`, or `notes` when useful.
- Prefer durable facts over discussion notes.
- Keep sections focused. Split only when it helps future lookup.
- Use `## Open Questions` only when the user explicitly wants unresolved questions recorded.
- Avoid writing rejected alternatives unless the rejection itself is important canon.
- If an existing file lacks this structure, normalize only the file being edited and only as much as needed for the current change.

## Concision Standard

Each file should be short enough to scan but complete enough to preserve needed facts. If a topic grows into several unrelated concerns, propose splitting it into separate files before doing so.

## Index Files

Use `_index.md`, `index.md`, `INDEX.md`, or `README.md` as navigational maps for folders that contain multiple durable files.

Good index files:

- summarize the folder's scope in one short overview when useful
- link to topic files with relative Markdown links
- use compact tables or bullets
- keep descriptions brief and discoverability-focused
- avoid duplicating detailed canon from topic files

When adding or retitling a durable topic file, update the nearest relevant index after the user confirms the file change. Do not create a new index unless the folder has several durable files and the user confirms that an index would help.
