# Managed launcher setup

The launcher is user-scoped convenience, not a runtime prerequisite. After the
required probes pass, `cw cli-doctor` tries to install or refresh it. Keep using
the resolved direct Python command if that attempt cannot be completed. Do not
install third-party packages or copy `cw.py` into the story project.

The command identifies the operating system, installed `project-maintenance`
skill path, and an existing user-owned launcher directory already present in
PATH. It builds a small managed wrapper that invokes `/project-maintenance`'s
exact bundled `resources/cli/cw.py` with the verified Python 3.10+ interpreter
and forwards every argument. It never creates or modifies system directories.

Automatic setup is allowed only when all of these conditions hold:

- the launcher's parent is an existing, writable, user-owned directory beneath
  the user's home and is already in PATH;
- the destination is absent or is a regular file carrying the cli-doctor
  managed marker;
- the generated wrapper contains the current absolute interpreter and bundled
  entrypoint paths;
- POSIX wrappers are installed atomically with executable mode `0700`.

An absent managed launcher is created. An existing managed launcher is compared
byte-for-byte and atomically replaced when its interpreter or plugin entrypoint
path changed. This is what repairs `cw` after a plugin update moves the bundled
files. The exact legacy wrapper shape documented below may be adopted once and
rewritten with the managed marker. Any other unmanaged `cw`, symlink, non-user
file, or system location is reported and left untouched.

Never silently change a shell profile or PATH. If no safe directory is already
available, report that automatic installation was not possible and retain the
direct invocation. Adding a new PATH entry or editing a shell profile remains a
separate author-approved action.

For Linux and macOS, a user-owned executable wrapper may call:

```sh
#!/bin/sh
exec python3 "/absolute/project-maintenance/resources/cli/cw.py" "$@"
```

For Windows, a user-owned `cw.cmd` may call:

```bat
@py -3 "C:\absolute\project-maintenance\resources\cli\cw.py" %*
```

After creation or refresh, the command invokes the launcher and compares its
reported version with the direct entrypoint. If verification fails, keep the
direct command as the working route and report the launcher problem.
