# Optional launcher setup

The launcher is user-scoped convenience, not a prerequisite. Keep using the
already resolved direct Python command for the current task while discussing
setup. Do not install third-party packages or copy `cw.py` into the story
project.

First identify the operating system, the user's actual shell, the installed
`project-maintenance` skill path, and a user-owned launcher directory. Build a
small wrapper that invokes `$project-maintenance`'s exact bundled
`resources/cli/cw.py` with Python 3.10 or newer and forwards every argument.
Use a user-owned executable wrapper in an existing user PATH directory; do not
modify system directories.

Before any write, show a complete preview containing:

- the exact launcher path and full wrapper contents;
- any PATH or shell-profile line to add, including the exact profile file;
- the verification command `cw cli-doctor --format json`;
- how to remove every proposed change.

Ask for explicit approval or permission for that preview. Approval for direct
CLI work is not approval for a persistent launcher, PATH edit, or profile edit.
Never silently change a shell profile or PATH. If approval is absent, stop the
setup and retain direct invocation.

For Linux and macOS, a user-owned executable wrapper may call:

```sh
exec python3 "/absolute/project-maintenance/resources/cli/cw.py" "$@"
```

For Windows, a user-owned `cw.cmd` may call:

```bat
@py -3 "C:\absolute\project-maintenance\resources\cli\cw.py" %*
```

After an approved change, run the launcher diagnosis and compare its reported
version with the direct entrypoint. If it is missing or stale, keep the direct
command as the working route and report the launcher problem; do not make
further persistent changes without a new preview and approval.
