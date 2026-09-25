---
name: qi-layer
description: Write concise project instructions and nearby reference context when an existing area needs durable agent guidance.
---

# Project Context

Use `$project-bootstrap` to find the project's instruction entrypoint before
editing. Preserve its chosen layout. Add or change guidance when it prevents
a real mistake in the area being worked on; ordinary code facts belong in
code or nearby reference docs.

In standing instructions, state the area's purpose, key boundaries, and
decisions an agent needs before acting. Put detailed contracts and rationale
in the project's existing reference location, such as `.context/CONTEXT.md`.
Place shared guidance at the closest common parent instead of repeating it in
sibling files. Keep links relative and check that they resolve.

Update instructions with the relevant source change. Remove stale or
duplicated text. Do not create an instruction file, mirror, or `.context/`
directory just to complete a template.
