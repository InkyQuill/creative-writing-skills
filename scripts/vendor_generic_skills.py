#!/usr/bin/env python3
"""Vendor the licensed generic skills used by the Codex plugin."""

import argparse
import filecmp
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

if __package__:
    from scripts.distribution import map_outside_fences
else:
    from distribution import map_outside_fences


REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "distribution.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "plugins" / "creative-writing-skills" / "skills"
_SKILL_NAME_RE = re.compile(r"[a-z][a-z0-9-]*\Z")
_SLASH_SKILL_RE = re.compile(r"(?<![A-Za-z0-9_.</%-])/([a-z][a-z0-9-]*)(?!(?:[A-Za-z0-9/-]|\.[A-Za-z0-9]))")
_QI_OWNERSHIP = "`/qi-maintenance` owns when colocated knowledge must move with source changes."
_QI_DESCRIPTION = (
    "description: 'Use when writing or maintaining AGENTS.md, .context/CONTEXT.md, "
    "or CLAUDE.md mirrors: keep intent docs minimal and load-bearing.'"
)
_QI_DESCRIPTION_ADAPTATION = (
    "description: 'Use when writing or maintaining harness instruction files and "
    ".context/CONTEXT.md: keep intent docs minimal and load-bearing.'"
)
_QI_ADAPTATION = (
    "When colocated knowledge changes, keep its AGENTS.md and .context "
    "documentation synchronized with the source in the same change."
)
_QI_MIRROR_COMMAND = (
    "Run `meridian qi claude-md-fix <target-root>` on the containing tree\n"
    "after creating or moving AGENTS.md files: it creates missing mirrors, skips\n"
    "exact ones, and reports anything else as a conflict.\n\n"
    "Never write shared instructions into CLAUDE.md. Claude-only knowledge is\n"
    "rare; when it exists, put it below the `@AGENTS.md` import and expect\n"
    "`claude-md-fix` to keep flagging the file, so the divergence stays visible."
)
_QI_MIRROR_SECTION = (
    "## CLAUDE.md Mirrors\n\n"
    "Claude harnesses read CLAUDE.md, not AGENTS.md. Give every AGENTS.md a\n"
    "sibling CLAUDE.md whose first line is `@AGENTS.md` — normally the whole\n"
    f"file. {_QI_MIRROR_COMMAND}\n\n"
    "Loading differs by level. At the root, each harness auto-loads its own\n"
    "file every session: Claude reads CLAUDE.md, others read AGENTS.md. In\n"
    "subdirectories, Claude auto-injects CLAUDE.md when it touches files there;\n"
    "other agents see nested AGENTS.md only by reading it on entry. Don't lean\n"
    "on Claude's auto-injection: a nested AGENTS.md carries the local additions\n"
    "an agent needs on entry, with everything else inherited from ancestors."
)
_QI_MIRROR_ADAPTATION = (
    "## Harness Instruction Files\n\n"
    "Use the instruction filename required by the active harness at each directory. "
    "When multiple harness entry points share guidance, each may import one distinct "
    "canonical source but must never import itself. After creating or moving "
    "instruction files, inspect the containing tree: create missing mirrors, leave "
    "exact mirrors unchanged, and report divergent files as conflicts.\n\n"
    "Keep shared instructions in one canonical source. Put harness-only guidance in "
    "the applicable entry point, and treat intentional divergence as a conflict that "
    "requires explicit review rather than silently overwriting it.\n\n"
    "At every directory, work from the active harness's instruction file and read any "
    "applicable local instructions on entry. Do not rely on harness-specific automatic "
    "loading when another tool may need the same local guidance."
)
_KNOWLEDGE_BOOTSTRAP_LAYOUT = (
    "```\n"
    "kb/\n"
    "  AGENTS.md          # intent: what belongs here, key rules\n"
    "  .context/\n"
    "    CONTEXT.md       # governance depth: writing conventions, structure, validation\n"
    "  index.md           # catalog of pages with one-line summaries\n"
    "  vocab.md           # project-wide terminology\n"
    "```"
)
_KNOWLEDGE_BOOTSTRAP_LAYOUT_ADAPTATION = (
    "```\n"
    "kb/\n"
    "  {instruction-file}  # active harness instructions: intent and key rules\n"
    "  .context/\n"
    "    CONTEXT.md         # governance depth: writing conventions, structure, validation\n"
    "  index.md             # catalog of pages with one-line summaries\n"
    "  vocab.md             # project-wide terminology\n"
    "```"
)
_KNOWLEDGE_BOOTSTRAP_HEADING = "## Starter AGENTS.md"
_KNOWLEDGE_BOOTSTRAP_HEADING_ADAPTATION = "## Starter instruction file"
_MERMAID_COMMAND = "Validate with `meridian mermaid check`."
_MERMAID_ADAPTATION = (
    "Validate with an available Mermaid parser or renderer, and report syntax errors "
    "before delivery."
)
_GRILL_INSTRUCTION_FILE = (
    "2. Project conventions in `CLAUDE.md` — established names and labels."
)
_GRILL_INSTRUCTION_FILE_ADAPTATION = (
    "2. Project conventions in `AGENTS.md` — established names and labels."
)
_LLM_DISK_DRAFT = (
    "3. **Draft.** Write a full draft to disk so you can edit it piece by piece."
)
_LLM_DISK_DRAFT_ADAPTATION = (
    "3. **Draft.** For an explicitly writable artifact task, write the draft only "
    "to the caller-assigned path and revise it there. Otherwise, draft and revise "
    "in the response context without creating or changing files."
)
_TREE_RENDERING = '''function renderNode(n) {
  if (!n.children) return `<li class="leaf">${n.name}</li>`;
  return `<li><details open><summary>${n.name}</summary><ul>${
    n.children.map(renderNode).join("")
  }</ul></details></li>`;
}

document.getElementById("tree").innerHTML = `<ul>${renderNode(data)}</ul>`;'''
_TREE_RENDERING_ADAPTATION = '''function renderNode(n) {
  const item = document.createElement("li");
  if (!n.children) {
    item.className = "leaf";
    item.textContent = n.name;
    return item;
  }

  const details = document.createElement("details");
  details.open = true;
  const summary = document.createElement("summary");
  summary.textContent = n.name;
  const children = document.createElement("ul");
  n.children.forEach(child => children.append(renderNode(child)));
  details.append(summary, children);
  item.append(details);
  return item;
}

const treeList = document.createElement("ul");
treeList.append(renderNode(data));
document.getElementById("tree").replaceChildren(treeList);'''
_TOC_RENDERING = '''const headings = [...document.querySelectorAll("#doc h2, #doc h3")];
document.getElementById("toc").innerHTML = headings
  .map(h => `<a href="#${h.id}" data-id="${h.id}">${h.textContent}</a><br>`)
  .join("");

const links = [...document.querySelectorAll("#toc a")];'''
_TOC_RENDERING_ADAPTATION = '''const headings = [...document.querySelectorAll("#doc h2, #doc h3")];
const toc = document.getElementById("toc");
headings.forEach(heading => {
  const link = document.createElement("a");
  link.href = `#${encodeURIComponent(heading.id)}`;
  link.dataset.id = heading.id;
  link.textContent = heading.textContent;
  toc.append(link, document.createElement("br"));
});

const links = [...toc.querySelectorAll("a")];'''
_MERMAID_CONFIG = '''mermaid.initialize({
  startOnLoad: false,
  theme: document.documentElement.classList.contains('dark') ? 'dark' : 'default',
  securityLevel: 'loose',  // required for click callbacks
  flowchart: { curve: 'basis', nodeSpacing: 50, rankSpacing: 60 },
});
await mermaid.run({ querySelector: '.mermaid' });'''
_MERMAID_CONFIG_ADAPTATION = '''mermaid.initialize({
  startOnLoad: false,
  theme: document.documentElement.classList.contains('dark') ? 'dark' : 'default',
  securityLevel: 'strict',
  flowchart: { curve: 'basis', nodeSpacing: 50, rankSpacing: 60 },
});
await mermaid.run({ querySelector: '.mermaid' });'''
_MERMAID_LOOSE_NOTE = (
    "`securityLevel: 'loose'` lets `click` directives call your JS. Without it, callbacks\n"
    "are silently dropped."
)
_MERMAID_STRICT_NOTE = (
    "Keep `securityLevel: 'strict'`. Bind interactions after rendering and only "
    "for node IDs present in the detail allow-list."
)
_MERMAID_CLICK_BINDING = '''### Click Callbacks

Two approaches — use whichever fits your graph:

**Mermaid `click` directives** (simpler, requires valid JS identifiers as node IDs):

```mermaid
flowchart TD
  api[API Layer] --> svc[Service]
  click api showDetail "api"
  click svc showDetail "svc"
```

**Post-render DOM binding** (works with any node ID):

```js
document.querySelectorAll('#diagram .node').forEach(node => {
  node.style.cursor = 'pointer';
  node.addEventListener('click', () => {
    const id = node.id.replace(/^flowchart-/, '').replace(/-\\d+$/, '');
    showDetail(id);
  });
});
```'''
_MERMAID_CLICK_BINDING_ADAPTATION = '''### Post-render Click Binding

Do not use Mermaid `click` directives or global callbacks. Declare the exact
detail keys the page supports, keep them aligned with `DETAIL`, and bind only
those nodes after Mermaid renders:

```js
const ALLOWED_DETAIL_KEYS = new Set(['api']);

document.querySelectorAll('#diagram .node').forEach(node => {
  const key = node.id.replace(/^flowchart-/, '').replace(/-\\d+$/, '');
  if (!ALLOWED_DETAIL_KEYS.has(key)) return;
  node.style.cursor = 'pointer';
  node.addEventListener('click', () => showDetail(key));
});
```'''
_DETAIL_RENDERING = '''function showDetail(key) {
  const d = DETAIL[key]; if (!d) return;
  document.getElementById('detail-title').textContent = d.title;
  document.getElementById('detail-desc').textContent = d.desc;
  if (d.code && window.hljs) {
    document.getElementById('detail-code').innerHTML =
      `<pre><code>${hljs.highlight(d.code, { language: d.lang }).value}</code></pre>`;
  }
  document.getElementById('detail-panel').classList.remove('collapsed');
}'''
_DETAIL_RENDERING_ADAPTATION = '''function showDetail(key) {
  if (!ALLOWED_DETAIL_KEYS.has(key)) return;
  const d = DETAIL[key];
  document.getElementById('detail-title').textContent = d.title;
  document.getElementById('detail-desc').textContent = d.desc;
  const codeHost = document.getElementById('detail-code');
  if (d.code) {
    const pre = document.createElement('pre');
    const code = document.createElement('code');
    code.className = `language-${d.lang}`;
    code.textContent = d.code;
    pre.append(code);
    codeHost.replaceChildren(pre);
    if (window.hljs) hljs.highlightElement(code);
  } else {
    codeHost.replaceChildren();
  }
  document.getElementById('detail-panel').classList.remove('collapsed');
}'''
_LOOSE_CALLBACK_NOTE = (
    "`showDetail` must be on `window` (a top-level `function` declaration) so Mermaid's\n"
    "loose-mode callback can reach it."
)
_STRICT_CALLBACK_NOTE = (
    "`showDetail` stays local; strict mode never invokes it from diagram text."
)


