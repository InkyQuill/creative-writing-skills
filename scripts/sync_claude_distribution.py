#!/usr/bin/env python3

import argparse
import json
import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass
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
_SKILL_NAME_RE = re.compile(r"[a-z][a-z0-9-]*\Z")
_CONFIG_KEYS = {
    "canonical_skills",
    "authored_skills",
    "vendored_skills",
    "workers",
    "claude",
}
_CLAUDE_PATH_CONFIG = {
    "root": "cw",
    "marketplace": ".claude-plugin/marketplace.json",
}
_CLAUDE_CONFIG_KEYS = {
    "root",
    "marketplace",
    "disable_model_invocation",
}


class UnsupportedTransformError(ValueError):
    pass


class DistributionTransactionError(ValueError):
    def __init__(
        self,
        forward_error: BaseException,
        rollback_errors: list[tuple[str, BaseException]],
        recovery_path: Path,
    ) -> None:
        self.forward_error = forward_error
        self.rollback_errors = tuple(rollback_errors)
        self.recovery_path = recovery_path
        details = "; ".join(
            f"{label}: {error}" for label, error in rollback_errors
        )
        super().__init__(
            f"distribution install failed ({forward_error}); rollback failures: "
            f"{details}; recovery files retained at {recovery_path}"
        )


class DistributionTransactionInterrupt(KeyboardInterrupt):
    def __init__(
        self,
        forward_error: KeyboardInterrupt,
        rollback_errors: list[tuple[str, BaseException]],
        recovery_path: Path,
    ) -> None:
        self.forward_error = forward_error
        self.rollback_errors = tuple(rollback_errors)
        self.recovery_path = recovery_path
        details = "; ".join(
            f"{label}: {error}" for label, error in rollback_errors
        )
        super().__init__(
            f"distribution install interrupted ({forward_error}); rollback failures: "
            f"{details}; recovery files retained at {recovery_path}"
        )


@dataclass(frozen=True)
class DistributionContext:
    repo_root: Path
    config: dict[str, object]
    plugin_root: Path
    skills_root: Path
    manifest_path: Path
    workers_path: Path
    cw_root: Path
    marketplace_path: Path
    skill_names: tuple[str, ...]
    known_skills: frozenset[str]
    claude_disable_model_invocation: frozenset[str]


@dataclass(frozen=True)
class InventoryEntry:
    kind: str
    mode: int
    payload: bytes | str | None = None


def _preflight_skill_tree(skill_root: Path, skill_name: str) -> None:
    excluded = Path("agents/openai.yaml")

    def walk(directory: Path) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as error:
            raise ValueError(f"{skill_name}: cannot inspect {directory}: {error}") from error
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(skill_root)
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as error:
                raise ValueError(
                    f"{skill_name}: cannot inspect runtime resource {relative}: {error}"
                ) from error
            if relative == excluded:
                if stat.S_ISREG(mode) or stat.S_ISLNK(mode):
                    continue
                raise ValueError(
                    f"{skill_name}: excluded agents/openai.yaml must be a file or symlink"
                )
            if stat.S_ISLNK(mode):
                raise ValueError(f"{skill_name}: runtime resource is a symlink: {relative}")
            _require_contained_path(
                path,
                skill_root,
                f"{skill_name} runtime resource {relative.as_posix()}",
            )
            if stat.S_ISDIR(mode):
                walk(path)
            elif not stat.S_ISREG(mode):
                raise ValueError(
                    f"{skill_name}: runtime resource is not a regular file: {relative}"
                )

    walk(skill_root)
    skill_file = skill_root / "SKILL.md"
    try:
        mode = skill_file.stat(follow_symlinks=False).st_mode
    except OSError as error:
        raise ValueError(f"{skill_name}: missing SKILL.md") from error
    if not stat.S_ISREG(mode):
        raise ValueError(f"{skill_name}: SKILL.md must be a regular file")


