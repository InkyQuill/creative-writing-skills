# Structured-artifact executable audit

`structured-artifact-audit.json` is a fail-closed review boundary. It lists
every structured-artifact resource that contains executable HTML, JavaScript,
SVG, Mermaid, or a corresponding executable fence and approves its exact
SHA-256. Validation rejects changed bytes, an unlisted executable resource, a
missing listed resource, unsafe paths, symlinks, and canonical/Claude drift.

After reviewing an intentional executable-example change, run:

```bash
python3 scripts/audit_structured_artifact_resources.py
```

The helper prints the proposed deterministic manifest to standard output. It
never modifies the tracked manifest; copying reviewed hashes into the manifest
is an explicit maintainer action.
