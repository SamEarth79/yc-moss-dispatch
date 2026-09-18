const stage = document.getElementById("dataMapStage");
const linesSvg = document.getElementById("dataMapLines");

const NODES = [
  { id: "hub", title: "Dispatch Copilot", sub: "live call session", tag: "", color: "acid", pos: [0, 0, 0] },
  { id: "protocol", title: "Protocol chunks", sub: "type: protocol", tag: "protocol-index · static · SME-gated", color: "teal", pos: [-270, -60, 90] },
  { id: "incident", title: "Past incidents", sub: "type: incident", tag: "live-data-index · dynamic", color: "violet", pos: [230, -95, -110] },
  { id: "facility", title: "Facilities", sub: "type: facility", tag: "live-data-index · dynamic", color: "green", pos: [190, 105, 130] },
];
const LINKS = [["hub", "protocol"], ["hub", "incident"], ["hub", "facility"]];
const PERSPECTIVE = 900;
const AUTO_SPIN = 0.0025;

let yaw = -0.35;
let pitch = 0.18;
let dragging = false;
let lastPointer = null;
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const cards = new Map();
for (const node of NODES) {
  const card = document.createElement("div");
  card.className = `map-node map-node--${node.color}`;
  card.innerHTML = `
    <div class="map-node-title">${node.title}</div>
    <div class="map-node-sub">${node.sub}</div>
    ${node.tag ? `<div class="map-node-tag">${node.tag}</div>` : ""}
  `;
  stage.appendChild(card);
  cards.set(node.id, card);
}

const lineEls = LINKS.map(([from, to]) => {
  const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
  line.setAttribute("class", `map-line map-line--${NODES.find((n) => n.id === to).color}`);
  linesSvg.appendChild(line);
  return { line, from, to };
});

function project([x, y, z]) {
  const cosY = Math.cos(yaw);
  const sinY = Math.sin(yaw);
  const cosP = Math.cos(pitch);
  const sinP = Math.sin(pitch);
  const x1 = x * cosY + z * sinY;
  const z1 = -x * sinY + z * cosY;
  const y2 = y * cosP - z1 * sinP;
  const z2 = y * sinP + z1 * cosP;
  const scale = PERSPECTIVE / (PERSPECTIVE + z2);
  return { x: x1 * scale, y: y2 * scale, scale, depth: z2 };
}

function render() {
  const { width, height } = stage.getBoundingClientRect();
  const cx = width / 2;
  const cy = height / 2;
  const fit = Math.min(1, width / 760);
  const projected = new Map();

  for (const node of NODES) {
    const p = project(node.pos);
    projected.set(node.id, p);
    const card = cards.get(node.id);
    const s = p.scale * fit;
    card.style.transform = `translate(${cx + p.x * fit}px, ${cy + p.y * fit}px) translate(-50%, -50%) scale(${s})`;
    card.style.opacity = String(Math.max(0.45, Math.min(1, 0.55 + p.scale * 0.45 - 0.2)));
    card.style.zIndex = String(Math.round(1000 - p.depth));
  }

  for (const { line, from, to } of lineEls) {
    const a = projected.get(from);
    const b = projected.get(to);
    line.setAttribute("x1", cx + a.x * fit);
    line.setAttribute("y1", cy + a.y * fit);
    line.setAttribute("x2", cx + b.x * fit);
    line.setAttribute("y2", cy + b.y * fit);
  }
}

function tick() {
  if (!dragging && !reducedMotion) yaw += AUTO_SPIN;
  render();
  requestAnimationFrame(tick);
}

stage.addEventListener("pointerdown", (e) => {
  dragging = true;
  lastPointer = { x: e.clientX, y: e.clientY };
  stage.setPointerCapture(e.pointerId);
});
stage.addEventListener("pointermove", (e) => {
  if (!dragging) return;
  yaw += (e.clientX - lastPointer.x) * 0.008;
  pitch = Math.max(-0.7, Math.min(0.7, pitch + (e.clientY - lastPointer.y) * 0.006));
  lastPointer = { x: e.clientX, y: e.clientY };
});
stage.addEventListener("pointerup", () => {
  dragging = false;
});
stage.addEventListener("pointercancel", () => {
  dragging = false;
});

tick();
