---
name: cli-doctor
description: Diagnose and directly invoke the bundled cw story-project CLI when its runtime path, Python interpreter, or optional launcher is unavailable or stale.
---

# CLI Doctor

Diagnose first, before changing runtime setup or offering launcher setup.
Resolve the actual installed `$project-maintenance` skill path from the active
skill catalog; do not infer it from the story project. Its exact bundled
entrypoint is `<project-maintenance-skill>/resources/cli/cw.py`.

Require Python 3.10 or newer. Test that exact bundled entrypoint with the
platform's interpreter, then consume its structured diagnosis:

```text
Linux/macOS: python3 <project-maintenance-skill>/resources/cli/cw.py cli-doctor --format json
Windows: py -3.10 <project-maintenance-skill>\resources\cli\cw.py cli-doctor --format json
```

Interpret the JSON before acting. A failed required Python or direct-entrypoint
probe blocks CLI mechanics; an absent or stale launcher is optional and does
not. Report the material failing probe and its exact direct command.

Direct Python invocation is the default zero-configuration solution. Use the
resolved direct path for the current task as soon as its required probes pass.
It needs no third-party packages or dependencies. Never copy the CLI into a
story project.

Only after the active task can proceed may you offer optional launcher setup.
Read [launcher setup](resources/launcher-setup.md) only when the author wants a
persistent convenience command. Show the complete proposed filesystem, PATH,
or profile change and obtain explicit approval or permission before applying
it; never change a shell profile silently.
