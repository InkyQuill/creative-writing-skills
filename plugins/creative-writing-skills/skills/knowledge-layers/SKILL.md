---
name: knowledge-layers
description: Place durable project knowledge in the existing instructions, reference docs, knowledge base, or active work notes.
---

# Knowledge Layers

First discover where this project already keeps each kind of information.
Use `$project-bootstrap` to resolve instruction files. Do not create a
standard folder tree when the author's project uses another layout.

- Project instructions hold short, standing guidance needed when entering an
  area. Use `$qi-layer` when editing them.
- Nearby reference docs hold contracts and detail for a specific area.
- The knowledge base holds confirmed concepts and decisions that span areas.
  Use `$kb-management` for its format and update rules.
- User documentation describes shipped behavior. Active work notes hold
  provisional reasoning and open choices.

Keep one current account of a fact and link to it when useful. Update a
durable claim when the underlying decision changes; do not promote an idea to
canon before the author confirms it. Remove stale guidance when its subject
has gone. Record a new page only when existing notes cannot hold the fact
clearly.

For a new knowledge base, `resources/bootstrap.md` offers a small optional
starting point; adapt it to the folders the author has selected.