def _preflight_inputs(context: DistributionContext) -> None:
    try:
        entries = sorted(os.scandir(context.skills_root), key=lambda entry: entry.name)
    except OSError as error:
        raise ValueError(f"cannot inspect canonical skills root: {error}") from error
    directories: dict[str, Path] = {}
    for entry in entries:
        path = Path(entry.path)
        mode = entry.stat(follow_symlinks=False).st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"canonical skill entry is a symlink: {entry.name}")
        if not stat.S_ISDIR(mode):
            raise ValueError(f"canonical skill entry is not a directory: {entry.name}")
        _require_contained_path(
            path,
            context.skills_root,
            f"canonical skill directory {entry.name}",
            require_directory=True,
        )
        directories[entry.name] = path
    if set(directories) != set(context.skill_names):
        missing = sorted(set(context.skill_names) - set(directories))
        unexpected = sorted(set(directories) - set(context.skill_names))
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected: {', '.join(unexpected)}")
        raise ValueError(f"canonical skill inventory mismatch ({'; '.join(details)})")
    for skill_name in context.skill_names:
        _preflight_skill_tree(directories[skill_name], skill_name)

    registry = load_json(context.workers_path)
    workers = registry.get("workers")
    if not isinstance(workers, list):
        raise ValueError("worker registry workers must be a list")
    for index, worker in enumerate(workers):
        if not isinstance(worker, dict):
            raise ValueError(f"worker entry {index} must be an object")
        name = worker.get("name")
        prompt = worker.get("prompt")
        if not isinstance(name, str) or not isinstance(prompt, str):
            raise ValueError(f"worker entry {index} has invalid name or prompt")
        prompt_relative = Path(prompt)
        if prompt_relative.is_absolute() or ".." in prompt_relative.parts:
            raise ValueError(f"worker {name} prompt must not contain parent segments")
        prompt_path = _require_contained_path(
            context.workers_path.parent / prompt_relative,
            context.workers_path.parent,
            f"worker {name} prompt",
            require_file=True,
        )
        if prompt_path.parent != context.workers_path.parent:
            raise ValueError(f"worker {name} prompt must be adjacent to registry")


def _require_contained_path(
    path: Path,
    boundary: Path,
    label: str,
    *,
    require_file: bool = False,
    require_directory: bool = False,
    allow_leaf_symlink: bool = False,
) -> Path:
    boundary = boundary.absolute()
    path = path.absolute()
    try:
        relative = path.relative_to(boundary)
    except ValueError as error:
        raise ValueError(f"{label} escapes repository boundary: {path}") from error

    current = boundary
    for part in relative.parts:
        current = current / part
        if current.is_symlink() and not (
            allow_leaf_symlink and current == path
        ):
            raise ValueError(f"{label} has symlinked path component: {current}")
    if boundary.is_symlink():
        raise ValueError(f"{label} has symlinked boundary: {boundary}")
    containment_target = path.parent if allow_leaf_symlink and path.is_symlink() else path
    try:
        containment_target.resolve(strict=False).relative_to(boundary.resolve(strict=True))
    except (OSError, RuntimeError, ValueError) as error:
        raise ValueError(f"{label} resolves outside repository boundary: {path}") from error
    if require_file and not path.is_file():
        raise ValueError(f"{label} must be a regular file: {path}")
    if require_directory and not path.is_dir():
        raise ValueError(f"{label} must be a directory: {path}")
    return path


