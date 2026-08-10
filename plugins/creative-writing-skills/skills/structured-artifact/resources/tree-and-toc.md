# Tree and TOC

Expandable hierarchy or document outline. No library needed — native HTML handles
both patterns. These are single-page navigation aids; when the hierarchy is big
enough that readers need whole pages per branch, use `multi-page-site.md`
instead of a deeper tree.

## Tree (File Explorer Style)

Use `<details>` and `<summary>` for expand/collapse. Render recursively from data.

```html
<input id="treeSearch" placeholder="Filter...">
<div id="tree"></div>
<script>
const data = {
  name: "root", children: [
    { name: "docs", children: [{ name: "releasing.md" }, { name: "arch.md" }] },
    { name: "src", children: [{ name: "cli.py" }, { name: "config.py" }] },
  ],
};

function renderNode(n) {
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
document.getElementById("tree").replaceChildren(treeList);

document.getElementById("treeSearch").oninput = e => {
  const q = e.target.value.toLowerCase();
  document.querySelectorAll("#tree li").forEach(li => {
    li.style.display = li.textContent.toLowerCase().includes(q) ? "" : "none";
  });
};
</script>
```

Click a leaf to show detail — add a click handler on `.leaf` elements.

## TOC (Document Outline)

Generate a nav from headings. Use `IntersectionObserver` to highlight the active
section.

```html
<style>html { scroll-behavior: smooth } #toc a.active { font-weight: bold }</style>
<nav id="toc"></nav>
<main id="doc"><!-- headings with ids --></main>
<script>
const headings = [...document.querySelectorAll("#doc h2, #doc h3")];
const toc = document.getElementById("toc");
headings.forEach(heading => {
  const link = document.createElement("a");
  link.href = `#${encodeURIComponent(heading.id)}`;
  link.dataset.id = heading.id;
  link.textContent = heading.textContent;
  toc.append(link, document.createElement("br"));
});

const links = [...toc.querySelectorAll("a")];
const obs = new IntersectionObserver(entries => {
  entries.filter(e => e.isIntersecting).forEach(e => {
    links.forEach(a => a.classList.toggle("active", a.dataset.id === e.target.id));
  });
}, { rootMargin: "-20% 0px -70% 0px" });
headings.forEach(h => obs.observe(h));
</script>
```
