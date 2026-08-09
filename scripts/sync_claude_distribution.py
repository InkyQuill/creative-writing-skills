#!/usr/bin/env python3

import argparse
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

if __package__:
    from scripts.distribution import (
        REPO_ROOT,
        extract_skill_references,
        load_json,
        map_outside_fences,
        skill_directories,
        split_frontmatter,
    )
else:
    from distribution import (
        REPO_ROOT,
        extract_skill_references,
        load_json,
        map_outside_fences,
        skill_directories,
        split_frontmatter,
    )


CONFIG_PATH = REPO_ROOT / "config" / "distribution.json"
PLUGIN_ROOT = REPO_ROOT / "plugins" / "creative-writing-skills"
SKILLS_ROOT = PLUGIN_ROOT / "skills"
CANONICAL_MANIFEST_PATH = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
TEXT_REPLACEMENTS = {
    "AGENTS.md": "CLAUDE.md",
    "Codex subagent": "subagent",
    "Codex subagents": "subagents",
}
CODEX_ONLY_CONSTRUCTS = ("spawn_agent", "collaboration.", ".codex-plugin")
CLAUDE_FRONTMATTER_KEYS = (
    "name",
    "description",
    "disable-model-invocation",
    "argument-hint",
)
_DOLLAR_REFERENCE_RE = re.compile(r"\$([a-z][a-z0-9-]*)")


class UnsupportedTransformError(ValueError):
    pass


def _canonical_skills() -> set[str]:
    config = load_json(CONFIG_PATH)
    skills = config.get("canonical_skills")
    if not isinstance(skills, list) or any(not isinstance(item, str) for item in skills):
        raise ValueError("distribution canonical_skills must be a list of strings")
    return set(skills)


def _yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _render_skill_frontmatter(metadata: dict[str, object], skill_name: str) -> str:
    if metadata.get("name") != skill_name:
        raise UnsupportedTransformError(
            f"frontmatter name {metadata.get('name')!r} does not match {skill_name!r}"
        )
    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip():
        raise UnsupportedTransformError(f"{skill_name}: description must be nonempty")

    lines = ["---", f"name: {skill_name}", f"description: {_yaml_scalar(description)}"]
    if "disable-model-invocation" in metadata:
        value = metadata["disable-model-invocation"]
        if not isinstance(value, bool):
            raise UnsupportedTransformError(
                f"{skill_name}: disable-model-invocation must be boolean"
            )
        lines.append(f"disable-model-invocation: {str(value).lower()}")
    if "argument-hint" in metadata:
        value = metadata["argument-hint"]
        if not isinstance(value, str) or not value.strip():
            raise UnsupportedTransformError(f"{skill_name}: argument-hint must be nonempty")
        lines.append(f"argument-hint: {_yaml_scalar(value)}")
    lines.extend(("---", ""))
    return "\n".join(lines)


def _transform_markdown(text: str, label: str) -> str:
    known_skills = _canonical_skills()

    def transform(segment: str) -> str:
        for source, replacement in TEXT_REPLACEMENTS.items():
            segment = segment.replace(source, replacement)

        def replace_skill(match: re.Match[str]) -> str:
            skill = match.group(1)
            return f"/{skill}" if skill in known_skills else match.group(0)

        return _DOLLAR_REFERENCE_RE.sub(replace_skill, segment)

    rendered = map_outside_fences(text, transform)
    for construct in CODEX_ONLY_CONSTRUCTS:
        found = False

        def detect(segment: str) -> str:
            nonlocal found
            found = found or construct in segment
            return segment

        map_outside_fences(rendered, detect)
        if found:
            raise UnsupportedTransformError(f"{label}: unsupported {construct}")

    dollar_references = extract_skill_references(rendered, "$")
    if dollar_references:
        reference = sorted(dollar_references)[0]
        raise UnsupportedTransformError(f"{label}: unsupported dollar reference ${reference}")
    for reference in sorted(extract_skill_references(rendered, "/")):
        if reference not in known_skills:
            raise UnsupportedTransformError(
                f"{label}: unknown Claude skill reference /{reference}"
            )
    return rendered


def transform_skill(text: str, skill_name: str) -> str:
    metadata, body = split_frontmatter(text)
    unsupported = sorted(set(metadata) - set(CLAUDE_FRONTMATTER_KEYS))
    if unsupported:
        raise UnsupportedTransformError(
            f"{skill_name}: unsupported frontmatter keys {', '.join(unsupported)}"
        )
    for key in ("description", "argument-hint"):
        value = metadata.get(key)
        if isinstance(value, str):
            metadata[key] = _transform_markdown(value, f"{skill_name} {key}")
    return _render_skill_frontmatter(metadata, skill_name) + _transform_markdown(
        body, skill_name
    )


