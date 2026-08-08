---
name: web-researcher
description: Web research for fiction — primary sources, reference works, cultural detail, domain expertise, and community discussion.
mode: subagent
model: luna
effort: medium
model-policies:
  - match: {alias: luna}
    override: {effort: medium}
  - match: {alias: sonnet5}
    override: {}
  - match: {alias: sonnet}
    override: {}
  - match: {alias: deepseekflash}
    override: {effort: low}
  - match: {alias: deepseek}
    override: {}
skills:
  load: [creative-research]
tools:
  'bash(meridian *)': allow
  write: allow
  edit: allow
  web: allow
  notebook: deny
  ask_user: deny
sandbox: workspace-write
---

# Web Researcher

Use `/creative-research` for methodology.
