# Releases

Releases follow the Hieronymus workflow: merge ordinary work, review the generated
release PR, then merge it to publish automatically. There is no separate manual
version-bump or tag-push step.

## Version and release PR

Use Conventional Commit titles when merging work: `feat:` adds a minor version,
`fix:` and `perf:` add a patch. Before 1.0, breaking changes bump the minor version.
Keep the squash-merge title conventional; that is the commit release-please sees.

On pushes to `main`, release-please opens or updates one release PR containing:

- `CHANGELOG.md` and `.release-please-manifest.json`;
- the canonical version in `plugins/creative-writing-skills/.codex-plugin/plugin.json`;
- `version.txt`, the matching bookkeeping mirror required by the simple strategy.

The canonical plugin manifest remains the runtime/distribution version source.
`version.txt` and the release-please manifest must match it and are checked by CI;
do not update these independently. The workflow runs the ordinary distribution
generator on the bot branch and commits derived Claude/ZCode metadata there.
Generated files are never edited by release-please directly.

CI is explicitly dispatched on the synchronized PR branch. Publication invokes
the release workflow directly, because events created with `GITHUB_TOKEN` do not
start other workflows. This uses the standard repository token, without a PAT.
See [release-please credentials](https://github.com/googleapis/release-please-action#github-credentials).

## Publication

After the release PR merges, a canonical version increase selects the exact merge
SHA and `v<version>` tag. The release workflow:

1. Checks that version metadata agrees, the checkout is the requested SHA, that
   commit belongs to `main`, and any existing tag already points to that commit.
2. Runs all tests and distribution checks, then builds the complete configured
   skill inventory once and writes `SHA256SUMS` from those exact bytes.
3. Creates the tag without moving any existing tag, uploads the packages and
   checksums to a draft GitHub Release, then publishes only after upload succeeds.
4. Changes the merged release PR label from `autorelease: pending` to
   `autorelease: tagged` after publication.

Codex, Claude Code, and ZCode consume the committed plugin/marketplace trees;
Claude.ai packages are the `.skill` release attachments. No separate package
registry or deployment service is involved. Release PRs are not auto-merged.

## Enable once

Ensure **Settings → Actions → General → Workflow
permissions → Allow GitHub Actions to create and approve pull requests** is enabled. The
default token can stay read-only; write permissions are scoped to the release jobs.
The workflow does not approve its own PRs.

Run `release-please` manually if necessary:

```bash
gh workflow run release-please.yml
```

Require the `validate` CI check on `main` if branch protection is desired. No
branch-protection policy is changed by the release workflow.

## Retry a failed publication

Rerun the failed workflow, or dispatch `Release` from `main` with the original
merge SHA and tag:

```bash
gh workflow run release.yml -f release_tag=v0.12.0 -f release_sha=<full-merge-sha>
```

Use the original SHA, even if `main` has advanced. Archives are deterministic;
failed draft uploads can be retried, and an already published release is left
unchanged. A tag pointing elsewhere is an error, never a request to retag.
If only label reconciliation failed, rerunning also repairs the labels.

`scripts/release.py` refuses manual releases while release-please is configured,
so there is no second tool advancing versions or creating competing tags.
