import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from scripts.vendor_generic_skills import (
    SOURCE,
    VendorDriftError,
    check_checkout,
    normalize_codex_references,
    render_from_checkout,
    source_checkout,
)


TREE_SOURCE = '''# Tree and TOC

```html
function renderNode(n) {
  if (!n.children) return `<li class="leaf">${n.name}</li>`;
  return `<li><details open><summary>${n.name}</summary><ul>${
    n.children.map(renderNode).join("")
  }</ul></details></li>`;
}

document.getElementById("tree").innerHTML = `<ul>${renderNode(data)}</ul>`;
```

```html
const headings = [...document.querySelectorAll("#doc h2, #doc h3")];
document.getElementById("toc").innerHTML = headings
  .map(h => `<a href="#${h.id}" data-id="${h.id}">${h.textContent}</a><br>`)
  .join("");

const links = [...document.querySelectorAll("#toc a")];
```
'''


DIAGRAM_SOURCE = '''# Diagrams

Validate with `meridian mermaid check`.

```js
mermaid.initialize({
  startOnLoad: false,
  theme: document.documentElement.classList.contains('dark') ? 'dark' : 'default',
  securityLevel: 'loose',  // required for click callbacks
  flowchart: { curve: 'basis', nodeSpacing: 50, rankSpacing: 60 },
});
await mermaid.run({ querySelector: '.mermaid' });
```

`securityLevel: 'loose'` lets `click` directives call your JS. Without it, callbacks
are silently dropped.

### Click Callbacks

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
```

```js
const DETAIL = {
  api: {
    title: 'API Layer',
    desc: 'Entry point. Validates payload, hands off to service.',
    files: ['src/api/orders.ts:14'],
    code: `app.post('/orders', validate(schema), handler);`,
    lang: 'typescript',
  },
};

function showDetail(key) {
  const d = DETAIL[key]; if (!d) return;
  document.getElementById('detail-title').textContent = d.title;
  document.getElementById('detail-desc').textContent = d.desc;
  if (d.code && window.hljs) {
    document.getElementById('detail-code').innerHTML =
      `<pre><code>${hljs.highlight(d.code, { language: d.lang }).value}</code></pre>`;
  }
  document.getElementById('detail-panel').classList.remove('collapsed');
}
```

`showDetail` must be on `window` (a top-level `function` declaration) so Mermaid's
loose-mode callback can reach it.
'''


CARD_GRID_SOURCE = '''# Card Grid

```html
function renderCards() {
  const q = document.getElementById("cardSearch").value.toLowerCase();
  const s = document.getElementById("cardSort").value;
  document.getElementById("cards").innerHTML = items
    .filter(x => JSON.stringify(x).toLowerCase().includes(q))
    .sort((a, b) => (a[s] > b[s] ? 1 : -1))
    .map(x => `<button class="card" onclick="showDetail('${x.name}')">
      <b>${x.name}</b><br><span style="color:var(--muted)">${x.type}</span>
    </button>`)
    .join("");
}

document.getElementById("cardSearch").oninput = renderCards;
document.getElementById("cardSort").onchange = renderCards;
renderCards();
```
'''

DATA_TABLE_SOURCE = '''# Data Table

```html
<input id="search" placeholder="Search..." oninput="applyFilter()">
<div id="table"></div>
<script>
function applyFilter() {
  const q = document.getElementById("search").value.toLowerCase();
  table.setFilter(row =>
    Object.values(row).join(" ").toLowerCase().includes(q)
  );
}

table.on("rowClick", showDetail);
</script>
```
'''

MULTI_PAGE_SOURCE = '''# Multi Page

```html
<header>
  <a href="index.html">← Index</a>
  <span class="crumb">Runtime loop</span>
  <button onclick="toggleTheme()">☀/🌙</button>
</header>
```
'''

DIFF_VIEW_SOURCE = '''# Diff View

```html
<div>
  <button onclick="renderDiff('side-by-side')">Side by Side</button>
  <button onclick="renderDiff('line-by-line')">Unified</button>
</div>
<script>
function renderDiff(mode) {
  const el = document.getElementById("diff");
  el.innerHTML = "";
  return mode;
}
renderDiff("side-by-side");
</script>
```
'''


class VendorGenericSkillsTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        )
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.checkout = self.root / "checkout"
        self.output = self.root / "output"
        skill = self.checkout / "cw" / "skills" / "demo"
        (skill / "resources").mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: demo\n---\n\n# Demo\n")
        (skill / "resources" / "guide.md").write_text("Guide\n")
        self.vendored_skills = patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("demo",),
        )
        self.vendored_skills.start()
        self.addCleanup(self.vendored_skills.stop)
        self.canonical_skills = patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"demo"},
        )
        self.canonical_skills.start()
        self.addCleanup(self.canonical_skills.stop)

    def test_render_copies_complete_skill_directory(self):
        render_from_checkout(self.checkout, self.output)
        self.assertEqual(
            (self.output / "demo" / "SKILL.md").read_text(),
            (self.checkout / "cw" / "skills" / "demo" / "SKILL.md").read_text(),
        )
        self.assertTrue((self.output / "demo" / "resources" / "guide.md").is_file())

    def test_render_strips_claude_only_invocation_metadata_from_codex_skill(self):
        skill = self.checkout / "cw" / "skills" / "demo" / "SKILL.md"
        skill.write_text(
            "---\n"
            "name: demo\n"
            "description: Demo.\n"
            "disable-model-invocation: true\n"
            "---\n"
            "# Demo\n"
        )

        render_from_checkout(self.checkout, self.output)

        rendered = (self.output / "demo" / "SKILL.md").read_text()
        self.assertNotIn("disable-model-invocation", rendered)
        self.assertIn("description: Demo.", rendered)

    def test_render_updates_a_preexisting_safe_output_root(self):
        self.output.mkdir()
        render_from_checkout(self.checkout, self.output)
        self.assertIn("# Demo", (self.output / "demo/SKILL.md").read_text())

    def test_check_reports_changed_vendored_file(self):
        render_from_checkout(self.checkout, self.output)
        (self.output / "demo" / "SKILL.md").write_text("changed\n")
        with self.assertRaisesRegex(VendorDriftError, "demo/SKILL.md"):
            check_checkout(self.checkout, self.output)

    def test_check_reports_byte_identical_nested_output_symlink_as_type_drift(self):
        render_from_checkout(self.checkout, self.output)
        rendered = self.output / "demo" / "resources" / "guide.md"
        external = self.root / "external-guide.md"
        external.write_bytes(rendered.read_bytes())
        rendered.unlink()
        rendered.symlink_to(external)

        with self.assertRaisesRegex(
            VendorDriftError,
            r"demo/resources/guide\.md.*expected file, found symlink",
        ):
            check_checkout(self.checkout, self.output)

        self.assertEqual(b"Guide\n", external.read_bytes())

    def test_source_is_licensed_snapshot_not_meridian_base(self):
        self.assertEqual(SOURCE.license, "Apache-2.0")
        self.assertEqual(SOURCE.commit, "fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3")
        self.assertNotIn("meridian-base", SOURCE.url)

    def test_normalizer_changes_known_skill_refs_but_preserves_shell_and_urls(self):
        source = "Use /story-memory.\n```bash\necho $chapter\n```\nhttps://example.com/story-memory\n"
        rendered = normalize_codex_references(source, {"story-memory"}, "demo")
        self.assertIn("Use $story-memory.", rendered)
        self.assertIn("echo $chapter", rendered)
        self.assertIn("https://example.com/story-memory", rendered)

    def test_normalizer_rejects_unbundled_skill_reference(self):
        with self.assertRaisesRegex(ValueError, "qi-layer: unbundled skill reference /qi-maintenance"):
            normalize_codex_references("Load /qi-maintenance.\n", {"qi-layer"}, "qi-layer")

    def test_render_adapts_qi_layer_mirror_command_without_losing_behavior(self):
        source = self.checkout / "cw" / "skills" / "qi-layer"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\n"
            "name: qi-layer\n"
            "description: 'Use when writing or maintaining AGENTS.md, .context/CONTEXT.md, or CLAUDE.md mirrors: keep intent docs minimal and load-bearing.'\n"
            "---\n"
            "`/qi-maintenance` owns when colocated knowledge must move with source changes.\n"
            "## CLAUDE.md Mirrors\n\n"
            "Claude harnesses read CLAUDE.md, not AGENTS.md. Give every AGENTS.md a\n"
            "sibling CLAUDE.md whose first line is `@AGENTS.md` — normally the whole\n"
            "file. Run `meridian qi claude-md-fix <target-root>` on the containing tree\n"
            "after creating or moving AGENTS.md files: it creates missing mirrors, skips\n"
            "exact ones, and reports anything else as a conflict.\n\n"
            "Never write shared instructions into CLAUDE.md. Claude-only knowledge is\n"
            "rare; when it exists, put it below the `@AGENTS.md` import and expect\n"
            "`claude-md-fix` to keep flagging the file, so the divergence stays visible.\n\n"
            "Loading differs by level. At the root, each harness auto-loads its own\n"
            "file every session: Claude reads CLAUDE.md, others read AGENTS.md. In\n"
            "subdirectories, Claude auto-injects CLAUDE.md when it touches files there;\n"
            "other agents see nested AGENTS.md only by reading it on entry. Don't lean\n"
            "on Claude's auto-injection: a nested AGENTS.md carries the local additions\n"
            "an agent needs on entry, with everything else inherited from ancestors.\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills", return_value=("qi-layer",)
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills", return_value={"qi-layer"}
        ):
            render_from_checkout(self.checkout, self.output)
        rendered = (self.output / "qi-layer" / "SKILL.md").read_text()
        self.assertNotIn("meridian", rendered.lower())
        self.assertNotIn("claude-md-fix", rendered)
        self.assertIn("`$project-bootstrap` owns filenames", rendered)
        self.assertIn("canonical path it resolves", rendered)
        self.assertIn("Do not duplicate entrypoint logic here", rendered)
        self.assertNotIn("sibling CLAUDE.md", rendered)
        self.assertNotIn("@AGENTS.md", rendered)
        self.assertIn(
            "description: 'Use when writing or maintaining harness instruction files "
            "and .context/CONTEXT.md: keep intent docs minimal and load-bearing.'",
            rendered,
        )

    def test_render_adapts_knowledge_bootstrap_to_instruction_placeholder(self):
        source = self.checkout / "cw" / "skills" / "knowledge-layers"
        (source / "resources").mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: knowledge-layers\n---\nBody.\n"
        )
        (source / "resources/bootstrap.md").write_text(
            "## Directory Layout\n\n"
            "```\n"
            "kb/\n"
            "  AGENTS.md          # intent: what belongs here, key rules\n"
            "  .context/\n"
            "    CONTEXT.md       # governance depth: writing conventions, structure, validation\n"
            "  index.md           # catalog of pages with one-line summaries\n"
            "  vocab.md           # project-wide terminology\n"
            "```\n\n"
            "## Starter AGENTS.md\n\n"
            "```markdown\n"
            "## Validation\n\n"
            "Use `/md-validation` for link checking and diagram validation before\n"
            "committing.\n"
            "```\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("knowledge-layers",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"knowledge-layers", "md-validation"},
        ):
            render_from_checkout(self.checkout, self.output)

        rendered = (
            self.output / "knowledge-layers/resources/bootstrap.md"
        ).read_text()
        self.assertIn(
            "{project-instructions} # resolved project instructions: intent and key rules",
            rendered,
        )
        self.assertIn("## Starter project instructions", rendered)
        self.assertNotIn("AGENTS.md", rendered)
        self.assertIn("Use `$md-validation` for link checking", rendered)
        self.assertNotIn("Use `/md-validation` for link checking", rendered)

    def test_bootstrap_semantic_adaptation_rejects_source_drift(self):
        source = self.checkout / "cw" / "skills" / "knowledge-layers"
        (source / "resources").mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: knowledge-layers\n---\nBody.\n"
        )
        (source / "resources/bootstrap.md").write_text(
            "## Directory Layout\n\n"
            "```\n"
            "kb/\n"
            "  AGENTS.md          # intent: what belongs here, key rules\n"
            "  .context/\n"
            "    CONTEXT.md       # governance depth: writing conventions, structure, validation\n"
            "  index.md           # catalog of pages with one-line summaries\n"
            "  vocab.md           # project-wide terminology\n"
            "```\n\n"
            "## Starter AGENTS.md\n\n"
            "```markdown\nUse changed validation guidance before committing.\n```\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("knowledge-layers",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"knowledge-layers", "md-validation"},
        ):
            with self.assertRaisesRegex(
                ValueError,
                "expected licensed bootstrap validation instruction",
            ):
                render_from_checkout(self.checkout, self.output)

    def test_bootstrap_semantic_adaptation_rejects_unknown_skill_reference(self):
        source = self.checkout / "cw" / "skills" / "knowledge-layers"
        (source / "resources").mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: knowledge-layers\n---\nBody.\n"
        )
        (source / "resources/bootstrap.md").write_text(
            "## Directory Layout\n\n"
            "```\n"
            "kb/\n"
            "  AGENTS.md          # intent: what belongs here, key rules\n"
            "  .context/\n"
            "    CONTEXT.md       # governance depth: writing conventions, structure, validation\n"
            "  index.md           # catalog of pages with one-line summaries\n"
            "  vocab.md           # project-wide terminology\n"
            "```\n\n"
            "## Starter AGENTS.md\n\n"
            "```markdown\n"
            "Use `/md-validation` for link checking and diagram validation before\n"
            "committing.\n"
            "```\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("knowledge-layers",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"knowledge-layers"},
        ):
            with self.assertRaisesRegex(
                ValueError,
                "unbundled skill reference /md-validation",
            ):
                render_from_checkout(self.checkout, self.output)

    def test_qi_adaptation_rejects_unrecognized_licensed_source(self):
        source = self.checkout / "cw" / "skills" / "qi-layer"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\n"
            "name: qi-layer\n"
            "description: 'Changed upstream description.'\n"
            "---\n"
            "`/qi-maintenance` owns when colocated knowledge must move with source changes.\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills", return_value=("qi-layer",)
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills", return_value={"qi-layer"}
        ):
            with self.assertRaisesRegex(ValueError, "expected licensed description"):
                render_from_checkout(self.checkout, self.output)

    def test_bootstrap_adaptation_rejects_unrecognized_licensed_source(self):
        source = self.checkout / "cw" / "skills" / "knowledge-layers"
        (source / "resources").mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: knowledge-layers\n---\nBody.\n"
        )
        (source / "resources/bootstrap.md").write_text(
            "## Directory Layout\n\nChanged upstream layout.\n\n## Starter AGENTS.md\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("knowledge-layers",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"knowledge-layers"},
        ):
            with self.assertRaisesRegex(ValueError, "expected licensed bootstrap layout"):
                render_from_checkout(self.checkout, self.output)

    def test_render_adapts_mermaid_validation_command(self):
        source = self.checkout / "cw" / "skills" / "structured-artifact"
        (source / "resources").mkdir(parents=True)
        (source / "SKILL.md").write_text("---\nname: structured-artifact\n---\nBody.\n")
        (source / "resources" / "diagrams.md").write_text(DIAGRAM_SOURCE)
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("structured-artifact",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"structured-artifact"},
        ):
            render_from_checkout(self.checkout, self.output)
        rendered = (
            self.output / "structured-artifact" / "resources" / "diagrams.md"
        ).read_text()
        self.assertNotIn("meridian", rendered.lower())
        self.assertIn("available Mermaid parser or renderer", rendered)
        self.assertIn("report syntax errors before delivery", rendered)

    def test_render_maps_upstream_grill_to_local_decision_grill(self):
        source = self.checkout / "cw" / "skills" / "grill-with-docs"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: grill-with-docs\n---\n"
            "# Grill With Docs\n\n"
            "2. Project conventions in `CLAUDE.md` — established names and labels.\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("decision-grill",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"decision-grill"},
        ):
            render_from_checkout(self.checkout, self.output)

        self.assertFalse((self.output / "grill-with-docs").exists())
        rendered = (self.output / "decision-grill/SKILL.md").read_text()
        self.assertIn("name: decision-grill", rendered)
        self.assertIn("# Decision Grill", rendered)
        self.assertNotIn("name: grill-with-docs", rendered)
        self.assertNotIn("# Grill With Docs", rendered)
        self.assertIn("Resolved project instructions", rendered)
        self.assertNotIn("AGENTS.md", rendered)
        self.assertNotIn("CLAUDE.md", rendered)

    def test_check_reports_mapped_skill_drift_under_local_name(self):
        source = self.checkout / "cw" / "skills" / "grill-with-docs"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: grill-with-docs\n---\n"
            "# Grill With Docs\n\n"
            "2. Project conventions in `CLAUDE.md` — established names and labels.\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("decision-grill",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"decision-grill"},
        ):
            render_from_checkout(self.checkout, self.output)
            check_checkout(self.checkout, self.output)
            (self.output / "decision-grill/SKILL.md").write_text("changed\n")
            with self.assertRaisesRegex(
                VendorDriftError,
                "decision-grill/SKILL.md",
            ):
                check_checkout(self.checkout, self.output)

    def test_grill_adaptation_rejects_unrecognized_licensed_source(self):
        source = self.checkout / "cw" / "skills" / "grill-with-docs"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: grill-with-docs\n---\n"
            "# Grill With Docs\n\n"
            "2. Changed project conventions wording.\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("decision-grill",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"decision-grill"},
        ):
            with self.assertRaisesRegex(ValueError, "licensed instruction-file reference"):
                render_from_checkout(self.checkout, self.output)

    def test_render_does_not_rename_unmapped_skill_content(self):
        source = self.checkout / "cw" / "skills" / "intent-modeling"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: intent-modeling\n---\n"
            "# Grill With Docs is merely mentioned here\n"
            "The upstream name grill-with-docs is example prose.\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("intent-modeling",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"intent-modeling"},
        ):
            render_from_checkout(self.checkout, self.output)

        rendered = (self.output / "intent-modeling/SKILL.md").read_text()
        self.assertIn("# Grill With Docs is merely mentioned here", rendered)
        self.assertIn("upstream name grill-with-docs", rendered)

    def test_render_adapts_llm_writing_disk_boundary(self):
        source = self.checkout / "cw" / "skills" / "llm-writing"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: llm-writing\n---\n"
            "3. **Draft.** Write a full draft to disk so you can edit it piece by piece.\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("llm-writing",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"llm-writing"},
        ):
            render_from_checkout(self.checkout, self.output)

        rendered = (self.output / "llm-writing/SKILL.md").read_text()
        self.assertIn("explicitly writable artifact", rendered)
        self.assertIn("caller-assigned path", rendered)
        self.assertIn("response context", rendered)
        self.assertNotIn("Write a full draft to disk so you can edit it piece by piece", rendered)

    def test_llm_writing_adaptation_rejects_unrecognized_licensed_source(self):
        source = self.checkout / "cw" / "skills" / "llm-writing"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: llm-writing\n---\n3. **Draft.** Changed upstream.\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("llm-writing",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"llm-writing"},
        ):
            with self.assertRaisesRegex(ValueError, "licensed disk-draft instruction"):
                render_from_checkout(self.checkout, self.output)

    def test_render_hardens_structured_artifact_examples(self):
        source = self.checkout / "cw" / "skills" / "structured-artifact"
        (source / "resources").mkdir(parents=True)
        (source / "SKILL.md").write_text("---\nname: structured-artifact\n---\nBody.\n")
        (source / "resources/tree-and-toc.md").write_text(TREE_SOURCE)
        (source / "resources/diagrams.md").write_text(DIAGRAM_SOURCE)
        (source / "resources/card-grid.md").write_text(CARD_GRID_SOURCE)
        (source / "resources/data-table.md").write_text(DATA_TABLE_SOURCE)
        (source / "resources/multi-page-site.md").write_text(MULTI_PAGE_SOURCE)
        (source / "resources/diff-view.md").write_text(DIFF_VIEW_SOURCE)
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("structured-artifact",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"structured-artifact"},
        ):
            render_from_checkout(self.checkout, self.output)

        tree = (self.output / "structured-artifact/resources/tree-and-toc.md").read_text()
        diagrams = (self.output / "structured-artifact/resources/diagrams.md").read_text()
        cards = (self.output / "structured-artifact/resources/card-grid.md").read_text()
        data_table = (self.output / "structured-artifact/resources/data-table.md").read_text()
        multi_page = (self.output / "structured-artifact/resources/multi-page-site.md").read_text()
        diff_view = (self.output / "structured-artifact/resources/diff-view.md").read_text()
        self.assertNotIn("innerHTML", tree)
        self.assertNotIn("innerHTML", diagrams)
        self.assertIn("textContent", tree)
        self.assertIn("replaceChildren", tree)
        self.assertIn("securityLevel: 'strict'", diagrams)
        self.assertNotIn("securityLevel: 'loose'", diagrams)
        self.assertNotRegex(diagrams, r"(?m)^\s*click\s+\w+\s+\w+")
        self.assertIn("ALLOWED_DETAIL_KEYS", diagrams)
        self.assertNotIn("new Set(Object.keys(DETAIL))", diagrams)
        self.assertIn("const d = DETAIL[key];\n  if (!d) return;", diagrams)
        self.assertNotIn("innerHTML", cards)
        self.assertNotIn("onclick", cards)
        self.assertIn("createElement", cards)
        self.assertIn("textContent", cards)
        self.assertIn("addEventListener", cards)
        self.assertIn("replaceChildren", cards)
        self.assertIn(
            ".sort((a, b) => (a[s] === b[s] ? 0 : a[s] > b[s] ? 1 : -1))",
            cards,
        )
        for rendered in (data_table, multi_page, diff_view):
            self.assertNotRegex(rendered, r"\son[a-z]+=", msg=rendered)
            self.assertIn("addEventListener", rendered)
        self.assertNotIn("innerHTML", diff_view)
        self.assertIn("replaceChildren", diff_view)

    def test_card_grid_security_adaptation_rejects_source_drift(self):
        source = self.checkout / "cw" / "skills" / "structured-artifact"
        (source / "resources").mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: structured-artifact\n---\nBody.\n"
        )
        (source / "resources/card-grid.md").write_text(
            CARD_GRID_SOURCE.replace("function renderCards()", "function drawCards()")
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("structured-artifact",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"structured-artifact"},
        ):
            with self.assertRaisesRegex(
                ValueError,
                "expected licensed card-grid rendering example",
            ):
                render_from_checkout(self.checkout, self.output)

    def test_card_grid_security_adaptation_rejects_duplicate_source_block(self):
        source = self.checkout / "cw" / "skills" / "structured-artifact"
        (source / "resources").mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: structured-artifact\n---\nBody.\n"
        )
        (source / "resources/card-grid.md").write_text(
            CARD_GRID_SOURCE + "\n" + CARD_GRID_SOURCE
        )
        self.output.mkdir()
        sentinel = self.output / "sentinel.txt"
        sentinel.write_text("unchanged\n")
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("structured-artifact",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"structured-artifact"},
        ):
            with self.assertRaisesRegex(
                ValueError,
                "card-grid rendering example.*exactly once; found 2",
            ):
                render_from_checkout(self.checkout, self.output)
        self.assertEqual("unchanged\n", sentinel.read_text())

    def test_bootstrap_adaptation_rejects_duplicate_source_block(self):
        source = self.checkout / "cw" / "skills" / "knowledge-layers"
        (source / "resources").mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: knowledge-layers\n---\nBody.\n"
        )
        validation = (
            "Use `/md-validation` for link checking and diagram validation before\n"
            "committing."
        )
        (source / "resources/bootstrap.md").write_text(
            "## Directory Layout\n\n"
            "```\n"
            "kb/\n"
            "  AGENTS.md          # intent: what belongs here, key rules\n"
            "  .context/\n"
            "    CONTEXT.md       # governance depth: writing conventions, structure, validation\n"
            "  index.md           # catalog of pages with one-line summaries\n"
            "  vocab.md           # project-wide terminology\n"
            "```\n\n"
            "## Starter AGENTS.md\n\n"
            f"```markdown\n{validation}\n\n{validation}\n```\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("knowledge-layers",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"knowledge-layers", "md-validation"},
        ):
            with self.assertRaisesRegex(
                ValueError,
                "bootstrap validation instruction.*exactly once; found 2",
            ):
                render_from_checkout(self.checkout, self.output)

    def test_existing_grill_adaptation_rejects_duplicate_source_block(self):
        source = self.checkout / "cw" / "skills" / "grill-with-docs"
        source.mkdir(parents=True)
        instruction = (
            "2. Project conventions in `CLAUDE.md` — established names and labels."
        )
        (source / "SKILL.md").write_text(
            "---\nname: grill-with-docs\n---\n"
            "# Grill With Docs\n\n"
            f"{instruction}\n{instruction}\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("decision-grill",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"decision-grill"},
        ):
            with self.assertRaisesRegex(
                ValueError,
                "instruction-file reference.*exactly once; found 2",
            ):
                render_from_checkout(self.checkout, self.output)

    def test_structured_artifact_security_adaptations_reject_source_drift(self):
        source = self.checkout / "cw" / "skills" / "structured-artifact"
        (source / "resources").mkdir(parents=True)
        (source / "SKILL.md").write_text("---\nname: structured-artifact\n---\nBody.\n")
        (source / "resources/tree-and-toc.md").write_text(
            TREE_SOURCE.replace("renderNode(n)", "renderTreeNode(n)", 1)
        )
        (source / "resources/diagrams.md").write_text(
            DIAGRAM_SOURCE.replace("required for click callbacks", "changed upstream", 1)
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("structured-artifact",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"structured-artifact"},
        ):
            with self.assertRaisesRegex(
                ValueError,
                "licensed (?:tree rendering example|Mermaid configuration)",
            ):
                render_from_checkout(self.checkout, self.output)

    def test_invalid_vendored_names_do_not_mutate_output_or_escape_it(self):
        outside = self.root / "escape"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep\n")
        invalid_configurations = (
            ("../escape",),
            (str(outside),),
            ("demo/demo",),
            (".",),
            ("demo", "demo"),
            ("not-canonical",),
        )

        for index, names in enumerate(invalid_configurations):
            output = self.root / f"output-{index}"
            with self.subTest(names=names), patch(
                "scripts.vendor_generic_skills.vendored_skills", return_value=names
            ), patch(
                "scripts.vendor_generic_skills.canonical_skills", return_value=set(names) - {"not-canonical"}
            ):
                with self.assertRaises(ValueError):
                    render_from_checkout(self.checkout, output)
            self.assertFalse(output.exists())
            self.assertEqual((outside / "keep.txt").read_text(), "keep\n")

    def test_render_rejects_symlinked_checkout_boundary(self):
        checkout_link = self.root / "checkout-link"
        checkout_link.symlink_to(self.checkout, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "checkout.*symlink"):
            render_from_checkout(checkout_link, self.output)
        self.assertFalse(self.output.exists())

    def test_render_rejects_symlinked_checkout_ancestor(self):
        physical_parent = self.root / "physical-checkout-parent"
        physical_parent.mkdir()
        physical_checkout = physical_parent / "checkout"
        self.checkout.rename(physical_checkout)
        linked_parent = self.root / "linked-checkout-parent"
        linked_parent.symlink_to(physical_parent, target_is_directory=True)

        with self.assertRaisesRegex(ValueError, "checkout.*symlink"):
            render_from_checkout(linked_parent / "checkout", self.output)

        self.assertFalse(self.output.exists())

    def test_explicit_source_checkout_preserves_symlink_for_preflight(self):
        checkout_link = self.root / "checkout-option"
        checkout_link.symlink_to(self.checkout, target_is_directory=True)
        with source_checkout(checkout_link) as selected:
            with self.assertRaisesRegex(ValueError, "checkout.*symlink"):
                render_from_checkout(selected, self.output)
        self.assertFalse(self.output.exists())

    def test_render_rejects_symlinked_source_root_boundary(self):
        source_root = self.checkout / "cw" / "skills"
        external = self.root / "external-skills"
        source_root.rename(external)
        source_root.symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "source root.*symlink"):
            render_from_checkout(self.checkout, self.output)
        self.assertFalse(self.output.exists())

    def test_render_rejects_symlinked_skill_boundary(self):
        skill = self.checkout / "cw" / "skills" / "demo"
        external = self.root / "external-demo"
        skill.rename(external)
        skill.symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "demo.*symlink"):
            render_from_checkout(self.checkout, self.output)
        self.assertFalse(self.output.exists())

    def test_render_rejects_symlinked_and_special_source_entries(self):
        skill = self.checkout / "cw" / "skills" / "demo"
        external = self.root / "outside.md"
        external.write_text("outside\n")
        link = skill / "resources" / "leak.md"
        link.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "source entry.*symlink"):
            render_from_checkout(self.checkout, self.output)
        self.assertFalse(self.output.exists())

        link.unlink()
        fifo = skill / "resources" / "pipe"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, "source entry.*regular"):
            render_from_checkout(self.checkout, self.output)
        self.assertFalse(self.output.exists())

    def test_render_rejects_symlinked_output_boundaries(self):
        external = self.root / "external-output"
        external.mkdir()
        self.output.symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "output root.*symlink"):
            render_from_checkout(self.checkout, self.output)
        self.assertEqual(list(external.iterdir()), [])

    def test_render_rejects_symlinked_output_ancestor_without_write_through(self):
        physical_parent = self.root / "physical-output-parent"
        physical_output_parent = physical_parent / "nested"
        physical_output_parent.mkdir(parents=True)
        linked_parent = self.root / "linked-output-parent"
        linked_parent.symlink_to(physical_parent, target_is_directory=True)

        with self.assertRaisesRegex(ValueError, "output parent.*symlink"):
            render_from_checkout(self.checkout, linked_parent / "nested" / "output")

        self.assertEqual(list(physical_output_parent.iterdir()), [])

    def test_late_invalid_skill_does_not_partially_apply_earlier_skill(self):
        self.output.mkdir()
        existing = self.output / "demo"
        existing.mkdir()
        (existing / "SKILL.md").write_text("old demo\n")
        broken = self.checkout / "cw" / "skills" / "broken"
        broken.mkdir()
        (broken / "not-skill.md").write_text("late failure\n")

        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("demo", "broken"),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"demo", "broken"},
        ):
            with self.assertRaisesRegex(ValueError, "broken: missing SKILL.md"):
                render_from_checkout(self.checkout, self.output)

        self.assertEqual((existing / "SKILL.md").read_text(), "old demo\n")
        self.assertFalse((self.output / "broken").exists())

    def test_complete_stage_uses_each_configured_skill_source(self):
        second = self.checkout / "cw" / "skills" / "second"
        second.mkdir()
        (second / "SKILL.md").write_text(
            "---\nname: second\n---\n\n# Second\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("demo", "second"),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"demo", "second"},
        ):
            render_from_checkout(self.checkout, self.output)

        self.assertIn("# Demo", (self.output / "demo/SKILL.md").read_text())
        self.assertIn("# Second", (self.output / "second/SKILL.md").read_text())

    def test_batch_install_rolls_back_first_skill_when_second_install_fails(self):
        second = self.checkout / "cw" / "skills" / "second"
        second.mkdir()
        (second / "SKILL.md").write_text("---\nname: second\n---\n\n# Second\n")
        self.output.mkdir()
        for name in ("demo", "second"):
            destination = self.output / name
            destination.mkdir()
            (destination / "SKILL.md").write_text(f"old {name}\n")
        real_replace = os.replace
        failed = False

        def fail_second_install(source, destination):
            nonlocal failed
            source = Path(source)
            destination = Path(destination)
            if (
                not failed
                and source.name == "second"
                and destination == self.output / "second"
            ):
                failed = True
                raise OSError("injected second install failure")
            return real_replace(source, destination)

        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("demo", "second"),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"demo", "second"},
        ), patch(
            "scripts.vendor_generic_skills.os.replace",
            side_effect=fail_second_install,
        ):
            with self.assertRaisesRegex(OSError, "injected second install failure"):
                render_from_checkout(self.checkout, self.output)

        self.assertEqual("old demo\n", (self.output / "demo/SKILL.md").read_text())
        self.assertEqual("old second\n", (self.output / "second/SKILL.md").read_text())

    def test_batch_install_restores_present_and_absent_destinations(self):
        second = self.checkout / "cw" / "skills" / "second"
        second.mkdir()
        (second / "SKILL.md").write_text("---\nname: second\n---\n\n# Second\n")
        real_replace = os.replace

        for demo_present in (False, True):
            for second_present in (False, True):
                with self.subTest(
                    demo_present=demo_present,
                    second_present=second_present,
                ):
                    output = self.root / f"output-{demo_present}-{second_present}"
                    output.mkdir()
                    for name, present in (
                        ("demo", demo_present),
                        ("second", second_present),
                    ):
                        if present:
                            destination = output / name
                            destination.mkdir()
                            (destination / "SKILL.md").write_text(f"old {name}\n")
                    failed = False

                    def fail_second_install(source, destination):
                        nonlocal failed
                        source = Path(source)
                        destination = Path(destination)
                        if (
                            not failed
                            and source.name == "second"
                            and destination == output / "second"
                        ):
                            failed = True
                            raise OSError("injected second install failure")
                        return real_replace(source, destination)

                    with patch(
                        "scripts.vendor_generic_skills.vendored_skills",
                        return_value=("demo", "second"),
                    ), patch(
                        "scripts.vendor_generic_skills.canonical_skills",
                        return_value={"demo", "second"},
                    ), patch(
                        "scripts.vendor_generic_skills.os.replace",
                        side_effect=fail_second_install,
                    ):
                        with self.assertRaisesRegex(
                            OSError,
                            "injected second install failure",
                        ):
                            render_from_checkout(self.checkout, output)

                    for name, present in (
                        ("demo", demo_present),
                        ("second", second_present),
                    ):
                        self.assertEqual(present, (output / name).exists())
                        if present:
                            self.assertEqual(
                                f"old {name}\n",
                                (output / name / "SKILL.md").read_text(),
                            )

    def test_batch_install_rolls_back_on_interrupt(self):
        second = self.checkout / "cw" / "skills" / "second"
        second.mkdir()
        (second / "SKILL.md").write_text("---\nname: second\n---\n\n# Second\n")
        self.output.mkdir()
        for name in ("demo", "second"):
            destination = self.output / name
            destination.mkdir()
            (destination / "SKILL.md").write_text(f"old {name}\n")
        real_replace = os.replace
        interrupted = False

        def interrupt_second_install(source, destination):
            nonlocal interrupted
            source = Path(source)
            destination = Path(destination)
            if (
                not interrupted
                and source.name == "second"
                and destination == self.output / "second"
            ):
                interrupted = True
                raise KeyboardInterrupt("injected install interrupt")
            return real_replace(source, destination)

        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("demo", "second"),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"demo", "second"},
        ), patch(
            "scripts.vendor_generic_skills.os.replace",
            side_effect=interrupt_second_install,
        ):
            with self.assertRaisesRegex(KeyboardInterrupt, "injected install interrupt"):
                render_from_checkout(self.checkout, self.output)

        self.assertEqual("old demo\n", (self.output / "demo/SKILL.md").read_text())
        self.assertEqual("old second\n", (self.output / "second/SKILL.md").read_text())

    def test_batch_install_reconciles_interrupt_after_completed_rename(self):
        second = self.checkout / "cw" / "skills" / "second"
        second.mkdir()
        (second / "SKILL.md").write_text("---\nname: second\n---\n\n# Second\n")
        real_replace = os.replace

        for interrupted_operation in ("backup", "install"):
            with self.subTest(interrupted_operation=interrupted_operation):
                output = self.root / f"output-after-{interrupted_operation}"
                output.mkdir()
                for name in ("demo", "second"):
                    destination = output / name
                    destination.mkdir()
                    (destination / "SKILL.md").write_text(f"old {name}\n")
                interrupted = False

                def interrupt_after_rename(source, destination):
                    nonlocal interrupted
                    source = Path(source)
                    destination = Path(destination)
                    result = real_replace(source, destination)
                    is_second_backup = (
                        source == output / "second"
                        and destination.parent.name == "previous"
                    )
                    is_second_install = (
                        source.name == "second"
                        and destination == output / "second"
                        and source.parent.name != "previous"
                    )
                    if not interrupted and (
                        (interrupted_operation == "backup" and is_second_backup)
                        or (interrupted_operation == "install" and is_second_install)
                    ):
                        interrupted = True
                        raise KeyboardInterrupt(
                            f"injected post-{interrupted_operation} interrupt"
                        )
                    return result

                with patch(
                    "scripts.vendor_generic_skills.vendored_skills",
                    return_value=("demo", "second"),
                ), patch(
                    "scripts.vendor_generic_skills.canonical_skills",
                    return_value={"demo", "second"},
                ), patch(
                    "scripts.vendor_generic_skills.os.replace",
                    side_effect=interrupt_after_rename,
                ):
                    with self.assertRaisesRegex(
                        KeyboardInterrupt,
                        f"injected post-{interrupted_operation} interrupt",
                    ):
                        render_from_checkout(self.checkout, output)

                self.assertEqual(
                    "old demo\n",
                    (output / "demo/SKILL.md").read_text(),
                )
                self.assertTrue((output / "second/SKILL.md").is_file())
                self.assertEqual(
                    "old second\n",
                    (output / "second/SKILL.md").read_text(),
                )
                self.assertEqual(
                    [],
                    sorted(self.root.glob(".vendor-generic-skills-*")),
                )

    def test_batch_install_retains_recovery_backups_when_rollback_fails(self):
        second = self.checkout / "cw" / "skills" / "second"
        second.mkdir()
        (second / "SKILL.md").write_text("---\nname: second\n---\n\n# Second\n")
        self.output.mkdir()
        for name in ("demo", "second"):
            destination = self.output / name
            destination.mkdir()
            (destination / "SKILL.md").write_text(f"old {name}\n")
        real_replace = os.replace
        failed = False

        def fail_install_and_demo_restore(source, destination):
            nonlocal failed
            source = Path(source)
            destination = Path(destination)
            if (
                not failed
                and source.name == "second"
                and destination == self.output / "second"
            ):
                failed = True
                raise OSError("injected second install failure")
            if source.parent.name == "previous" and source.name == "demo":
                raise OSError("injected demo restore failure")
            return real_replace(source, destination)

        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("demo", "second"),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"demo", "second"},
        ), patch(
            "scripts.vendor_generic_skills.os.replace",
            side_effect=fail_install_and_demo_restore,
        ):
            with self.assertRaises(BaseException) as caught:
                render_from_checkout(self.checkout, self.output)

        self.assertIsInstance(caught.exception, ValueError)
        self.assertRegex(
            str(caught.exception),
            "demo restore failure.*recovery files retained",
        )

        recovery_roots = sorted(self.root.glob(".vendor-generic-skills-*"))
        self.assertEqual(1, len(recovery_roots))
        self.assertEqual(
            "old demo\n",
            (recovery_roots[0] / "previous/demo/SKILL.md").read_text(),
        )
        self.assertEqual("old second\n", (self.output / "second/SKILL.md").read_text())

    def test_batch_install_preserves_interrupt_when_rollback_fails(self):
        second = self.checkout / "cw" / "skills" / "second"
        second.mkdir()
        (second / "SKILL.md").write_text("---\nname: second\n---\n\n# Second\n")
        self.output.mkdir()
        for name in ("demo", "second"):
            destination = self.output / name
            destination.mkdir()
            (destination / "SKILL.md").write_text(f"old {name}\n")
        real_replace = os.replace
        interrupted = False

        def interrupt_install_and_fail_demo_restore(source, destination):
            nonlocal interrupted
            source = Path(source)
            destination = Path(destination)
            if (
                not interrupted
                and source.name == "second"
                and destination == self.output / "second"
            ):
                interrupted = True
                raise KeyboardInterrupt("injected install interrupt")
            if source.parent.name == "previous" and source.name == "demo":
                raise OSError("injected demo restore failure")
            return real_replace(source, destination)

        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("demo", "second"),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"demo", "second"},
        ), patch(
            "scripts.vendor_generic_skills.os.replace",
            side_effect=interrupt_install_and_fail_demo_restore,
        ):
            with self.assertRaises(KeyboardInterrupt) as caught:
                render_from_checkout(self.checkout, self.output)

        self.assertIn("demo restore failure", str(caught.exception))
        recovery_roots = sorted(self.root.glob(".vendor-generic-skills-*"))
        self.assertEqual(1, len(recovery_roots))
        self.assertEqual(
            "old demo\n",
            (recovery_roots[0] / "previous/demo/SKILL.md").read_text(),
        )

    def test_normalizer_preserves_commonmark_fenced_blocks(self):
        source = (
            "Use /story-memory.\n"
            "   ```bash\nLoad /qi-maintenance.\n   ```\n"
            "~~~text\nLoad /qi-maintenance.\n~~~\n"
            "```\n~~~\nLoad /qi-maintenance.\n```\n"
            "````\n```\nLoad /qi-maintenance.\n````\n"
            "```\n```not-a-close /qi-maintenance\n```\n"
            "```\nLoad /qi-maintenance.\n"
        )

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source.replace("Use /story-memory.", "Use $story-memory."))

    def test_normalizer_preserves_block_quote_fenced_code(self):
        source = "> ```bash\n> Load /qi-maintenance.\n> Load /story-memory.\n> ```\n"

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_preserves_list_continuation_fenced_code(self):
        source = "- ```bash\n  Load /qi-maintenance.\n  Load /story-memory.\n  ```\n"

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_preserves_list_state_fenced_code_byte_for_byte(self):
        cases = {
            "blank line in open fence": (
                "- ```markdown\n"
                "  literal\n"
                "\n"
                "  [placeholder](kb/{domain}/vocab.md)\n"
                "  $chapter /story-memory @ghost\n"
                "  ```\n"
            ),
            "continuation after empty marker": (
                "-\n"
                "    ```markdown\n"
                "    [placeholder](kb/{domain}/vocab.md)\n"
                "    $chapter /story-memory @ghost\n"
                "    ```\n"
            ),
        }
        for label, source in cases.items():
            with self.subTest(label=label):
                rendered = normalize_codex_references(
                    source,
                    {"story-memory"},
                    "demo",
                )
                self.assertEqual(rendered, source)

    def test_normalizer_preserves_quote_list_fenced_code(self):
        source = "> - ```bash\n>   Load /qi-maintenance.\n>   Load /story-memory.\n>   ```\n"

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_preserves_list_quote_fenced_code(self):
        source = "- > ```bash\n  > Load /qi-maintenance.\n  > Load /story-memory.\n  > ```\n"

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_preserves_nested_list_fenced_code(self):
        source = "- - ```bash\n    Load /qi-maintenance.\n    Load /story-memory.\n    ```\n"

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_preserves_tab_separated_list_fenced_code(self):
        source = "-\t```bash\n    Load /qi-maintenance.\n    Load /story-memory.\n    ```\n"

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_reopens_root_fence_after_list_fence_ends(self):
        source = (
            "- ```bash\n  Load /qi-maintenance.\n````\n"
            "Load /qi-maintenance.\nLoad /story-memory.\n````\n"
        )

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_reopens_root_fence_after_quote_fence_ends(self):
        source = (
            "> ```bash\n> Load /qi-maintenance.\n````\n"
            "Load /qi-maintenance.\nLoad /story-memory.\n````\n"
        )

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_reopens_root_fence_after_composed_container_ends(self):
        source = (
            "> - ```bash\n>   Load /qi-maintenance.\n````\n"
            "Load /qi-maintenance.\nLoad /story-memory.\n````\n"
        )

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)

    def test_normalizer_reopens_fence_at_surviving_outer_list_level(self):
        source = (
            "123. - ```bash\n       Load /qi-maintenance.\n     ````\n"
            "     Load /qi-maintenance.\n     Load /story-memory.\n     ````\n"
        )

        rendered = normalize_codex_references(source, {"story-memory"}, "demo")

        self.assertEqual(rendered, source)
