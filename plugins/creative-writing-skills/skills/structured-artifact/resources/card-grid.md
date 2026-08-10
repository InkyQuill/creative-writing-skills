# Card Grid

Items displayed as cards with summary info, filterable and sortable, click to
expand detail. No library needed — CSS Grid handles layout.

## Minimal Example

```html
<input id="cardSearch" placeholder="Search...">
<select id="cardSort">
  <option value="name">Name</option>
  <option value="score">Score</option>
</select>
<div id="cards" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px"></div>
<script>
const items = [
  { name: "Parser", type: "code", score: 8, detail: "Builds AST from source" },
  { name: "Release", type: "docs", score: 5, detail: "Ship process docs" },
];

function createCard(item) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "card";

  const name = document.createElement("b");
  name.textContent = item.name;
  const type = document.createElement("span");
  type.style.color = "var(--muted)";
  type.textContent = item.type;

  button.append(name, document.createElement("br"), type);
  button.addEventListener("click", () => showDetail(item.name));
  return button;
}

function renderCards() {
  const q = document.getElementById("cardSearch").value.toLowerCase();
  const s = document.getElementById("cardSort").value;
  const cards = items
    .filter(item => JSON.stringify(item).toLowerCase().includes(q))
    .sort((a, b) => (a[s] === b[s] ? 0 : a[s] > b[s] ? 1 : -1))
    .map(createCard);
  document.getElementById("cards").replaceChildren(...cards);
}

document.getElementById("cardSearch").addEventListener("input", renderCards);
document.getElementById("cardSort").addEventListener("change", renderCards);
renderCards();
</script>
```

Equal-height grid is usually sufficient. For variable-height packing, layer
native CSS masonry as a progressive enhancement — browser support is still
uneven (check current support if packing matters), so the grid fallback
carries most readers:

```css
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
         gap: 12px; align-items: start; }
@supports (grid-template-rows: masonry) { .cards { grid-template-rows: masonry; } }
@supports (display: grid-lanes)         { .cards { display: grid-lanes; } }
```
