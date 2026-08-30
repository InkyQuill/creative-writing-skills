---
name: cli-doctor
description: "Diagnose and directly invoke the bundled cw story-project CLI, installing or refreshing its user launcher when a safe PATH location is available."
---

# CLI Doctor

Diagnose first, before changing runtime setup or offering launcher setup.
Resolve the actual installed `/project-maintenance` skill path from the active
skill catalog; do not infer it from the story project. Its exact bundled
entrypoint is `<project-maintenance-skill>/resources/cli/cw.py`.

Require Python 3.10 or newer. Select an available Python 3 interpreter, test
that exact bundled entrypoint, and let its diagnosis enforce the minimum:

```text
Linux/macOS: python3 "<project-maintenance-skill>/resources/cli/cw.py" cli-doctor --format json
Windows: py -3 "<project-maintenance-skill>\resources\cli\cw.py" cli-doctor --format json
```

Interpret the JSON before acting. A failed required Python or direct-entrypoint
probe blocks CLI mechanics. Launcher installation or repair is attempted only
after those probes pass; inability to write a safe user-owned PATH location is
nonblocking. Report the material failing probe and its exact direct command.

Direct Python invocation is the default zero-configuration solution. Use the
resolved direct path for the current task as soon as its required probes pass.
It needs no third-party packages or dependencies. Never copy the CLI into a
story project.

The diagnosis command installs `cw` into an existing user-owned PATH directory
when possible. It marks that wrapper as managed and refreshes its exact Python
and bundled-entrypoint paths whenever `cli-doctor` runs from a new plugin
installation. Read [launcher setup](resources/launcher-setup.md) when reporting
or troubleshooting this behavior. Never overwrite an unmanaged launcher,
write a system directory, or change PATH or a shell profile automatically.
