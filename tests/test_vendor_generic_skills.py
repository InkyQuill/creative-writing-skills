import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from scripts.vendor_generic_skills import (
    SOURCE,
    VendorDriftError,
    _replace_directory,
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


class VendorGenericSkillsTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
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

    def test_render_updates_a_preexisting_safe_output_root(self):
        self.output.mkdir()
        render_from_checkout(self.checkout, self.output)
        self.assertIn("# Demo", (self.output / "demo/SKILL.md").read_text())

    def test_check_reports_changed_vendored_file(self):
        render_from_checkout(self.checkout, self.output)
        (self.output / "demo" / "SKILL.md").write_text("changed\n")
        with self.assertRaisesRegex(VendorDriftError, "demo/SKILL.md"):
            check_checkout(self.checkout, self.output)

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
        self.assertIn("create missing mirrors", rendered)
        self.assertIn("leave exact mirrors unchanged", rendered)
        self.assertIn("report divergent files as conflicts", rendered)
        self.assertIn("instruction filename required by the active harness", rendered)
        self.assertIn("must never import itself", rendered)
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
            "## Starter AGENTS.md\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("knowledge-layers",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"knowledge-layers"},
        ):
            render_from_checkout(self.checkout, self.output)

        rendered = (
            self.output / "knowledge-layers/resources/bootstrap.md"
        ).read_text()
        self.assertIn(
            "{instruction-file}  # active harness instructions: intent and key rules",
            rendered,
        )
        self.assertIn("## Starter instruction file", rendered)
        self.assertNotIn("AGENTS.md", rendered)

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

    def test_render_adapts_grill_instruction_file_for_codex(self):
        source = self.checkout / "cw" / "skills" / "grill-with-docs"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: grill-with-docs\n---\n"
            "2. Project conventions in `CLAUDE.md` — established names and labels.\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("grill-with-docs",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"grill-with-docs"},
        ):
            render_from_checkout(self.checkout, self.output)

        rendered = (self.output / "grill-with-docs/SKILL.md").read_text()
        self.assertIn("Project conventions in `AGENTS.md`", rendered)
        self.assertNotIn("CLAUDE.md", rendered)

    def test_grill_adaptation_rejects_unrecognized_licensed_source(self):
        source = self.checkout / "cw" / "skills" / "grill-with-docs"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: grill-with-docs\n---\n"
            "2. Changed project conventions wording.\n"
        )
        with patch(
            "scripts.vendor_generic_skills.vendored_skills",
            return_value=("grill-with-docs",),
        ), patch(
            "scripts.vendor_generic_skills.canonical_skills",
            return_value={"grill-with-docs"},
        ):
            with self.assertRaisesRegex(ValueError, "licensed instruction-file reference"):
                render_from_checkout(self.checkout, self.output)

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
        self.assertNotIn("innerHTML", tree)
        self.assertNotIn("innerHTML", diagrams)
        self.assertIn("textContent", tree)
        self.assertIn("replaceChildren", tree)
        self.assertIn("securityLevel: 'strict'", diagrams)
        self.assertNotIn("securityLevel: 'loose'", diagrams)
        self.assertNotRegex(diagrams, r"(?m)^\s*click\s+\w+\s+\w+")
        self.assertIn("ALLOWED_DETAIL_KEYS", diagrams)
        self.assertNotIn("new Set(Object.keys(DETAIL))", diagrams)

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

    def test_replace_preserves_preexisting_backup_collision(self):
        destination = self.root / "demo"
        destination.mkdir()
        (destination / "value.txt").write_text("old\n")
        staged = self.root / "staged"
        staged.mkdir()
        (staged / "value.txt").write_text("new\n")
        collision = self.root / ".demo.vendor-backup"
        collision.mkdir()
        (collision / "keep.txt").write_text("keep\n")

        _replace_directory(staged, destination)

        self.assertEqual((destination / "value.txt").read_text(), "new\n")
        self.assertEqual((collision / "keep.txt").read_text(), "keep\n")

    def test_replace_rolls_back_when_install_rename_fails(self):
        destination = self.root / "demo"
        destination.mkdir()
        (destination / "value.txt").write_text("old\n")
        staged = self.root / "staged"
        staged.mkdir()
        (staged / "value.txt").write_text("new\n")
        real_replace = os.replace

        def fail_install(source, target):
            if Path(source) == staged and Path(target) == destination:
                raise OSError("injected install failure")
            return real_replace(source, target)

        with patch("scripts.vendor_generic_skills.os.replace", side_effect=fail_install):
            with self.assertRaisesRegex(OSError, "injected install failure"):
                _replace_directory(staged, destination)

        self.assertEqual((destination / "value.txt").read_text(), "old\n")
        self.assertTrue(staged.is_dir())
