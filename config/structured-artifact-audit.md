# Structured-artifact resource audit

`structured-artifact-audit.json` is a fail-closed review boundary. It lists
every regular file under the canonical structured-artifact skill and approves
its exact SHA-256. Validation does not classify files by extension or content:
any new file is unlisted until reviewed. It rejects changed bytes, missing or
unlisted resources, unsafe paths, symlinks, incomplete inspection, and
canonical/Claude drift for every approved file.

Inventory traversal opens each directory component and file relative to a
trusted directory descriptor with no-follow flags, verifies the opened object
with `fstat`, and hashes only bytes read from that descriptor. Platforms that
cannot provide this atomic boundary fail closed instead of falling back to
pathname reads.

After reviewing an intentional structured-artifact resource change, run:

```bash
python3 scripts/audit_structured_artifact_resources.py
```

The helper prints the proposed deterministic manifest to standard output. It
never modifies the tracked manifest; copying reviewed hashes into the manifest
is an explicit maintainer action.