@dataclass(frozen=True)
class VendorSource:
    url: str
    commit: str
    skills_path: str
    license: str


SOURCE = VendorSource(
    url="https://github.com/haowjy/creative-writing-skills.git",
    commit="fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3",
    skills_path="cw/skills",
    license="Apache-2.0",
)


class VendorDriftError(RuntimeError):
    """Raised when generated vendored skills differ from their source snapshot."""


def distribution() -> dict[str, object]:
    value = json.loads(CONFIG_PATH.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {CONFIG_PATH}")
    return value


def vendored_skills() -> tuple[str, ...]:
    skills = distribution()["vendored_skills"]
    if not isinstance(skills, list) or not all(isinstance(skill, str) for skill in skills):
        raise ValueError("config/distribution.json vendored_skills must be a list of strings")
    return tuple(skills)


def canonical_skills() -> set[str]:
    skills = distribution()["canonical_skills"]
    if not isinstance(skills, list) or not all(isinstance(skill, str) for skill in skills):
        raise ValueError("config/distribution.json canonical_skills must be a list of strings")
    return set(skills)


def validated_vendored_skills() -> tuple[str, ...]:
    skills = vendored_skills()
    canonical = canonical_skills()
    if len(set(skills)) != len(skills):
        raise ValueError("config/distribution.json vendored_skills must not contain duplicates")
    for skill in skills:
        if _SKILL_NAME_RE.fullmatch(skill) is None:
            raise ValueError(f"config/distribution.json has invalid vendored skill name: {skill!r}")
        if skill not in canonical:
            raise ValueError(f"config/distribution.json vendored skill is not canonical: {skill}")
    return skills


def normalize_codex_references(text: str, canonical_skills: set[str], skill_name: str) -> str:
    """Convert Claude slash skill references outside fenced code blocks to Codex syntax."""

    def normalize(segment_text: str) -> str:
        def replace(match: re.Match[str]) -> str:
            reference = match.group(1)
            if reference not in canonical_skills:
                raise ValueError(f"{skill_name}: unbundled skill reference /{reference}")
            return f"${reference}"

        return _SLASH_SKILL_RE.sub(replace, segment_text)

    return map_outside_fences(text, normalize)


def _adapt_markdown(
    text: str,
    skill_name: str,
    known_skills: set[str],
    relative_path: Path,
) -> str:
    is_skill_document = relative_path == Path("SKILL.md")
    if skill_name == "grill-with-docs" and is_skill_document:
        if _GRILL_INSTRUCTION_FILE not in text:
            raise ValueError(
                "grill-with-docs: expected licensed instruction-file reference was not found"
            )
        text = text.replace(
            _GRILL_INSTRUCTION_FILE,
            _GRILL_INSTRUCTION_FILE_ADAPTATION,
            1,
        )
    if skill_name == "llm-writing" and is_skill_document:
        if _LLM_DISK_DRAFT not in text:
            raise ValueError(
                "llm-writing: expected licensed disk-draft instruction was not found"
            )
        text = text.replace(_LLM_DISK_DRAFT, _LLM_DISK_DRAFT_ADAPTATION, 1)
    if skill_name == "qi-layer" and is_skill_document:
        if _QI_DESCRIPTION not in text:
            raise ValueError("qi-layer: expected licensed description was not found")
        text = text.replace(_QI_DESCRIPTION, _QI_DESCRIPTION_ADAPTATION, 1)
        if _QI_OWNERSHIP not in text:
            raise ValueError("qi-layer: expected licensed ownership sentence was not found")
        text = text.replace(_QI_OWNERSHIP, _QI_ADAPTATION, 1)
        if _QI_MIRROR_SECTION not in text:
            raise ValueError("qi-layer: expected licensed mirror section was not found")
        text = text.replace(_QI_MIRROR_SECTION, _QI_MIRROR_ADAPTATION, 1)
    if (
        skill_name == "knowledge-layers"
        and relative_path == Path("resources/bootstrap.md")
    ):
        if _KNOWLEDGE_BOOTSTRAP_LAYOUT not in text:
            raise ValueError(
                "knowledge-layers: expected licensed bootstrap layout was not found"
            )
        if _KNOWLEDGE_BOOTSTRAP_HEADING not in text:
            raise ValueError(
                "knowledge-layers: expected licensed bootstrap heading was not found"
            )
        text = text.replace(
            _KNOWLEDGE_BOOTSTRAP_LAYOUT,
            _KNOWLEDGE_BOOTSTRAP_LAYOUT_ADAPTATION,
            1,
        )
        text = text.replace(
            _KNOWLEDGE_BOOTSTRAP_HEADING,
            _KNOWLEDGE_BOOTSTRAP_HEADING_ADAPTATION,
            1,
        )
    if (
        skill_name == "structured-artifact"
        and relative_path == Path("resources/tree-and-toc.md")
    ):
        if _TREE_RENDERING not in text:
            raise ValueError(
                "structured-artifact: expected licensed tree rendering example was not found"
            )
        if _TOC_RENDERING not in text:
            raise ValueError(
                "structured-artifact: expected licensed TOC rendering example was not found"
            )
        text = text.replace(_TREE_RENDERING, _TREE_RENDERING_ADAPTATION, 1)
        text = text.replace(_TOC_RENDERING, _TOC_RENDERING_ADAPTATION, 1)
    if skill_name == "structured-artifact" and relative_path == Path("resources/diagrams.md"):
        if _MERMAID_COMMAND not in text:
            raise ValueError("structured-artifact: expected licensed Mermaid command was not found")
        expected_examples = (
            ("Mermaid configuration", _MERMAID_CONFIG),
            ("Mermaid loose-mode note", _MERMAID_LOOSE_NOTE),
            ("Mermaid click-binding example", _MERMAID_CLICK_BINDING),
            ("detail rendering example", _DETAIL_RENDERING),
            ("loose callback note", _LOOSE_CALLBACK_NOTE),
        )
        for label, source in expected_examples:
            if source not in text:
                raise ValueError(
                    f"structured-artifact: expected licensed {label} was not found"
                )
        text = text.replace(_MERMAID_COMMAND, _MERMAID_ADAPTATION, 1)
        text = text.replace(_MERMAID_CONFIG, _MERMAID_CONFIG_ADAPTATION, 1)
        text = text.replace(_MERMAID_LOOSE_NOTE, _MERMAID_STRICT_NOTE, 1)
        text = text.replace(
            _MERMAID_CLICK_BINDING,
            _MERMAID_CLICK_BINDING_ADAPTATION,
            1,
        )
        text = text.replace(_DETAIL_RENDERING, _DETAIL_RENDERING_ADAPTATION, 1)
        text = text.replace(_LOOSE_CALLBACK_NOTE, _STRICT_CALLBACK_NOTE, 1)
    return normalize_codex_references(text, known_skills, skill_name)


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _require_safe_directory(
    path: Path,
    label: str,
    *,
    allow_missing_leaf: bool = False,
    boundary: Path | None = None,
) -> Path:
    absolute = _absolute(path)
    if absolute == Path(absolute.anchor):
        raise ValueError(f"{label} must not be a filesystem root")

    if boundary is None:
        current = absolute.parent
        parts = (absolute.name,)
    else:
        boundary = _absolute(boundary)
        try:
            relative = absolute.relative_to(boundary)
        except ValueError as error:
            raise ValueError(f"{label} escapes its boundary: {absolute}") from error
        current = boundary
        parts = relative.parts
    for index, part in enumerate(parts):
        current = current / part
        is_leaf = index == len(parts) - 1
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError as error:
            if allow_missing_leaf and is_leaf:
                return absolute
            raise ValueError(f"{label} does not exist: {current}") from error
        except OSError as error:
            raise ValueError(f"cannot inspect {label}: {current}: {error}") from error
        if stat.S_ISLNK(mode):
            raise ValueError(f"{label} is a symlink: {current}")
        if not stat.S_ISDIR(mode):
            raise ValueError(f"{label} is not a directory: {current}")
    return absolute


def _preflight_source_tree(source: Path, skill_name: str) -> None:
    def walk(directory: Path) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as error:
            raise ValueError(
                f"{skill_name}: cannot inspect licensed source: {directory}: {error}"
            ) from error
        for entry in entries:
            entry_path = Path(entry.path)
            relative = entry_path.relative_to(source)
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as error:
                raise ValueError(
                    f"{skill_name}: cannot inspect source entry {relative}: {error}"
                ) from error
            if stat.S_ISLNK(mode):
                raise ValueError(
                    f"{skill_name}: source entry is a symlink: {relative}"
                )
            if stat.S_ISDIR(mode):
                walk(entry_path)
            elif not stat.S_ISREG(mode):
                raise ValueError(
                    f"{skill_name}: source entry is not a regular file: {relative}"
                )

    walk(source)
    skill_file = source / "SKILL.md"
    try:
        mode = os.lstat(skill_file).st_mode
    except FileNotFoundError as error:
        raise ValueError(f"{skill_name}: missing SKILL.md in licensed source") from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ValueError(f"{skill_name}: SKILL.md must be a regular file")


def _copy_source_tree(source: Path, destination: Path, skill_name: str) -> None:
    destination.mkdir()
    for entry in sorted(os.scandir(source), key=lambda item: item.name):
        source_entry = Path(entry.path)
        destination_entry = destination / entry.name
        relative = source_entry.relative_to(source)
        try:
            mode = entry.stat(follow_symlinks=False).st_mode
        except OSError as error:
            raise ValueError(
                f"{skill_name}: cannot inspect source entry {relative}: {error}"
            ) from error
        if stat.S_ISLNK(mode):
            raise ValueError(f"{skill_name}: source entry is a symlink: {relative}")
        if stat.S_ISDIR(mode):
            _copy_source_tree(source_entry, destination_entry, skill_name)
        elif stat.S_ISREG(mode):
            shutil.copy2(source_entry, destination_entry, follow_symlinks=False)
        else:
            raise ValueError(
                f"{skill_name}: source entry is not a regular file: {relative}"
            )


def _copy_skill(source: Path, destination: Path, skill_name: str, known_skills: set[str]) -> None:
    _copy_source_tree(source, destination, skill_name)
    for markdown in destination.rglob("*.md"):
        markdown.write_text(
            _adapt_markdown(
                markdown.read_text(),
                skill_name,
                known_skills,
                markdown.relative_to(destination),
            )
        )


def _replace_directory(staged: Path, destination: Path) -> None:
    backup_root: Path | None = None
    backup: Path | None = None
    keep_backup = False
    try:
        if destination.exists():
            backup_root = Path(tempfile.mkdtemp(prefix=f".{destination.name}.vendor-backup-", dir=destination.parent))
            backup = backup_root / "previous"
            os.replace(destination, backup)
        os.replace(staged, destination)
    except BaseException:
        if backup is not None and backup.exists():
            try:
                os.replace(backup, destination)
            except BaseException:
                keep_backup = True
                raise
        raise
    finally:
        if backup_root is not None and not keep_backup:
            shutil.rmtree(backup_root)


def render_from_checkout(checkout: Path, output_root: Path) -> None:
    """Render configured skill snapshots from a licensed source checkout."""

    configured_skills = validated_vendored_skills()
    known_skills = canonical_skills()
    checkout = _require_safe_directory(checkout, "licensed checkout boundary")
    source_root = _require_safe_directory(
        checkout / SOURCE.skills_path,
        "licensed source root boundary",
        boundary=checkout,
    )
    sources: dict[str, Path] = {}
    for skill_name in configured_skills:
        source = _require_safe_directory(
            source_root / skill_name,
            f"{skill_name} licensed source skill boundary",
            boundary=source_root,
        )
        _preflight_source_tree(source, skill_name)
        sources[skill_name] = source

    output_root = _absolute(output_root)
    _require_safe_directory(
        output_root.parent,
        "vendor output parent boundary",
    )
    output_exists = output_root.exists()
    _require_safe_directory(
        output_root,
        "vendor output root boundary",
        allow_missing_leaf=True,
        boundary=output_root.parent,
    )
    if output_root == checkout or checkout in output_root.parents:
        raise ValueError("vendor output root must be outside the licensed checkout")
    if output_exists:
        for skill_name in configured_skills:
            destination = output_root / skill_name
            try:
                mode = os.lstat(destination).st_mode
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(mode):
                raise ValueError(
                    f"{skill_name}: vendor output skill boundary is a symlink"
                )
            if not stat.S_ISDIR(mode):
                raise ValueError(
                    f"{skill_name}: vendor output skill boundary is not a directory"
                )

    with tempfile.TemporaryDirectory(
        prefix=".vendor-generic-skills-render-",
        dir=output_root.parent,
    ) as temporary:
        staged_root = Path(temporary) / "skills"
        staged_root.mkdir()
        for skill_name in configured_skills:
            staged = staged_root / skill_name
            _copy_skill(sources[skill_name], staged, skill_name, known_skills)
        output_root.mkdir(exist_ok=True)
        for skill_name in configured_skills:
            staged = staged_root / skill_name
            _replace_directory(staged, output_root / skill_name)


def _relative_files(root: Path) -> set[Path]:
    if not root.exists():
        return set()
    return {path.relative_to(root) for path in root.rglob("*") if path.is_file()}


def _drifted_files(expected_root: Path, output_root: Path) -> list[str]:
    changed: list[str] = []
    for skill_name in validated_vendored_skills():
        expected = expected_root / skill_name
        actual = output_root / skill_name
        expected_files = _relative_files(expected)
        actual_files = _relative_files(actual)
        for relative in sorted(expected_files | actual_files):
            expected_file = expected / relative
            actual_file = actual / relative
            if not expected_file.is_file() or not actual_file.is_file() or not filecmp.cmp(expected_file, actual_file, shallow=False):
                changed.append((Path(skill_name) / relative).as_posix())
    return changed


def check_checkout(checkout: Path, output_root: Path) -> None:
    """Raise a concise drift error if the output differs from a source render."""

    with tempfile.TemporaryDirectory(prefix="vendor-generic-skills-check-") as temporary:
        expected_root = Path(temporary) / "skills"
        render_from_checkout(checkout, expected_root)
        changed = _drifted_files(expected_root, output_root)
    if changed:
        raise VendorDriftError("vendored skill drift:\n" + "\n".join(changed))


@contextmanager
def source_checkout(source_checkout: Path | None) -> Iterator[Path]:
    if source_checkout is not None:
        yield _absolute(source_checkout)
        return

    with tempfile.TemporaryDirectory(prefix="vendor-generic-skills-source-") as temporary:
        checkout = Path(temporary) / "source"
        subprocess.run(
            ["git", "clone", "--filter=blob:none", "--no-checkout", SOURCE.url, str(checkout)],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(checkout), "checkout", SOURCE.commit, "--", SOURCE.skills_path],
            check=True,
        )
        yield checkout


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="refresh the vendored skill snapshots")
    mode.add_argument("--check", action="store_true", help="verify the vendored skill snapshots")
    parser.add_argument("--source-checkout", type=Path, help="use an existing licensed source checkout")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with source_checkout(args.source_checkout) as checkout:
        if args.apply:
            render_from_checkout(checkout, DEFAULT_OUTPUT_ROOT)
            for skill_name in vendored_skills():
                print(f"synced {skill_name}")
            return 0
        try:
            check_checkout(checkout, DEFAULT_OUTPUT_ROOT)
        except VendorDriftError as error:
            print(error)
            return 1
    print(f"{len(vendored_skills())} vendored skills in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
