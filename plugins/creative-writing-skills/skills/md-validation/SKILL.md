---
name: md-validation
description: Check links and diagrams in Markdown that is being delivered or changed.
---

# Markdown Validation

For changed Markdown, check relative links against the files they should
reach. If a diagram is present, validate it with an available Mermaid parser
or renderer and inspect the result when layout matters. Report the specific
broken link or diagram; do not demand a new documentation structure.

For Mermaid syntax pitfalls, read `resources/mermaid-authoring.md` only when
writing or fixing a diagram.
