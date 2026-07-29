---
name: character-sim
description: In-character conversation for voice discovery and relationship testing.
model: opus46
model-policies:
  - match: {alias: opus46}
    override: {}
  - match: {alias: "opus46[1m]"}
    override: {}
  - match: {alias: fable}
    override: {}
  - match: {alias: opus}
    override: {}
  - match: {alias: opus48}
    override: {}
  - match: {alias: sonnet5}
    override: {}
  - match: {alias: sonnet}
    override: {}
  - match: {alias: sol}
    override: {}
  - match: {alias: deepseek}
    override: {effort: low}
skills:
  load: [character-sim, writing-principles, llm-writing]
  available: [story-memory]
tools:
  'bash(meridian spawn show *)': allow
  'bash(meridian session *)': allow
  'bash(cat *)': allow
  edit: deny
  write: deny
  notebook: deny
  ask_user: deny
sandbox: read-only
---

# Character Simulation

Use `/character-sim`.