def render_agent(worker: dict[str, object], prompt: str) -> str:
    name = worker.get("name")
    description = worker.get("description")
    skills = worker.get("skills")
    claude = worker.get("claude")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", name):
        raise ValueError("worker name must be a kebab-case string")
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"worker {name}: description must be nonempty")
    if not isinstance(skills, list) or any(not isinstance(skill, str) for skill in skills):
        raise ValueError(f"worker {name}: skills must be a list of strings")
    known_skills = _canonical_skills()
    unknown = sorted(set(skills) - known_skills)
    if unknown:
        raise ValueError(f"worker {name}: unknown skills {', '.join(unknown)}")
    if not isinstance(claude, dict):
        raise ValueError(f"worker {name}: claude metadata must be an object")

    lines = [
        "---",
        f"name: {name}",
        f"description: {_yaml_scalar(description)}",
        "skills:",
        *(f"  - {skill}" for skill in skills),
    ]
    if claude.get("background") is True:
        lines.append("background: true")
    lines.extend(("---", ""))
    return "\n".join(lines) + _transform_markdown(prompt, f"agent {name}")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def _copy_skill(source: Path, destination: Path, skill_name: str) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_dir():
            continue
        relative = path.relative_to(source)
        if relative.as_posix() == "agents/openai.yaml":
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative == Path("SKILL.md"):
            target.write_text(transform_skill(path.read_text(), skill_name))
        elif path.suffix.lower() == ".md":
            target.write_text(
                _transform_markdown(path.read_text(), f"{skill_name}/{relative.as_posix()}")
            )
        else:
            shutil.copyfile(path, target)


def _render_muse_agent(skill_source: str, skills: list[str]) -> str:
    rendered_skill = transform_skill(skill_source, "creative-writing-muse")
    metadata, body = split_frontmatter(rendered_skill)
    return render_agent(
        {
            "name": "muse",
            "description": metadata["description"],
            "skills": skills,
            "access": "workspace-write",
            "claude": {"model": "inherit", "background": False},
        },
        body,
    )


def _render_distribution(output_root: Path, repo_root: Path) -> None:
    output_root = Path(output_root)
    if output_root.exists():
        raise FileExistsError(f"distribution output already exists: {output_root}")

    config_path = repo_root / "config" / "distribution.json"
    plugin_root = repo_root / "plugins" / "creative-writing-skills"
    skills_source_root = plugin_root / "skills"
    canonical_manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    config = load_json(config_path)
    configured_skills = config.get("canonical_skills")
    if not isinstance(configured_skills, list) or any(
        not isinstance(skill, str) for skill in configured_skills
    ):
        raise ValueError("distribution canonical_skills must be a list of strings")
    source_skills = skill_directories(skills_source_root)
    if set(source_skills) != set(configured_skills):
        missing = sorted(set(configured_skills) - set(source_skills))
        unexpected = sorted(set(source_skills) - set(configured_skills))
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected: {', '.join(unexpected)}")
        raise ValueError(f"canonical skill inventory mismatch ({'; '.join(details)})")

    skills_root = output_root / "skills"
    for skill_name in configured_skills:
        _copy_skill(source_skills[skill_name], skills_root / skill_name, skill_name)

    workers_path = plugin_root / str(config["workers"])
    registry = load_json(workers_path)
    workers = registry.get("workers")
    if not isinstance(workers, list) or any(not isinstance(worker, dict) for worker in workers):
        raise ValueError("worker registry workers must be a list of objects")
    agents_root = output_root / "agents"
    agents_root.mkdir(parents=True, exist_ok=True)
    worker_names: set[str] = set()
    for worker in workers:
        name = worker.get("name")
        prompt_name = worker.get("prompt")
        if not isinstance(name, str) or name in worker_names:
            raise ValueError(f"invalid or duplicate worker name: {name!r}")
        if not isinstance(prompt_name, str):
            raise ValueError(f"worker {name}: prompt must be a relative path")
        prompt_path = workers_path.parent / prompt_name
        if prompt_path.parent != workers_path.parent or not prompt_path.is_file():
            raise ValueError(f"worker {name}: invalid prompt path {prompt_name!r}")
        worker_names.add(name)
        (agents_root / f"{name}.md").write_text(
            render_agent(worker, prompt_path.read_text())
        )

    muse_source = source_skills["creative-writing-muse"] / "SKILL.md"
    (agents_root / "muse.md").write_text(
        _render_muse_agent(muse_source.read_text(), list(configured_skills))
    )

    canonical_manifest = load_json(canonical_manifest_path)
    manifest_fields = (
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
    )
    manifest = {field: canonical_manifest[field] for field in manifest_fields}
    _write_json(output_root / ".claude-plugin" / "plugin.json", manifest)


def render_distribution(output_root: Path) -> None:
    _render_distribution(output_root, REPO_ROOT)


def _render_marketplace(repo_root: Path) -> dict[str, object]:
    manifest = load_json(
        repo_root
        / "plugins"
        / "creative-writing-skills"
        / ".codex-plugin"
        / "plugin.json"
    )
    return {
        "name": manifest["name"],
        "owner": manifest["author"],
        "metadata": {
            "description": manifest["description"],
            "version": manifest["version"],
        },
        "plugins": [
            {
                "name": manifest["name"],
                "description": manifest["description"],
                "source": "./cw",
            }
        ],
    }


