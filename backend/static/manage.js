const indexSelect = document.getElementById("indexSelect");
const indexCountBadge = document.getElementById("indexCountBadge");
const errorBanner = document.getElementById("errorBanner");
const errorBannerText = document.getElementById("errorBannerText");
const retryButton = document.getElementById("retryButton");
const docsArea = document.getElementById("docsArea");

let loadedIndexes = [];

function showError(message, onRetry) {
  errorBannerText.textContent = message;
  errorBanner.hidden = false;
  retryButton.onclick = onRetry;
}

function hideError() {
  errorBanner.hidden = true;
  retryButton.onclick = null;
}

function clearChildren(el) {
  while (el.firstChild) {
    el.removeChild(el.firstChild);
  }
}

function renderLoading(container, message) {
  clearChildren(container);
  const el = document.createElement("div");
  el.className = "loading-state";
  el.textContent = message;
  container.appendChild(el);
}

function renderEmpty(container, message) {
  clearChildren(container);
  const el = document.createElement("div");
  el.className = "empty-state";
  el.textContent = message;
  container.appendChild(el);
}

async function loadIndexes() {
  indexSelect.disabled = true;
  clearChildren(indexSelect);
  indexCountBadge.textContent = "";
  hideError();
  renderLoading(docsArea, "Loading indexes…");

  let indexes;
  try {
    const res = await fetch("/api/indexes");
    if (!res.ok) {
      throw new Error(`Request failed (${res.status})`);
    }
    indexes = await res.json();
  } catch (err) {
    clearChildren(docsArea);
    showError("Failed to load indexes.", loadIndexes);
    return;
  }

  if (!Array.isArray(indexes) || indexes.length === 0) {
    const option = document.createElement("option");
    option.textContent = "No indexes available";
    indexSelect.appendChild(option);
    indexSelect.disabled = true;
    renderEmpty(docsArea, "No indexes available");
    return;
  }

  loadedIndexes = indexes;
  indexSelect.disabled = false;
  for (const index of indexes) {
    const option = document.createElement("option");
    option.value = index.name;
    option.textContent = index.name;
    indexSelect.appendChild(option);
  }

  indexSelect.selectedIndex = 0;
  updateCountBadge();
  await loadDocsForSelectedIndex();
}

function updateCountBadge() {
  const selected = loadedIndexes.find((index) => index.name === indexSelect.value);
  indexCountBadge.textContent = selected ? `${selected.docCount} chunks` : "";
}

function resolveGroupKey(chunks) {
  if (chunks.some((chunk) => chunk.metadata && chunk.metadata.sourceDoc)) {
    return "sourceDoc";
  }
  if (chunks.some((chunk) => chunk.metadata && chunk.metadata.type)) {
    return "type";
  }
  return null;
}

function groupChunks(chunks) {
  const groupKey = resolveGroupKey(chunks);
  const groups = new Map();

  for (const chunk of chunks) {
    const value = groupKey && chunk.metadata ? chunk.metadata[groupKey] : null;
    const groupName = value || "Ungrouped";
    if (!groups.has(groupName)) {
      groups.set(groupName, []);
    }
    groups.get(groupName).push(chunk);
  }

  return groups;
}

function createMetadataChips(metadata) {
  const wrap = document.createElement("div");
  wrap.className = "metadata-chips";
  if (!metadata) {
    return wrap;
  }
  for (const [key, value] of Object.entries(metadata)) {
    const chip = document.createElement("span");
    chip.className = "badge";
    chip.textContent = `${key}: ${value}`;
    wrap.appendChild(chip);
  }
  return wrap;
}

function createChunkRow(chunk) {
  const row = document.createElement("div");
  row.className = "chunk-row";

  const id = document.createElement("code");
  id.className = "chunk-id";
  id.textContent = chunk.id;
  row.appendChild(id);

  const text = document.createElement("p");
  text.className = "chunk-text clamped";
  text.textContent = chunk.text;
  row.appendChild(text);

  const showMoreBtn = document.createElement("button");
  showMoreBtn.type = "button";
  showMoreBtn.className = "show-more-btn";
  showMoreBtn.textContent = "Show more";
  showMoreBtn.addEventListener("click", () => {
    const isClamped = text.classList.contains("clamped");
    text.classList.toggle("clamped", !isClamped);
    showMoreBtn.textContent = isClamped ? "Show less" : "Show more";
  });
  row.appendChild(showMoreBtn);

  row.appendChild(createMetadataChips(chunk.metadata));

  return row;
}

function createDocGroupCard(name, chunks, isExpanded) {
  const card = document.createElement("section");
  card.className = "panel doc-group" + (isExpanded ? " expanded" : "");

  const header = document.createElement("button");
  header.type = "button";
  header.className = "doc-group-header";
  header.setAttribute("aria-expanded", String(isExpanded));

  const chevron = document.createElement("span");
  chevron.className = "doc-group-chevron";
  chevron.textContent = "▸";
  header.appendChild(chevron);

  const groupName = document.createElement("span");
  groupName.className = "doc-group-name";
  groupName.textContent = name;
  header.appendChild(groupName);

  const countBadge = document.createElement("span");
  countBadge.className = "badge";
  countBadge.textContent = `${chunks.length} chunk${chunks.length === 1 ? "" : "s"}`;
  header.appendChild(countBadge);

  header.addEventListener("click", () => {
    const nowExpanded = card.classList.toggle("expanded");
    header.setAttribute("aria-expanded", String(nowExpanded));
  });

  card.appendChild(header);

  const body = document.createElement("div");
  body.className = "doc-group-body";

  const list = document.createElement("div");
  list.className = "doc-group-list";
  for (const chunk of chunks) {
    list.appendChild(createChunkRow(chunk));
  }
  body.appendChild(list);
  card.appendChild(body);

  return card;
}

function renderDocGroups(chunks) {
  clearChildren(docsArea);

  if (chunks.length === 0) {
    renderEmpty(docsArea, "No documents in this index yet");
    return;
  }

  const groups = groupChunks(chunks);
  let isFirst = true;
  for (const [name, groupChunksList] of groups) {
    docsArea.appendChild(createDocGroupCard(name, groupChunksList, isFirst));
    isFirst = false;
  }
}

async function loadDocsForSelectedIndex() {
  const name = indexSelect.value;
  if (!name) {
    return;
  }

  hideError();
  renderLoading(docsArea, "Loading documents…");

  let chunks;
  try {
    const res = await fetch(`/api/indexes/${encodeURIComponent(name)}/docs`);
    if (!res.ok) {
      throw new Error(`Request failed (${res.status})`);
    }
    chunks = await res.json();
  } catch (err) {
    clearChildren(docsArea);
    showError("Failed to load documents for this index.", loadDocsForSelectedIndex);
    return;
  }

  renderDocGroups(Array.isArray(chunks) ? chunks : []);
}

indexSelect.addEventListener("change", () => {
  updateCountBadge();
  loadDocsForSelectedIndex();
});

loadIndexes();