def _load_context(repo_root: Path) -> DistributionContext:
    repo_root = Path(repo_root).absolute()
    if repo_root.is_symlink() or not repo_root.is_dir():
        raise ValueError(f"repository root must be a non-symlink directory: {repo_root}")
    config_path = _require_contained_path(
        repo_root / "config" / "distribution.json",
        repo_root,
        "distribution config",
        require_file=True,
    )
    config = load_json(config_path)
    if set(config) != _CONFIG_KEYS:
        raise ValueError("distribution config fields do not match schema")
    claude = config.get("claude")
    if not isinstance(claude, dict) or set(claude) != _CLAUDE_CONFIG_KEYS:
        raise ValueError("distribution Claude fields do not match schema")
    if any(claude.get(key) != value for key, value in _CLAUDE_PATH_CONFIG.items()):
        raise ValueError("distribution Claude paths are not canonical")
    disable_model_invocation = claude.get("disable_model_invocation")
    if not isinstance(disable_model_invocation, list) or any(
        not isinstance(skill, str) or _SKILL_NAME_RE.fullmatch(skill) is None
        for skill in disable_model_invocation
    ):
        raise ValueError(
            "distribution Claude disable_model_invocation must be a list of skill names"
        )
    if len(disable_model_invocation) != len(set(disable_model_invocation)):
        raise ValueError(
            "distribution Claude disable_model_invocation must not contain duplicates"
        )
    if disable_model_invocation != sorted(disable_model_invocation):
        raise ValueError("distribution Claude disable_model_invocation must be sorted")

    skill_values = config.get("canonical_skills")
    if not isinstance(skill_values, list) or any(
        not isinstance(skill, str) or _SKILL_NAME_RE.fullmatch(skill) is None
        for skill in skill_values
    ):
        raise ValueError("distribution canonical_skills must contain skill names")
    if len(skill_values) != len(set(skill_values)):
        raise ValueError("distribution canonical_skills must not contain duplicates")
    if not set(disable_model_invocation) <= set(skill_values):
        raise ValueError(
            "distribution Claude disable_model_invocation must be a subset of canonical_skills"
        )
    partition: dict[str, set[str]] = {}
    for key in ("authored_skills", "vendored_skills"):
        values = config.get(key)
        if not isinstance(values, list) or any(
            not isinstance(item, str) or _SKILL_NAME_RE.fullmatch(item) is None
            for item in values
        ):
            raise ValueError(f"distribution {key} must be a list of strings")
        if len(values) != len(set(values)):
            raise ValueError(f"distribution {key} must not contain duplicates")
        partition[key] = set(values)
    if partition["authored_skills"] & partition["vendored_skills"]:
        raise ValueError("distribution authored and vendored skills must be disjoint")
    if partition["authored_skills"] | partition["vendored_skills"] != set(
        skill_values
    ):
        raise ValueError(
            "distribution authored and vendored skills must partition canonical skills"
        )

    plugin_root = _require_contained_path(
        repo_root / "plugins" / "creative-writing-skills",
        repo_root,
        "canonical plugin root",
        require_directory=True,
    )
    skills_root = _require_contained_path(
        plugin_root / "skills",
        repo_root,
        "canonical skills root",
        require_directory=True,
    )
    manifest_path = _require_contained_path(
        plugin_root / ".codex-plugin" / "plugin.json",
        repo_root,
        "canonical manifest",
        require_file=True,
    )
    workers_value = config.get("workers")
    if not isinstance(workers_value, str) or not workers_value:
        raise ValueError("distribution workers path must be a nonempty string")
    workers_relative = Path(workers_value)
    if workers_relative.is_absolute() or ".." in workers_relative.parts:
        raise ValueError(
            "distribution workers path must be repository-relative without parent segments"
        )
    workers_path = _require_contained_path(
        plugin_root / workers_relative,
        plugin_root,
        "worker registry",
        require_file=True,
    )
    cw_root = _require_contained_path(
        repo_root / "cw",
        repo_root,
        "Claude root",
        allow_leaf_symlink=True,
    )
    marketplace_path = _require_contained_path(
        repo_root / ".claude-plugin" / "marketplace.json",
        repo_root,
        "Claude marketplace",
        allow_leaf_symlink=True,
    )
    context = DistributionContext(
        repo_root=repo_root,
        config=config,
        plugin_root=plugin_root,
        skills_root=skills_root,
        manifest_path=manifest_path,
        workers_path=workers_path,
        cw_root=cw_root,
        marketplace_path=marketplace_path,
        skill_names=tuple(skill_values),
        known_skills=frozenset(skill_values),
        claude_disable_model_invocation=frozenset(disable_model_invocation),
    )
    _preflight_inputs(context)
    return context


def _canonical_skills(repo_root: Path = REPO_ROOT) -> set[str]:
    config = load_json(Path(repo_root) / "config" / "distribution.json")
    skills = config.get("canonical_skills")
    if not isinstance(skills, list) or any(not isinstance(item, str) for item in skills):
        raise ValueError("distribution canonical_skills must be a list of strings")
    return set(skills)


def _yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _render_skill_frontmatter(
    metadata: dict[str, object],
    skill_name: str,
    *,
    disable_model_invocation: bool,
) -> str:
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
        if value is True:
            raise UnsupportedTransformError(
                f"{skill_name}: disable-model-invocation true is not supported "
                "in canonical Codex skills"
            )
    if disable_model_invocation:
        lines.append("disable-model-invocation: true")
    if "argument-hint" in metadata:
        value = metadata["argument-hint"]
        if not isinstance(value, str) or not value.strip():
            raise UnsupportedTransformError(f"{skill_name}: argument-hint must be nonempty")
        lines.append(f"argument-hint: {_yaml_scalar(value)}")
    lines.extend(("---", ""))
    return "\n".join(lines)


def _transform_markdown(
    text: str,
    label: str,
    known_skills: set[str] | frozenset[str] | None = None,
) -> str:
    known_skills = known_skills if known_skills is not None else _canonical_skills()

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


def transform_skill(
    text: str,
    skill_name: str,
    known_skills: set[str] | frozenset[str] | None = None,
    *,
    disable_model_invocation: bool = False,
) -> str:
    known_skills = known_skills if known_skills is not None else _canonical_skills()
    metadata, body = split_frontmatter(text)
    unsupported = sorted(set(metadata) - set(CLAUDE_FRONTMATTER_KEYS))
    if unsupported:
        raise UnsupportedTransformError(
            f"{skill_name}: unsupported frontmatter keys {', '.join(unsupported)}"
        )
    for key in ("description", "argument-hint"):
        value = metadata.get(key)
        if isinstance(value, str):
            metadata[key] = _transform_markdown(
                value, f"{skill_name} {key}", known_skills
            )
    return _render_skill_frontmatter(
        metadata,
        skill_name,
        disable_model_invocation=disable_model_invocation,
    ) + _transform_markdown(
        body, skill_name, known_skills
    )


