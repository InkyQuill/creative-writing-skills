# Mermaid authoring notes

Give nodes short, distinct IDs. Quote labels containing punctuation or HTML,
and use `<br/>` only where the chosen diagram renderer supports it. Avoid a
bare lowercase `end` in flowcharts; it can be read as a subgraph terminator.
Put a space after an edge marker before IDs beginning with `o` or `x`.

Prefer the renderer's theme colors. If custom fills are necessary, set text
and stroke colors with enough contrast, and do not rely on color alone to
communicate meaning. Render the finished diagram in the target environment;
source that looks valid can still be unreadable.
