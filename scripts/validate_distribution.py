#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote

if __package__:
    from scripts.distribution import (
        REPO_ROOT,
        extract_instructional_relative_path_contexts,
        extract_skill_references,
        iter_fenced_lines,
        map_outside_fences,
        split_frontmatter,
    )
else:
    from distribution import (
        REPO_ROOT,
        extract_instructional_relative_path_contexts,
        extract_skill_references,
        iter_fenced_lines,
        map_outside_fences,
        split_frontmatter,
    )


PLUGIN_NAME = "creative-writing-skills"
REPOSITORY = "https://github.com/InkyQuill/creative-writing-skills"
EXPECTED_SKILLS = {
    "character-sim", "creative-research", "creative-writing-craft",
    "creative-writing-modes", "creative-writing-muse", "grill-with-docs",
    "information-hierarchy", "intent-modeling", "kb-management",
    "knowledge-layers", "llm-writing", "md-validation", "project-setup",
    "qi-layer", "reader-sim", "reflect", "shared-dao", "story-memory",
    "story-planning", "story-review", "structured-artifact", "world-creation",
    "writing-principles", "writing-staffing", "zoom-out",
}
AUTHORED_SKILLS = {
    "character-sim", "creative-research", "creative-writing-craft",
    "creative-writing-modes", "creative-writing-muse", "kb-management",
    "project-setup", "reader-sim", "shared-dao", "story-memory",
    "story-planning", "story-review", "world-creation",
    "writing-principles", "writing-staffing",
}
VENDORED_SKILLS = EXPECTED_SKILLS - AUTHORED_SKILLS
CLAUDE_DISABLE_MODEL_INVOCATION = (
    "reflect",
    "structured-artifact",
)
EXPECTED_WORKERS = {
    "brainstormer", "character-sim", "continuity-checker", "critic", "editor",
    "outliner", "reader-sim", "style-creator", "web-researcher", "writer",
}
READ_ONLY_WORKERS = {
    "character-sim", "continuity-checker", "critic", "editor", "reader-sim",
}
EXPECTED_WORKER_SKILLS = {
    "brainstormer": {"story-planning", "story-memory", "intent-modeling", "llm-writing"},
    "character-sim": {"character-sim", "writing-principles", "llm-writing", "story-memory"},
    "continuity-checker": {"story-review", "md-validation", "shared-dao", "story-memory"},
    "critic": {"story-review", "writing-principles", "llm-writing", "story-memory"},
    "editor": {
        "story-review", "writing-principles", "creative-writing-craft",
        "llm-writing", "story-memory",
    },
    "outliner": {"story-planning", "story-memory", "md-validation"},
    "reader-sim": {"reader-sim", "writing-principles", "llm-writing"},
    "style-creator": {
        "creative-writing-craft", "writing-principles", "llm-writing", "story-memory",
    },
    "web-researcher": {"creative-research"},
    "writer": {
        "creative-writing-modes", "creative-writing-craft", "writing-principles",
        "story-memory", "llm-writing",
    },
}
ALLOWED_FRONTMATTER_KEYS = {
    "name", "description", "disable-model-invocation", "argument-hint",
}
WORKER_KEYS = {"name", "description", "prompt", "skills", "access", "claude"}
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
MARKDOWN_LINK_RE = re.compile(
    r"\[[^]]+\]\((?!https?://|#|mailto:)([^)]+)\)",
    re.IGNORECASE,
)
URL_RE = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s<>]+", re.IGNORECASE)
PLATFORM_VOCABULARY_RE = re.compile(
    r"\bmeridian_[a-z0-9_]+\b|\bmeridian\s+mars\b|\b(?:mars|meridian)\b",
    re.IGNORECASE,
)
WORKER_REFERENCE_RE = re.compile(
    r"(?<![A-Za-z0-9_.%+-])@([a-z][a-z0-9]*(?:-[a-z0-9-]+)?)(?![A-Za-z0-9/-])"
)
CSS_AT_RULES = {
    "annotation", "apply", "bottom-center", "bottom-left", "bottom-left-corner",
    "bottom-right", "bottom-right-corner", "character-variant", "charset",
    "color-profile", "container", "contents", "counter-style", "custom-media",
    "custom-selector", "document", "else", "font-face", "font-feature-values",
    "font-palette-values", "function", "import", "keyframes", "layer",
    "historical-forms", "left-bottom", "left-middle", "left-top", "media",
    "mixin", "namespace", "nest",
    "ornaments", "page", "position-try", "property", "return", "right-bottom",
    "right-middle", "right-top", "scope", "scroll-timeline", "starting-style",
    "styleset", "stylistic", "supports", "supports-condition", "swash",
    "tailwind", "theme", "top-center", "top-left", "top-left-corner",
    "top-right", "top-right-corner", "view-transition", "viewport", "when",
}
TEXT_RUNTIME_SUFFIXES = {
    "", ".bash", ".c", ".cfg", ".cjs", ".conf", ".cpp", ".css", ".fish",
    ".h", ".html", ".htm", ".ini", ".java", ".js", ".json", ".jsx",
    ".less", ".lua", ".md", ".mjs", ".php", ".pl", ".ps1", ".py", ".rb",
    ".rs", ".rst", ".sass", ".scss", ".sh", ".sql", ".svg", ".toml",
    ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml", ".zsh",
}
STRUCTURED_ARTIFACT_UNSAFE_PATTERNS = (
    (
        "innerHTML assignment",
        re.compile(
            r"(?:\.innerHTML|\[\s*['\"]innerHTML['\"]\s*\])\s*\+?=(?!=)",
            re.IGNORECASE,
        ),
    ),
    (
        "outerHTML assignment",
        re.compile(
            r"(?:\.outerHTML|\[\s*['\"]outerHTML['\"]\s*\])\s*\+?=(?!=)",
            re.IGNORECASE,
        ),
    ),
    ("insertAdjacentHTML", re.compile(r"\.insertAdjacentHTML\s*\(", re.IGNORECASE)),
    (
        "document.write/writeln",
        re.compile(r"\bdocument\.(?:write|writeln)\s*\(", re.IGNORECASE),
    ),
    ("inline event attribute", re.compile(r"<[^>]+\s+on[a-z]+\s*=", re.IGNORECASE)),
    (
        "event-handler setAttribute",
        re.compile(r"\.setAttribute\s*\(\s*['\"]on[a-z]+['\"]", re.IGNORECASE),
    ),
    (
        "srcdoc assignment",
        re.compile(
            r"(?:\.srcdoc|\[\s*['\"]srcdoc['\"]\s*\])\s*\+?=(?!=)"
            r"|\.setAttribute\s*\(\s*['\"]srcdoc['\"]",
            re.IGNORECASE,
        ),
    ),
    (
        "dangerous raw HTML API",
        re.compile(
            r"\bdangerouslySetInnerHTML\b"
            r"|\.(?:createContextualFragment|setHTMLUnsafe)\s*\("
            r"|\bDocument\.parseHTMLUnsafe\s*\("
            r"|\.parseFromString\s*\([^,]+,\s*['\"]text/html['\"]",
            re.IGNORECASE,
        ),
    ),
    (
        "string-to-code sink",
        re.compile(
            r"\beval\s*\(|\b(?:new\s+)?Function\s*\("
            r"|\b(?:setTimeout|setInterval)\s*\(\s*['\"`]",
            re.IGNORECASE,
        ),
    ),
    (
        "Mermaid loose security",
        re.compile(r"securityLevel\s*:\s*['\"]loose['\"]", re.IGNORECASE),
    ),
    ("Mermaid callback directive", re.compile(r"(?m)^\s*click\s+\w+\s+\w+")),
)