def render_agent(
    worker: dict[str, object],
    prompt: str,
    known_skills: set[str] | frozenset[str] | None = None,
) -> str:
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
    known_skills = known_skills if known_skills is not None else _canonical_skills()
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
    return "\n".join(lines) + _transform_markdown(
        prompt, f"agent {name}", known_skills
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def _copy_skill(
    source: Path,
    destination: Path,
    skill_name: str,
    known_skills: set[str] | frozenset[str],
    *,
    disable_model_invocation: bool,
) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_dir():
            continue
        relative = path.relative_to(source)
        if relative.as_posix() == "agents/openai.yaml":
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative == Path("SKILL.md"):
            target.write_text(
                transform_skill(
                    path.read_text(),
                    skill_name,
                    known_skills,
                    disable_model_invocation=disable_model_invocation,
                )
            )
        elif path.suffix.lower() == ".md":
            target.write_text(
                _transform_markdown(
                    path.read_text(),
                    f"{skill_name}/{relative.as_posix()}",
                    known_skills,
                )
            )
        else:
            shutil.copyfile(path, target)


def _render_muse_agent(
    skill_source: str,
    skills: list[str],
    known_skills: set[str] | frozenset[str],
) -> str:
    rendered_skill = transform_skill(
        skill_source, "creative-writing-muse", known_skills
    )
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
        known_skills,
    )


def _render_distribution(
    output_root: Path,
    repo_root: Path,
    context: DistributionContext | None = None,
) -> None:
    output_root = Path(output_root)
    if output_root.exists():
        raise FileExistsError(f"distribution output already exists: {output_root}")

    context = context or _load_context(repo_root)
    config = context.config
    configured_skills = context.skill_names
    source_skills = skill_directories(context.skills_root)
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
        _copy_skill(
            source_skills[skill_name],
            skills_root / skill_name,
            skill_name,
            context.known_skills,
            disable_model_invocation=(
                skill_name in context.claude_disable_model_invocation
            ),
        )

    workers_path = context.workers_path
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
            render_agent(worker, prompt_path.read_text(), context.known_skills)
        )

    muse_source = source_skills["creative-writing-muse"] / "SKILL.md"
    (agents_root / "muse.md").write_text(
        _render_muse_agent(
            muse_source.read_text(),
            list(configured_skills),
            context.known_skills,
        )
    )

    canonical_manifest = load_json(context.manifest_path)
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
    context = _load_context(REPO_ROOT)
    _render_distribution(output_root, REPO_ROOT, context)


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


def _inventory_entry(path: Path) -> InventoryEntry | None:
    try:
        status = path.lstat()
    except FileNotFoundError:
        return None
    mode = stat.S_IMODE(status.st_mode)
    if stat.S_ISREG(status.st_mode):
        return InventoryEntry("file", mode, path.read_bytes())
    if stat.S_ISDIR(status.st_mode):
        return InventoryEntry("directory", mode)
    if stat.S_ISLNK(status.st_mode):
        return InventoryEntry("symlink", mode, os.readlink(path))
    return InventoryEntry("special", mode)


def _typed_inventory(root: Path) -> dict[Path, InventoryEntry]:
    root_entry = _inventory_entry(root)
    if root_entry is None or root_entry.kind != "directory":
        return {}
    inventory: dict[Path, InventoryEntry] = {}

    def walk(directory: Path) -> None:
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            path = Path(entry.path)
            relative = path.relative_to(root)
            item = _inventory_entry(path)
            if item is None:
                continue
            inventory[relative] = item
            if item.kind == "directory":
                walk(path)

    walk(root)
    return inventory


def _changed_diagnostic(label: str, expected: InventoryEntry, actual: InventoryEntry) -> str | None:
    if expected.kind != actual.kind:
        return (
            f"changed generated path: {label} "
            f"(expected {expected.kind}, found {actual.kind})"
        )
    if expected.payload != actual.payload:
        return f"changed generated {expected.kind}: {label}"
    if expected.mode != actual.mode:
        return (
            f"changed generated {expected.kind}: {label} "
            f"(mode {expected.mode:04o} != {actual.mode:04o})"
        )
    return None


