---
name: structured-artifact
description: Build a navigable static HTML page when a reader needs to explore structured information.
---

# Structured Artifact

Use `$information-hierarchy` to decide what the reader should see first.
Build a static page that opens directly in a browser; add child pages only
when a single page becomes hard to navigate. Prefer native HTML and CSS for
simple interactions. Use external libraries only for a feature the artifact
actually needs, and bundle them when offline use is required.

Check the rendered page at a narrow width, follow its links, and try every
control. Keep the main finding visible without interaction. For a specific
pattern, read only the relevant resource:

- `resources/layout-and-theme.md` for layout and color.
- `resources/multi-page-site.md` for child pages and navigation.
- `resources/diagrams.md` for relationship diagrams.
- `resources/data-table.md` or `resources/data-chart.md` for data.
- `resources/timeline.md`, `resources/tree-and-toc.md`, or
  `resources/card-grid.md` for browsing sequences or collections.
- `resources/diff-view.md` for comparing two versions.
- `resources/mockups.md` for a layout proposal.

Use `resources/experimental-react-flow.md` only when direct node interaction
is essential and static diagrams cannot serve the task.
