import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_ROOT = REPO_ROOT / "plugins/creative-writing-skills/skills/project-maintenance/resources/cli"
sys.path.insert(0, str(CLI_ROOT))

from cwcli import app, findings  # noqa: E402
