# Issue Reporting

Use this procedure only after the main skill's ownership, evidence, duplicate,
and confidence checks. Keep feedback work subordinate to the primary task.

## Read-only search and inspection

Search open and closed issues together. With GitHub CLI, execute an argument
vector equivalent to:

```text
gh issue list --repo InkyQuill/creative-writing-skills --state all --search <sanitized search terms> --json number,title,state,url,body
```

Inspect every plausible candidate rather than relying on title similarity:

```text
gh issue view <number> --repo InkyQuill/creative-writing-skills --json number,title,state,url,body,comments
```

When `gh` or authentication is missing, use an available public web or GitHub
read path for the same open and closed search. Lack of a mutation capability
does not excuse skipping duplicate detection when public read access works.

## Evidence and privacy

Verify the observed behavior from local evidence, instructions, or prose.
Never send manuscript prose, `<hidden>` material, private story facts,
credentials, tokens, cookies, environment dumps, or unrelated user data.
Redact personal absolute paths and usernames, replacing them with neutral
placeholders such as `<project>` and `<user>`. Include only the smallest
sanitized excerpt needed to prove the defect.

A complete issue body uses this structure; omit Environment only when it has
no bearing on the problem:

```markdown
## Affected component

Component and plugin or CLI version.

## Minimal reproduction

Small, deterministic steps using redacted sample data.

## Expected behavior

The behavior required by the relevant contract or instruction.

## Actual behavior

The directly observed result.

## Sanitized evidence

Minimal logs, output, or source references with private data removed.

## Impact

How this affects the writing or maintenance workflow.

## Environment

Only versions or platform facts relevant to reproduction.
```

Do not assign labels, milestones, assignees, or severity unless the repository
already defines an unambiguous matching convention. Never comment on, close,
reopen, or edit an existing issue automatically; each is a separate external
mutation that requires task-specific intent.

## Capability and creation

Check once that all required capabilities are currently usable:

1. `gh` resolves as an executable.
2. `gh auth status` reports an authenticated account usable for GitHub.com.
3. `gh repo view InkyQuill/creative-writing-skills --json nameWithOwner,hasIssuesEnabled,url`
   reaches the intended repository and reports issues enabled.

Do not require a maintainer role or repository write permission. Public issue
creation is a distinct capability available to ordinary authenticated users.
The creation attempt itself is the final capability check.

Write the exact redacted body to a body file in an already established safe
writable area. Then execute `gh` directly as an argument vector, without shell
interpolation, equivalent to:

```text
gh issue create --repo InkyQuill/creative-writing-skills --title <redacted title> --body-file <body file>
```

Do not pass the body through a shell string, command substitution, or inline
escaping. On success, report the new issue URL and return to the primary task.

## One-pass fallback

If `gh`, authentication, network, or creation permission is unavailable, or
creation fails, record that specific failure once. Do not request or prompt for
a login, repeatedly retry creation, or enter a retry loop.

Keep the complete title and body in an already established writable task/report
area. In a canonical story project, prefer its existing `work/reviews/` area;
otherwise use an existing active task/report area. Never invent or create
either directory only to hold feedback. If no safe durable area already exists,
return the complete draft inline.

State the exact failure and the draft location. For an inline fallback, state
the exact failure and include the complete draft content. Then continue the
primary task; the fallback is not a blocker.