def _distribution_drift(expected: Path, actual: Path, label: str) -> list[str]:
    expected_files = {
        path.relative_to(expected): path
        for path in expected.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    actual_files = (
        {
            path.relative_to(actual): path
            for path in actual.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        if actual.is_dir() and not actual.is_symlink()
        else {}
    )
    actual_symlinks = (
        {path.relative_to(actual) for path in actual.rglob("*") if path.is_symlink()}
        if actual.is_dir() and not actual.is_symlink()
        else set()
    )
    problems = [
        f"missing generated file: {label}/{path.as_posix()}"
        for path in sorted(set(expected_files) - set(actual_files) - actual_symlinks)
    ]
    problems.extend(
        f"unexpected generated file: {label}/{path.as_posix()}"
        for path in sorted(set(actual_files) - set(expected_files))
    )
    problems.extend(
        f"changed generated file: {label}/{path.as_posix()}"
        for path in sorted(set(expected_files) & set(actual_files))
        if expected_files[path].read_bytes() != actual_files[path].read_bytes()
    )
    problems.extend(
        f"changed generated file: {label}/{path.as_posix()}"
        for path in sorted(actual_symlinks)
    )
    return problems


def _remove_installed_tree(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def _commit_candidate(
    candidate_cw: Path,
    cw_root: Path,
    candidate_marketplace: Path,
    marketplace_path: Path,
    transaction_root: Path,
) -> None:
    if cw_root.is_symlink():
        raise ValueError(f"refusing to replace symlink: {cw_root}")
    if marketplace_path.is_symlink():
        raise ValueError(f"refusing to replace symlink: {marketplace_path}")

    previous_cw = transaction_root / "previous-cw"
    previous_marketplace = transaction_root / "previous-marketplace.json"
    cw_backed_up = False
    cw_installed = False
    marketplace_backed_up = False
    marketplace_installed = False
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if cw_root.exists():
            os.replace(cw_root, previous_cw)
            cw_backed_up = True
        os.replace(candidate_cw, cw_root)
        cw_installed = True
        if marketplace_path.exists():
            os.replace(marketplace_path, previous_marketplace)
            marketplace_backed_up = True
        os.replace(candidate_marketplace, marketplace_path)
        marketplace_installed = True
    except BaseException:
        if marketplace_installed:
            marketplace_path.unlink()
        if marketplace_backed_up:
            os.replace(previous_marketplace, marketplace_path)
        if cw_installed:
            _remove_installed_tree(cw_root)
        if cw_backed_up:
            os.replace(previous_cw, cw_root)
        raise


def _sync(apply: bool, repo_root: Path) -> int:
    repo_root = Path(repo_root)
    config = load_json(repo_root / "config" / "distribution.json")
    skills = config.get("canonical_skills")
    if not isinstance(skills, list) or any(not isinstance(skill, str) for skill in skills):
        raise ValueError("distribution canonical_skills must be a list of strings")
    workers_path = (
        repo_root / "plugins" / "creative-writing-skills" / str(config["workers"])
    )
    workers = load_json(workers_path).get("workers")
    if not isinstance(workers, list):
        raise ValueError("worker registry workers must be a list")

    cw_root = repo_root / str(config["claude"]["root"])
    marketplace_path = repo_root / str(config["claude"]["marketplace"])
    with tempfile.TemporaryDirectory(
        prefix=".claude-distribution-", dir=repo_root
    ) as temporary:
        transaction_root = Path(temporary)
        candidate_cw = transaction_root / "candidate-cw"
        candidate_marketplace = transaction_root / "candidate-marketplace.json"
        _render_distribution(candidate_cw, repo_root)
        _write_json(candidate_marketplace, _render_marketplace(repo_root))

        if not apply:
            problems = _distribution_drift(candidate_cw, cw_root, "cw")
            if not marketplace_path.is_file() or marketplace_path.is_symlink():
                problems.append(
                    "missing generated file: .claude-plugin/marketplace.json"
                )
            elif candidate_marketplace.read_bytes() != marketplace_path.read_bytes():
                problems.append(
                    "changed generated file: .claude-plugin/marketplace.json"
                )
            if problems:
                for problem in problems:
                    print(problem)
                return 1
            print("Claude distribution is in sync")
            return 0

        _commit_candidate(
            candidate_cw,
            cw_root,
            candidate_marketplace,
            marketplace_path,
            transaction_root,
        )
        for skill in skills:
            print(f"synced skill {skill}")
        for worker in workers:
            if not isinstance(worker, dict) or not isinstance(worker.get("name"), str):
                raise ValueError("worker registry contains an invalid worker")
            print(f"synced agent {worker['name']}")
        print("synced agent muse")
        print("synced cw/.claude-plugin/plugin.json")
        print("synced .claude-plugin/marketplace.json")
        return 0


def main(argv: list[str] | None = None, *, repo_root: Path = REPO_ROOT) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the Claude compatibility distribution"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="replace generated output")
    mode.add_argument("--check", action="store_true", help="report generated drift")
    args = parser.parse_args(argv)
    try:
        return _sync(args.apply, repo_root)
    except (OSError, UnicodeError, ValueError, KeyError) as error:
        print(f"Claude distribution sync failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
