# Command Reference

Resolve the installed `project-maintenance` skill and invoke
`resources/cli/cw.py` directly with Python. Run from the relevant project path
or pass the project path where the command accepts one. A user-scoped `cw`
launcher is optional convenience, never a prerequisite.

Use `--format json` when structured output helps. Transactional previews do
not modify the project. Transactional mutations preview by default and write
only when repeated with `--apply`; the derived context cache has the narrower
exceptions described below.

## Inspect and prepare context

```text
check structure|links|kb|continuity|drafts|prose|journal|all [project]
doctor
context draft|chapter|kb <path> [--as trusted|reader|character:<id>] [--snapshot]
clean-context
reindex
```

Use `check all` for the mechanical floor, or a focused checker while working
in one domain. Context planning without `--snapshot` is read-only. A restricted
`context --snapshot` writes derived cache without `--apply`; trusted context
can use the selected source paths directly. `clean-context` previews and
applies derived-cache deletion with `--apply`, but it stays outside transaction
history. `reindex` is transactional: preview it, then apply the reviewed diff.

`check prose` always reports universal Unicode counts and integrity signals.
Russian and English capabilities additionally measure their own pronoun,
opener, quote, punctuation, and dialogue conventions. For an unsupported
language, the check explicitly omits those language-sensitive metrics, reports their
structured `skipped_metrics`, and continues without a failing status or an
English fallback.

Russian-language projects additionally receive deterministic typography
findings (`CW-PROSE-100`…`CW-PROSE-103` warnings for straight quotes,
spaced hyphens, three-dot ellipses, and breakable spaces after
single-letter words; `CW-PROSE-110`…`CW-PROSE-114` info findings for digit
grouping, decimal points, `№`, ordinals, and abbreviation spacing). They
report typographic norms as warnings the project's `project.md`
conventions may override; they never fail `check all` without `--strict`.

## Project and draft lifecycle

```text
init [path] --title <title> --language <language>
draft create <target> [--draft-path <path>]
draft set-status <draft> working|review|ready
draft rebase <draft>
draft accept <draft>
draft abandon <draft>
migrate --plan
migrate --preview <plan.json> --expect-plan-hash <hash>
migrate --apply <plan.json> --expect-plan-hash <hash>
```

New projects receive `prose-profile: general`. Existing schema-v1 projects
without the optional field behave the same way, and valid custom profile slugs
are preserved by migration, rebase, and exact document edits.

Preview every lifecycle mutation. Draft acceptance changes the story target;
it does not itself write material into the KB. After acceptance, re-read the
accepted text and synchronize direct and unambiguous facts from that accepted
text through a separate previewed, recoverable KB transaction without
reapproval.

A separate KB transaction does not mean separate approval. Ask the author only
when ambiguity, inference, conflict, retcon, source-tag uncertainty, or
character/reader knowledge-boundary uncertainty would materially change canon
or knowledge boundaries. The agent carries plan hashes and `base-revision`
values between commands without asking the author to maintain them.

## Exact edits and transaction history

```text
edit replace|insert-before|insert-after|delete ...
edit apply <operations.json>
history
history show <transaction-id>
undo <transaction-id>
recover <transaction-id>
```

Put large anchors and replacement bodies in files. Preview edit, undo, and
recover operations before `--apply`. `history` is append-only evidence: undo
creates a new inverse transaction and refuses diverged targets. Recovery rolls
an interrupted transaction back only when journal evidence still proves the
safe before-state.

## Exit status

- Exit 0: the command completed; continue the requested workflow.
- Exit 1: findings or a safe conflict need agent inspection. Continue any
  unrelated creative work while planning a bounded repair.
- Exit 2: the CLI could not execute. Follow the `cli-doctor` workflow; keep
  runtime setup away from the author.
