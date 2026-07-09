---
name: web-researcher
description: Web research for fiction — primary sources, reference works, cultural detail, domain expertise, and community discussion.
mode: subagent
model: gptmini
effort: medium
model-policies:
  - match:
      alias: gptmini
    override: {}
  - match:
      alias: sonnet
    override: {}
  - match:
      alias: gpt
    override: {}
  - match:
      alias: gpt55
    override:
      effort: medium
  - match:
      alias: deepseek
    override:
      effort: high
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