def _distribution_drift(expected: Path, actual: Path, label: str) -> list[str]:
    expected_root = _inventory_entry(expected)
    actual_root = _inventory_entry(actual)
    if expected_root is None:
        raise ValueError(f"expected generated root is missing: {expected}")
    if actual_root is None:
        return [f"missing generated {expected_root.kind}: {label}"]
    root_diagnostic = _changed_diagnostic(label, expected_root, actual_root)
    if expected_root.kind != actual_root.kind:
        return [root_diagnostic] if root_diagnostic is not None else []

    expected_inventory = _typed_inventory(expected)
    actual_inventory = _typed_inventory(actual)
    problems: list[str] = [root_diagnostic] if root_diagnostic is not None else []
    for path in sorted(set(expected_inventory) | set(actual_inventory)):
        display = f"{label}/{path.as_posix()}"
        expected_entry = expected_inventory.get(path)
        actual_entry = actual_inventory.get(path)
        if expected_entry is None and actual_entry is not None:
            problems.append(
                f"unexpected generated {actual_entry.kind}: {display}"
            )
        elif expected_entry is not None and actual_entry is None:
            problems.append(
                f"missing generated {expected_entry.kind}: {display}"
            )
        elif expected_entry is not None and actual_entry is not None:
            diagnostic = _changed_diagnostic(display, expected_entry, actual_entry)
            if diagnostic is not None:
                problems.append(diagnostic)
    return problems


def _single_path_drift(expected: Path, actual: Path, label: str) -> list[str]:
    expected_entry = _inventory_entry(expected)
    actual_entry = _inventory_entry(actual)
    if expected_entry is None:
        raise ValueError(f"expected generated path is missing: {expected}")
    if actual_entry is None:
        return [f"missing generated {expected_entry.kind}: {label}"]
    diagnostic = _changed_diagnostic(label, expected_entry, actual_entry)
    return [diagnostic] if diagnostic is not None else []


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
    """Install both outputs and roll back detected exceptions and interrupts.

    Failed restores retain their last recoverable backups in transaction_root. This
    transaction does not claim durability across process termination, power loss, or
    an operating-system crash between filesystem operations.
    """
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
    except BaseException as forward_error:
        rollback_errors: list[tuple[str, BaseException]] = []

        def attempt(label: str, operation) -> None:
            try:
                operation()
            except BaseException as rollback_error:
                rollback_errors.append((label, rollback_error))

        if marketplace_installed:
            attempt(
                "marketplace cleanup failure",
                lambda: _remove_installed_tree(marketplace_path),
            )
        if marketplace_backed_up:
            attempt(
                "marketplace restore failure",
                lambda: os.replace(previous_marketplace, marketplace_path),
            )
        if cw_installed:
            attempt("cw cleanup failure", lambda: _remove_installed_tree(cw_root))
        if cw_backed_up:
            attempt(
                "cw restore failure",
                lambda: os.replace(previous_cw, cw_root),
            )
        if rollback_errors:
            if isinstance(forward_error, KeyboardInterrupt):
                raise DistributionTransactionInterrupt(
                    forward_error,
                    rollback_errors,
                    transaction_root,
                ) from forward_error
            raise DistributionTransactionError(
                forward_error,
                rollback_errors,
                transaction_root,
            ) from forward_error
        raise


def _sync(apply: bool, repo_root: Path) -> int:
    context = _load_context(repo_root)
    repo_root = context.repo_root
    skills = context.skill_names
    workers = load_json(context.workers_path).get("workers")
    if not isinstance(workers, list):
        raise ValueError("worker registry workers must be a list")

    cw_root = context.cw_root
    marketplace_path = context.marketplace_path
    transaction_root = Path(
        tempfile.mkdtemp(prefix=".claude-distribution-", dir=repo_root)
    )
    retain_recovery = False
    try:
        candidate_cw = transaction_root / "candidate-cw"
        candidate_marketplace = transaction_root / "candidate-marketplace.json"
        _render_distribution(candidate_cw, repo_root, context)
        _write_json(candidate_marketplace, _render_marketplace(repo_root))

        if not apply:
            problems = _distribution_drift(candidate_cw, cw_root, "cw")
            problems.extend(
                _single_path_drift(
                    candidate_marketplace,
                    marketplace_path,
                    ".claude-plugin/marketplace.json",
                )
            )
            problems.sort(key=lambda problem: problem.split(": ", 1)[-1])
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
    except (DistributionTransactionError, DistributionTransactionInterrupt):
        retain_recovery = True
        raise
    finally:
        if not retain_recovery and transaction_root.exists():
            shutil.rmtree(transaction_root)


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