def _validate_structured_artifact_resource(
    owner: str,
    relative: str,
    text: str,
    problems: list[str],
) -> None:
    findings: set[str] = set()
    for finding, pattern in STRUCTURED_ARTIFACT_UNSAFE_PATTERNS:
        if pattern.search(text):
            findings.add(finding)
    for finding in sorted(findings):
        problems.append(
            f"{owner}: unsafe executable HTML/JavaScript in {relative}: {finding}"
        )


def _load_object(
    path: Path,
    label: str,
    problems: list[str],
    unreadable_paths: set[Path] | None = None,
) -> dict[str, object] | None:
    if not path.is_file():
        problems.append(f"missing {label}: {path}")
        return None
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeError) as error:
        if unreadable_paths is not None:
            unreadable_paths.add(path)
        problems.append(f"invalid {label}: {error}")
        return None
    except json.JSONDecodeError as error:
        problems.append(f"invalid {label}: {error}")
        return None
    if not isinstance(value, dict):
        problems.append(f"invalid {label}: expected JSON object")
        return None
    return value


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _as_string_set(value: object) -> set[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return None
    return set(value)


def _check_exact_inventory(
    label: str,
    actual: set[str] | None,
    expected: set[str],
    problems: list[str],
) -> None:
    if actual is None:
        problems.append(f"{label} must be a list of strings")
        return
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing:
        problems.append(f"{label} missing: {', '.join(missing)}")
    if unexpected:
        problems.append(f"{label} unexpected: {', '.join(unexpected)}")


def _resolve_relative(base: Path, value: object, boundary: Path) -> Path | None:
    if not _nonempty_string(value):
        return None
    relative = Path(str(value))
    if relative.is_absolute():
        return None
    try:
        candidate = base / relative
        resolved = candidate.resolve()
        resolved.relative_to(boundary.resolve())
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate


def _is_within(path: Path, boundary: Path) -> bool:
    try:
        path.resolve().relative_to(boundary.resolve())
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def _has_symlink_component(path: Path, boundary: Path) -> bool:
    try:
        relative = path.absolute().relative_to(boundary.absolute())
    except ValueError:
        return True
    current = boundary
    for part in relative.parts:
        current = current / part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True
    return False


def _reject_control_symlink(
    path: Path,
    boundary: Path,
    label: str,
    problems: list[str],
) -> bool:
    if not _has_symlink_component(path, boundary):
        return False
    problems.append(f"{label} must not traverse symlinks")
    return True


def _outside_fences(text: str) -> str:
    segments: list[str] = []

    def collect(segment: str) -> str:
        segments.append(segment)
        return segment

    map_outside_fences(text, collect)
    return "".join(segments)


def _without_urls_outside_fences(text: str) -> str:
    return map_outside_fences(text, lambda segment: URL_RE.sub("", segment))


def _iter_relative_links(text: str):
    for line, fenced in iter_fenced_lines(text):
        for match in MARKDOWN_LINK_RE.finditer(line):
            target = match.group(1).strip()
            if fenced and ("{" in target or "<" in target):
                continue
            yield target


def _link_path(target: str) -> str:
    target = target.strip()
    if not target:
        return ""
    if target.startswith("<") and ">" in target:
        target = target[1:target.index(">")]
    else:
        fields = target.split(maxsplit=1)
        if not fields:
            return ""
        target = fields[0]
    target = target.split("#", 1)[0].split("?", 1)[0]
    return unquote(target)


def _worker_references(text: str) -> set[str]:
    references = set()
    for match in WORKER_REFERENCE_RE.finditer(text):
        name = match.group(1)
        if name in CSS_AT_RULES:
            continue
        references.add(name)
    return references


def _runtime_label(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _validate_manifest(
    repo_root: Path,
    problems: list[str],
) -> tuple[dict[str, object] | None, Path, bool]:
    plugin_root = repo_root / "plugins" / PLUGIN_NAME
    if _reject_control_symlink(
        plugin_root,
        repo_root,
        "canonical plugin root",
        problems,
    ):
        return None, plugin_root, False
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    if _reject_control_symlink(
        manifest_path,
        plugin_root,
        "canonical manifest",
        problems,
    ):
        return None, plugin_root, False
    manifest = _load_object(manifest_path, "canonical plugin manifest", problems)
    if manifest is None:
        return None, plugin_root, False

    identity = {
        "name": PLUGIN_NAME,
        "repository": REPOSITORY,
        "homepage": REPOSITORY,
        "license": "Apache-2.0",
        "skills": "./skills/",
    }
    for field, expected in identity.items():
        actual = manifest.get(field)
        if actual != expected:
            problems.append(f"canonical plugin {field} {actual} != {expected}")

    version = manifest.get("version")
    if not isinstance(version, str) or SEMVER_RE.fullmatch(version) is None:
        problems.append(f"canonical plugin version {version} is not strict semver")
    if not _nonempty_string(manifest.get("description")):
        problems.append("canonical plugin description must be nonempty")
    author = manifest.get("author")
    if not isinstance(author, dict) or author.get("name") != "InkyQuill":
        problems.append("canonical plugin author name must be InkyQuill")
    for forbidden in ("apps", "mcpServers", "hooks"):
        if forbidden in manifest:
            problems.append(f"canonical plugin must not declare {forbidden}")

    interface = manifest.get("interface")
    required_interface = {
        "displayName", "shortDescription", "longDescription", "developerName",
        "category", "capabilities", "websiteURL", "defaultPrompt",
    }
    if not isinstance(interface, dict):
        problems.append("canonical plugin interface must be an object")
    else:
        missing = sorted(required_interface - set(interface))
        if missing:
            problems.append(f"canonical plugin interface missing: {', '.join(missing)}")
        for field in ("displayName", "shortDescription", "longDescription"):
            if field in interface and not _nonempty_string(interface[field]):
                problems.append(f"canonical plugin interface {field} must be nonempty")
        if interface.get("developerName") != "InkyQuill":
            problems.append("canonical plugin interface developerName must be InkyQuill")
        if interface.get("category") != "Productivity":
            problems.append("canonical plugin interface category must be Productivity")
        if interface.get("websiteURL") != REPOSITORY:
            problems.append(f"canonical plugin interface websiteURL must be {REPOSITORY}")
        capabilities = interface.get("capabilities")
        if capabilities != ["Interactive", "Write"]:
            problems.append("canonical plugin interface capabilities must be Interactive, Write")
        prompts = interface.get("defaultPrompt")
        if not isinstance(prompts, list) or not prompts or any(not _nonempty_string(item) for item in prompts):
            problems.append("canonical plugin interface defaultPrompt must contain nonempty prompts")
        else:
            prompt_text = "\n".join(str(item) for item in prompts)
            for reference in sorted(extract_skill_references(prompt_text, "/")):
                problems.append(
                    f"canonical plugin interface: Claude-style reference /{reference} in defaultPrompt"
                )
            for reference in sorted(extract_skill_references(prompt_text, "$")):
                if reference not in EXPECTED_SKILLS:
                    problems.append(
                        f"canonical plugin interface: dangling skill reference ${reference}"
                    )

    skills_path = _resolve_relative(plugin_root, manifest.get("skills"), plugin_root)
    if skills_path is None or not skills_path.is_dir():
        problems.append("canonical plugin skills path ./skills/ does not exist")
    return manifest, plugin_root, True


def _validate_marketplace(repo_root: Path, problems: list[str]) -> None:
    path = repo_root / ".agents" / "plugins" / "marketplace.json"
    if _reject_control_symlink(path, repo_root, "Codex marketplace", problems):
        return
    marketplace = _load_object(path, "Codex marketplace", problems)
    if marketplace is None:
        return
    if marketplace.get("name") != PLUGIN_NAME:
        problems.append(f"marketplace name {marketplace.get('name')} != {PLUGIN_NAME}")
    interface = marketplace.get("interface")
    if not isinstance(interface, dict) or interface.get("displayName") != "Creative Writing Skills":
        problems.append("marketplace displayName must be Creative Writing Skills")
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
        problems.append("marketplace must contain exactly one plugin entry")
        return
    plugin = plugins[0]
    if plugin.get("name") != PLUGIN_NAME:
        problems.append(f"marketplace plugin name {plugin.get('name')} != {PLUGIN_NAME}")
    source = plugin.get("source")
    if not isinstance(source, dict):
        problems.append("marketplace source must be an object")
    else:
        if source.get("source") != "local":
            problems.append(f"marketplace source type {source.get('source')} != local")
        expected_path = "./plugins/creative-writing-skills"
        if source.get("path") != expected_path:
            problems.append(f"marketplace source path {source.get('path')} != {expected_path}")
        resolved = _resolve_relative(repo_root, source.get("path"), repo_root)
        if resolved is None or not resolved.is_dir():
            problems.append(f"marketplace source path {source.get('path')} does not exist")
    policy = plugin.get("policy")
    if not isinstance(policy, dict):
        problems.append("marketplace policy must be an object")
    else:
        if policy.get("installation") != "AVAILABLE":
            problems.append(
                f"marketplace installation policy {policy.get('installation')} != AVAILABLE"
            )
        if policy.get("authentication") != "ON_INSTALL":
            problems.append(
                f"marketplace authentication policy {policy.get('authentication')} != ON_INSTALL"
            )
    if plugin.get("category") != "Productivity":
        problems.append(f"marketplace category {plugin.get('category')} != Productivity")


def _validate_config(repo_root: Path, problems: list[str]) -> dict[str, object] | None:
    path = repo_root / "config" / "distribution.json"
    if _reject_control_symlink(path, repo_root, "distribution config", problems):
        return None
    config = _load_object(path, "distribution config", problems)
    if config is None:
        return None
    expected_keys = {"canonical_skills", "authored_skills", "vendored_skills", "workers", "claude"}
    if set(config) != expected_keys:
        problems.append(
            "distribution config keys must be canonical_skills, authored_skills, "
            "vendored_skills, workers, claude"
        )
    inventories = (
        ("canonical skill registry", "canonical_skills", EXPECTED_SKILLS),
        ("authored skill registry", "authored_skills", AUTHORED_SKILLS),
        ("vendored skill registry", "vendored_skills", VENDORED_SKILLS),
    )
    for label, field, expected in inventories:
        value = config.get(field)
        actual = _as_string_set(value)
        _check_exact_inventory(label, actual, expected, problems)
        if isinstance(value, list) and len(value) != len(set(map(str, value))):
            problems.append(f"{label} contains duplicates")
    if config.get("workers") != "skills/creative-writing-muse/resources/workers/registry.json":
        problems.append("distribution config workers path is not canonical")
    claude = config.get("claude")
    expected_claude_keys = {
        "root",
        "marketplace",
        "disable_model_invocation",
    }
    if not isinstance(claude, dict) or set(claude) != expected_claude_keys:
        problems.append("distribution config Claude fields do not match schema")
        return config
    if (
        claude.get("root") != "cw"
        or claude.get("marketplace") != ".claude-plugin/marketplace.json"
    ):
        problems.append("distribution config Claude paths are not canonical")
    disabled = claude.get("disable_model_invocation")
    valid_disabled = isinstance(disabled, list) and all(
        isinstance(skill, str) and re.fullmatch(r"[a-z][a-z0-9-]*", skill)
        for skill in disabled
    )
    if not valid_disabled:
        problems.append(
            "distribution config Claude disable_model_invocation must be a list of skill names"
        )
    else:
        if len(disabled) != len(set(disabled)):
            problems.append(
                "distribution config Claude disable_model_invocation contains duplicates"
            )
        if disabled != sorted(disabled):
            problems.append(
                "distribution config Claude disable_model_invocation must be sorted"
            )
        unexpected = sorted(set(disabled) - EXPECTED_SKILLS)
        if unexpected:
            problems.append(
                "distribution config Claude disable_model_invocation is not a subset "
                f"of canonical skills: {', '.join(unexpected)}"
            )
        if disabled != list(CLAUDE_DISABLE_MODEL_INVOCATION):
            problems.append(
                "distribution config Claude disable_model_invocation does not match "
                "the compatibility policy"
            )
    return config


def _validate_frontmatter(skill_name: str, text: str, problems: list[str]) -> None:
    try:
        metadata, body = split_frontmatter(text)
    except ValueError as error:
        problems.append(f"{skill_name}: invalid frontmatter: {error}")
        return
    extra = sorted(set(metadata) - ALLOWED_FRONTMATTER_KEYS)
    if extra:
        problems.append(f"{skill_name}: unsupported frontmatter keys {', '.join(extra)}")
    if metadata.get("name") != skill_name:
        problems.append(
            f"{skill_name}: frontmatter name {metadata.get('name')} != directory name"
        )
    if not _nonempty_string(metadata.get("description")):
        problems.append(f"{skill_name}: frontmatter description must be nonempty")
    if "disable-model-invocation" in metadata:
        value = metadata["disable-model-invocation"]
        if not isinstance(value, bool):
            problems.append(f"{skill_name}: disable-model-invocation must be boolean")
        elif value is True:
            problems.append(
                f"{skill_name}: disable-model-invocation true is Claude-only"
            )
    if "argument-hint" in metadata and not _nonempty_string(metadata["argument-hint"]):
        problems.append(f"{skill_name}: argument-hint must be nonempty")
    if not body.strip():
        problems.append(f"{skill_name}: skill body must be nonempty")


def _validate_markdown(
    skill_name: str,
    path: Path,
    skill_root: Path,
    text: str,
    worker_names: set[str],
    problems: list[str],
) -> None:
    for target in _iter_relative_links(text):
        relative = _link_path(target)
        resolved = _resolve_relative(path.parent, relative, skill_root)
        if not relative or resolved is None or not resolved.exists():
            display_target = target or "<empty>"
            problems.append(f"{skill_name}: missing relative resource {display_target}")

    instructional_paths = extract_instructional_relative_path_contexts(text)
    for target, context_references in sorted(
        instructional_paths,
        key=lambda item: (item[0], sorted(item[1])),
    ):
        relative = _link_path(target)
        candidates = [skill_root]
        explicit_targets = sorted(
            (context_references & EXPECTED_SKILLS) - {skill_name}
        )
        if explicit_targets:
            candidates = (
                [skill_root.parent / explicit_targets[0]]
                if len(explicit_targets) == 1
                else []
            )
        found = False
        if relative:
            for candidate_root in candidates:
                resolved = _resolve_relative(
                    candidate_root,
                    relative,
                    candidate_root,
                )
                if resolved is not None and resolved.exists():
                    found = True
                    break
        if not found:
            problems.append(f"{skill_name}: missing relative resource {target}")

    reference_text = _without_urls_outside_fences(text)
    for reference in sorted(extract_skill_references(reference_text, "/")):
        problems.append(
            f"{skill_name}: Claude-style reference /{reference} in canonical Codex skill"
        )
    for reference in sorted(extract_skill_references(reference_text, "$")):
        if reference not in EXPECTED_SKILLS:
            problems.append(f"{skill_name}: dangling skill reference ${reference}")

    visible = _outside_fences(reference_text)
    if "CLAUDE.md" in visible:
        problems.append(f"{skill_name}: Claude-only vocabulary CLAUDE.md")
    for reference in sorted(_worker_references(visible) - worker_names):
        problems.append(f"{skill_name}: dangling worker reference @{reference}")


def _validate_skills(
    plugin_root: Path,
    worker_names: set[str],
    unreadable_paths: set[Path],
    problems: list[str],
) -> None:
    skills_root = plugin_root / "skills"
    if skills_root.is_symlink():
        problems.append("canonical skills root must not be a symlink")
        return
    if not skills_root.is_dir():
        _check_exact_inventory("canonical skill directories", set(), EXPECTED_SKILLS, problems)
        return
    if not _is_within(skills_root, plugin_root):
        problems.append("canonical skills root escapes canonical plugin root")
        return
    directories = {
        path.name: path
        for path in skills_root.iterdir()
        if path.is_dir() or path.is_symlink()
    }
    _check_exact_inventory("canonical skill directories", set(directories), EXPECTED_SKILLS, problems)
    for skill_name, skill_root in sorted(directories.items()):
        if skill_root.is_symlink():
            problems.append(f"{skill_name}: skill directory must not be a symlink")
            continue
        if not skill_root.is_dir() or not _is_within(skill_root, skills_root):
            problems.append(f"{skill_name}: skill directory escapes canonical skills root")
            continue
        skill_file = skill_root / "SKILL.md"
        if not skill_file.is_file() and not skill_file.is_symlink():
            problems.append(f"{skill_name}: missing SKILL.md")
        for path in sorted(skill_root.rglob("*")):
            relative = _runtime_label(path, skill_root)
            if path.is_symlink():
                problems.append(
                    f"{skill_name}: runtime resource {relative} must not be a symlink"
                )
                continue
            if path.is_dir():
                if not _is_within(path, skill_root):
                    problems.append(
                        f"{skill_name}: runtime resource {relative} escapes skill root"
                    )
                continue
            if not path.is_file() or path.suffix.lower() not in TEXT_RUNTIME_SUFFIXES:
                continue
            if path in unreadable_paths:
                continue
            if not _is_within(path, skill_root):
                problems.append(f"{skill_name}: runtime resource {relative} escapes skill root")
                continue
            try:
                text = path.read_text()
            except (OSError, UnicodeError) as error:
                problems.append(f"{skill_name}: cannot read {relative}: {error}")
                continue
            if path == skill_file:
                _validate_frontmatter(skill_name, text, problems)
            if path.suffix.lower() == ".md":
                _validate_markdown(
                    skill_name,
                    path,
                    skill_root,
                    text,
                    worker_names,
                    problems,
                )
            if skill_name == "structured-artifact":
                _validate_structured_artifact_resource(
                    skill_name,
                    relative,
                    text,
                    problems,
                )
            for match in PLATFORM_VOCABULARY_RE.finditer(text):
                problems.append(
                    f"{skill_name}: forbidden canonical runtime vocabulary {match.group(0)}"
                )


def _validate_workers(
    plugin_root: Path,
    config: dict[str, object] | None,
    unreadable_paths: set[Path],
    problems: list[str],
) -> set[str]:
    registry_value = (
        config.get("workers") if config is not None
        else "skills/creative-writing-muse/resources/workers/registry.json"
    )
    registry_candidate = plugin_root / Path(str(registry_value))
    if _reject_control_symlink(
        registry_candidate,
        plugin_root,
        "worker registry",
        problems,
    ):
        return set()
    registry_path = _resolve_relative(plugin_root, registry_value, plugin_root)
    if registry_path is None:
        problems.append(f"worker registry path {registry_value} is not a safe relative path")
        return set()
    registry = _load_object(
        registry_path,
        "worker registry",
        problems,
        unreadable_paths,
    )
    if registry is None:
        return set()
    if set(registry) != {"workers"}:
        problems.append("worker registry must contain only workers")
    workers = registry.get("workers")
    if not isinstance(workers, list):
        problems.append("worker registry workers must be a list")
        return set()

    names: set[str] = set()
    prompts: set[str] = set()
    for index, worker in enumerate(workers):
        if not isinstance(worker, dict):
            problems.append(f"worker entry {index}: must be an object")
            continue
        name_value = worker.get("name")
        name = name_value if isinstance(name_value, str) else f"entry-{index}"
        if set(worker) != WORKER_KEYS:
            problems.append(f"worker {name}: registry fields do not match schema")
        if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
            problems.append(f"worker {name}: invalid name")
        if name in names:
            problems.append(f"worker {name}: duplicate name")
        names.add(name)
        if not _nonempty_string(worker.get("description")):
            problems.append(f"worker {name}: description must be nonempty")

        prompt_value = worker.get("prompt")
        if not _nonempty_string(prompt_value):
            problems.append(f"worker {name}: prompt must be a relative path")
        else:
            prompt = str(prompt_value)
            if prompt in prompts:
                problems.append(f"worker {name}: duplicate prompt path {prompt}")
            prompts.add(prompt)
            resolved = _resolve_relative(registry_path.parent, prompt, registry_path.parent)
            if resolved is None or not resolved.is_file():
                problems.append(f"worker {name}: missing prompt {prompt}")

        skill_values = worker.get("skills")
        if not isinstance(skill_values, list) or any(
            not isinstance(skill, str) for skill in skill_values
        ):
            problems.append(f"worker {name}: skills must be a list of strings")
        else:
            if len(skill_values) != len(set(skill_values)):
                problems.append(f"worker {name}: duplicate skill mapping")
            skill_set = set(skill_values)
            for skill in sorted(skill_set - EXPECTED_SKILLS):
                problems.append(f"worker {name}: dangling skill mapping {skill}")
            if name in EXPECTED_WORKER_SKILLS and skill_set != EXPECTED_WORKER_SKILLS[name]:
                problems.append(
                    f"worker {name}: skill mapping does not match canonical registry"
                )

        access = worker.get("access")
        if access not in {"read-only", "workspace-write"}:
            problems.append(f"worker {name}: invalid access {access}")
        if name in READ_ONLY_WORKERS and access != "read-only":
            problems.append(f"worker {name}: review role must be read-only")
        if name in EXPECTED_WORKERS - READ_ONLY_WORKERS and access == "read-only":
            problems.append(f"worker {name}: production role must be workspace-write")

        claude = worker.get("claude")
        if not isinstance(claude, dict) or set(claude) != {"model", "background"}:
            problems.append(f"worker {name}: claude metadata does not match schema")
        elif claude.get("model") != "inherit" or not isinstance(claude.get("background"), bool):
            problems.append(f"worker {name}: invalid claude metadata")
        elif name in EXPECTED_WORKERS and claude.get("background") != (name == "web-researcher"):
            problems.append(f"worker {name}: claude background setting does not match canonical registry")

    _check_exact_inventory("worker registry", names, EXPECTED_WORKERS, problems)
    return names


def _validate_claude_frontmatter(
    text: str,
    label: str,
    skill_name: str,
    disable_model_invocation: bool,
    problems: list[str],
) -> None:
    try:
        metadata, body = split_frontmatter(text)
    except ValueError as error:
        problems.append(f"{label}: invalid frontmatter: {error}")
        return
    if metadata.get("name") != skill_name:
        problems.append(f"{label}: frontmatter name must be {skill_name}")
    if not _nonempty_string(metadata.get("description")):
        problems.append(f"{label}: description must be nonempty")
    value = metadata.get("disable-model-invocation")
    if disable_model_invocation:
        if value is not True:
            problems.append(f"{label}: disable-model-invocation must be true")
    elif "disable-model-invocation" in metadata:
        problems.append(
            f"{label}: disable-model-invocation is not configured for {skill_name}"
        )
    if not body.strip():
        problems.append(f"{label}: body must be nonempty")


def _validate_claude_distribution(
    repo_root: Path,
    config: dict[str, object] | None,
    canonical_manifest: dict[str, object] | None,
    worker_names: set[str],
    problems: list[str],
) -> None:
    claude_root_value: object = "cw"
    marketplace_value: object = ".claude-plugin/marketplace.json"
    disabled_skills = set(CLAUDE_DISABLE_MODEL_INVOCATION)
    if config is not None and isinstance(config.get("claude"), dict):
        claude_config = config["claude"]
        claude_root_value = claude_config.get("root", claude_root_value)
        marketplace_value = claude_config.get("marketplace", marketplace_value)
        configured_disabled = claude_config.get("disable_model_invocation")
        if (
            isinstance(configured_disabled, list)
            and all(isinstance(skill, str) for skill in configured_disabled)
            and len(configured_disabled) == len(set(configured_disabled))
            and configured_disabled == sorted(configured_disabled)
            and set(configured_disabled) <= EXPECTED_SKILLS
            and configured_disabled == list(CLAUDE_DISABLE_MODEL_INVOCATION)
        ):
            disabled_skills = set(configured_disabled)
    claude_root_candidate = repo_root / Path(str(claude_root_value))
    if claude_root_candidate.is_symlink():
        problems.append("cw root must not be a symlink")
        return
    claude_root = _resolve_relative(repo_root, claude_root_value, repo_root)
    if claude_root is None:
        if claude_root_candidate.exists():
            problems.append("cw root escapes repository root")
        return
    if not claude_root.exists():
        return

    manifest_path = claude_root / ".claude-plugin" / "plugin.json"
    if _reject_control_symlink(
        manifest_path,
        claude_root,
        "cw plugin manifest",
        problems,
    ):
        manifest = None
    else:
        manifest = _load_object(manifest_path, "cw plugin manifest", problems)
    canonical_version = canonical_manifest.get("version") if canonical_manifest else None
    if manifest is not None and canonical_manifest is not None:
        claude_version = manifest.get("version")
        if claude_version != canonical_version:
            problems.append(
                f"cw plugin version {claude_version} != canonical version {canonical_version}"
            )
        for field in ("name", "description", "author", "homepage", "repository", "license"):
            if manifest.get(field) != canonical_manifest.get(field):
                problems.append(f"cw plugin {field} does not match canonical manifest")

    skill_root = claude_root / "skills"
    valid_skill_root = True
    if skill_root.is_symlink():
        problems.append("cw skills root must not be a symlink")
        valid_skill_root = False
    elif skill_root.exists() and not _is_within(skill_root, claude_root):
        problems.append("cw skills root escapes Claude root")
        valid_skill_root = False
    skill_dirs = (
        {
            path.name: path
            for path in skill_root.iterdir()
            if path.is_dir() or path.is_symlink()
        }
        if valid_skill_root and skill_root.is_dir() else {}
    )
    _check_exact_inventory("cw skill directories", set(skill_dirs), EXPECTED_SKILLS, problems)
    rejected_skill_dirs: set[Path] = set()
    for name, directory in sorted(skill_dirs.items()):
        if directory.is_symlink():
            problems.append(f"cw skill {name}: directory must not be a symlink")
            rejected_skill_dirs.add(directory)
            continue
        if not directory.is_dir() or not _is_within(directory, skill_root):
            problems.append(f"cw skill {name}: directory escapes Claude skills root")
            rejected_skill_dirs.add(directory)
            continue
        path = directory / "SKILL.md"
        relative = path.relative_to(repo_root)
        if not path.is_file() and not path.is_symlink():
            problems.append(f"{relative.as_posix()}: missing generated skill")

    agent_root = claude_root / "agents"
    valid_agent_root = True
    if agent_root.is_symlink():
        problems.append("cw agents root must not be a symlink")
        valid_agent_root = False
    elif agent_root.exists() and not _is_within(agent_root, claude_root):
        problems.append("cw agents root escapes Claude root")
        valid_agent_root = False
    agents = (
        {path.stem for path in agent_root.glob("*.md") if path.is_file()}
        if valid_agent_root and agent_root.is_dir() else set()
    )
    _check_exact_inventory("cw agent files", agents, worker_names | {"muse"}, problems)

    marketplace_candidate = repo_root / Path(str(marketplace_value))
    if _reject_control_symlink(
        marketplace_candidate,
        repo_root,
        "Claude marketplace",
        problems,
    ):
        marketplace_path = None
        marketplace_rejected = True
    else:
        marketplace_path = _resolve_relative(repo_root, marketplace_value, repo_root)
        marketplace_rejected = False
    if marketplace_path is None and not marketplace_rejected:
        problems.append(f"Claude marketplace path {marketplace_value} is not a safe relative path")
    elif marketplace_path is not None:
        marketplace = _load_object(marketplace_path, "Claude marketplace", problems)
        if marketplace is not None and canonical_manifest is not None:
            metadata = marketplace.get("metadata")
            version = metadata.get("version") if isinstance(metadata, dict) else None
            if version != canonical_version:
                problems.append(
                    f"Claude marketplace version {version} != canonical version {canonical_version}"
                )
            owner = marketplace.get("owner")
            if not isinstance(owner, dict) or owner.get("name") != "InkyQuill":
                problems.append("Claude marketplace owner name must be InkyQuill")
            entries = marketplace.get("plugins")
            if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
                problems.append("Claude marketplace must contain exactly one plugin entry")
            else:
                entry = entries[0]
                if entry.get("name") != PLUGIN_NAME:
                    problems.append(f"Claude marketplace plugin name must be {PLUGIN_NAME}")
                if entry.get("source") != "./cw":
                    problems.append("Claude marketplace plugin source must be ./cw")
                if entry.get("description") != canonical_manifest.get("description"):
                    problems.append("Claude marketplace description does not match canonical manifest")

    runtime_paths = set()
    runtime_roots = []
    if valid_agent_root:
        runtime_roots.append(agent_root)
    if valid_skill_root:
        runtime_roots.append(skill_root)
    for runtime_root in runtime_roots:
        if runtime_root.is_dir():
            runtime_paths.update(runtime_root.rglob("*"))
    for path in sorted(runtime_paths):
        label = _runtime_label(path, repo_root)
        if path in rejected_skill_dirs:
            continue
        if path.is_symlink():
            problems.append(f"{label}: runtime resource must not be a symlink")
            continue
        if path.is_dir():
            if not _is_within(path, claude_root):
                problems.append(f"{label}: runtime resource escapes Claude root")
            continue
        if not path.is_file() or path.suffix.lower() not in TEXT_RUNTIME_SUFFIXES:
            continue
        if not _is_within(path, claude_root):
            problems.append(f"{label}: runtime resource escapes Claude root")
            continue
        try:
            text = path.read_text()
        except (OSError, UnicodeError) as error:
            problems.append(f"{label}: cannot read: {error}")
            continue
        structured_artifact_root = skill_root / "structured-artifact"
        if valid_skill_root and _is_within(path, structured_artifact_root):
            _validate_structured_artifact_resource(
                "cw/skills/structured-artifact",
                _runtime_label(path, structured_artifact_root),
                text,
                problems,
            )
        if (
            path.name == "SKILL.md"
            and path.parent.parent == skill_root
            and path.parent.name in skill_dirs
        ):
            _validate_claude_frontmatter(
                text,
                label,
                path.parent.name,
                path.parent.name in disabled_skills,
                problems,
            )
        visible = _outside_fences(_without_urls_outside_fences(text))
        for token in ("AGENTS.md", "spawn_agent", "collaboration."):
            if token in visible:
                problems.append(f"{label}: Codex-only vocabulary {token}")
        for reference in sorted(extract_skill_references(_without_urls_outside_fences(text), "$")):
            problems.append(f"{label}: Codex-only skill reference ${reference}")
        for reference in sorted(extract_skill_references(text, "/")):
            if reference not in EXPECTED_SKILLS:
                problems.append(f"{label}: dangling Claude skill reference /{reference}")
        for reference in sorted(_worker_references(visible) - worker_names):
            problems.append(f"{label}: dangling worker reference @{reference}")
        for match in PLATFORM_VOCABULARY_RE.finditer(text):
            problems.append(f"{label}: forbidden runtime vocabulary {match.group(0)}")


def validate(repo_root: Path, *, canonical_only: bool = False) -> list[str]:
    repo_root = Path(repo_root)
    problems: list[str] = []
    unreadable_paths: set[Path] = set()
    manifest, plugin_root, canonical_safe = _validate_manifest(repo_root, problems)
    _validate_marketplace(repo_root, problems)
    config = _validate_config(repo_root, problems)
    if canonical_safe:
        workers = _validate_workers(plugin_root, config, unreadable_paths, problems)
        effective_workers = workers if workers == EXPECTED_WORKERS else EXPECTED_WORKERS
        _validate_skills(plugin_root, effective_workers, unreadable_paths, problems)
    else:
        effective_workers = EXPECTED_WORKERS
    if not canonical_only:
        _validate_claude_distribution(
            repo_root,
            config,
            manifest,
            effective_workers,
            problems,
        )
    return list(dict.fromkeys(problems))


def main(argv: list[str] | None = None, *, repo_root: Path = REPO_ROOT) -> int:
    parser = argparse.ArgumentParser(description="Validate plugin distributions")
    parser.add_argument(
        "--canonical-only",
        action="store_true",
        help="skip checks for the generated Claude compatibility distribution",
    )
    args = parser.parse_args(argv)
    problems = validate(repo_root, canonical_only=args.canonical_only)
    if problems:
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("Distribution validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
