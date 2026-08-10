# Diagrams

Use when information has relationships, dependencies, or flow — after the prose
it illustrates, never instead of it. Validate with an available Mermaid parser or renderer, and report syntax errors before delivery.

## Mermaid (default)

Use Mermaid for flowcharts, dependency graphs, and system maps. For force-directed
layouts or network graphs, see Cytoscape below.

### CDN

```html
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
```

Use the `dist/mermaid.min.js` IIFE — it exposes the `mermaid` global and
vendors cleanly for offline use (the ESM entry pulls further imports at
runtime).

### Config

Initialize with manual start for stable node IDs and click callbacks.

```js
mermaid.initialize({
  startOnLoad: false,
  theme: document.documentElement.classList.contains('dark') ? 'dark' : 'default',
  securityLevel: 'strict',
  flowchart: { curve: 'basis', nodeSpacing: 50, rankSpacing: 60 },
});
await mermaid.run({ querySelector: '.mermaid' });
```

Keep `securityLevel: 'strict'`. Bind interactions after rendering and only for node IDs present in the detail allow-list.

When the viewer toggles theme, re-initialize Mermaid with the new theme and re-render
the diagram.

### Post-render Click Binding

Do not use Mermaid `click` directives or global callbacks. Declare the exact
detail keys the page supports, keep them aligned with `DETAIL`, and bind only
those nodes after Mermaid renders:

```js
const ALLOWED_DETAIL_KEYS = new Set(['api']);

document.querySelectorAll('#diagram .node').forEach(node => {
  const key = node.id.replace(/^flowchart-/, '').replace(/-\d+$/, '');
  if (!ALLOWED_DETAIL_KEYS.has(key)) return;
  node.style.cursor = 'pointer';
  node.addEventListener('click', () => showDetail(key));
});
```

### Detail Data

Hold per-node detail in a JS object; the callback fills the detail sidebar from
`layout-and-theme.md`.

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
}
```

`showDetail` stays local; strict mode never invokes it from diagram text.

### Pan and Zoom

Wrap the diagram in a transform layer for larger graphs.

```js
let scale = 1, tx = 0, ty = 0, dragging = false, sx, sy;
const stage = document.getElementById('stage');
const apply = () => stage.style.transform =
  `translate(${tx}px,${ty}px) scale(${scale})`;

stage.parentElement.addEventListener('wheel', e => {
  e.preventDefault();
  scale = Math.min(3, Math.max(0.3, scale - e.deltaY * 0.001));
  apply();
}, { passive: false });

stage.parentElement.addEventListener('pointerdown', e => {
  dragging = true; sx = e.clientX - tx; sy = e.clientY - ty;
});
window.addEventListener('pointermove', e => {
  if (!dragging) return; tx = e.clientX - sx; ty = e.clientY - sy; apply();
});
window.addEventListener('pointerup', () => dragging = false);
```

Add pinch-zoom for mobile:

```js
const pts = new Map();
let pinchDist = 0;
stage.parentElement.addEventListener('pointerdown', e => pts.set(e.pointerId, e));
stage.parentElement.addEventListener('pointermove', e => {
  if (!pts.has(e.pointerId)) return;
  pts.set(e.pointerId, e);
  if (pts.size === 2) {
    const [a, b] = [...pts.values()];
    const d = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
    if (pinchDist) {
      scale = Math.min(3, Math.max(0.3, scale * (d / pinchDist)));
      apply();
    }
    pinchDist = d;
  }
});
window.addEventListener('pointerup', e => { pts.delete(e.pointerId); pinchDist = 0; });
```

### Diagram Styling

Default to renderer theme colors. Use stroke-only `classDef` for emphasis so nodes
adapt to any background:

```text
classDef highlight stroke:#f59e0b,stroke-width:2px
```

Reserve one accent for flagged nodes, applied as stroke plus a label.

## Cytoscape (alternative)

Use Cytoscape.js when you need force-directed layout, network visualization, or
richer interaction than Mermaid supports. ~136 KB gzipped.

```html
<script src="https://cdn.jsdelivr.net/npm/cytoscape@3/dist/cytoscape.min.js"></script>
```

```js
const cy = cytoscape({
  container: document.getElementById('graph'),
  elements: [
    { data: { id: 'a', label: 'API' } },
    { data: { id: 'b', label: 'DB' } },
    { data: { source: 'a', target: 'b' } },
  ],
  style: [
    { selector: 'node', style: { label: 'data(label)', 'background-color': '#467' } },
    { selector: 'edge', style: { width: 2, 'target-arrow-shape': 'triangle' } },
  ],
  layout: { name: 'breadthfirst' },
});
cy.on('tap', 'node', e => showDetail(e.target.data('id')));
```

Cytoscape has built-in zoom, pan, and box selection. Layouts: `breadthfirst`,
`circle`, `cose` (force-directed), `grid`.
