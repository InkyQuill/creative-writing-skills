#!/usr/bin/env python3

import json

if __package__:
    from scripts.distribution import PLUGIN_ROOT
    from scripts.validate_distribution import compute_structured_artifact_audit
else:
    from distribution import PLUGIN_ROOT
    from validate_distribution import compute_structured_artifact_audit


def main() -> int:
    skill_root = PLUGIN_ROOT / "skills" / "structured-artifact"
    print(json.dumps(compute_structured_artifact_audit(skill_root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
