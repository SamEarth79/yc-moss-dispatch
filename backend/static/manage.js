const indexSelect = document.getElementById("indexSelect");
const indexCountBadge = document.getElementById("indexCountBadge");
const errorBanner = document.getElementById("errorBanner");
const errorBannerText = document.getElementById("errorBannerText");
const retryButton = document.getElementById("retryButton");
const docsArea = document.getElementById("docsArea");
const newDocumentButton = document.getElementById("newDocumentButton");
const newDocFormSlot = document.getElementById("newDocFormSlot");
const toastContainer = document.getElementById("toastContainer");
const liveRegion = document.getElementById("liveRegion");

let loadedIndexes = [];
let currentChunks = [];
let expandedGroups = new Set();
let formInstanceCounter = 0;

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

function announce(message) {
  liveRegion.textContent = "";
  requestAnimationFrame(() => {
    liveRegion.textContent = message;
  });
}

function showToast(message, isError) {
  const toast = document.createElement("div");
  toast.className = "toast" + (isError ? " toast-error" : "");
  toast.textContent = message;
  toastContainer.appendChild(toast);
  setTimeout(() => toast.remove(), 5000);
  announce(message);
}

async function loadIndexes() {
  indexSelect.disabled = true;
  newDocumentButton.disabled = true;
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
  newDocumentButton.disabled = false;
  updateCountBadge();
  await loadDocsForSelectedIndex();
}

function updateCountBadge() {
  const selected = loadedIndexes.find((index) => index.name === indexSelect.value);
  indexCountBadge.textContent = selected ? `${selected.docCount} chunks` : "";
}

function adjustDocCount(delta) {
  const selected = loadedIndexes.find((index) => index.name === indexSelect.value);
  if (selected) {
    selected.docCount += delta;
    updateCountBadge();
  }
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

function createMetadataEditor(formId, initialMetadata) {
  const editor = document.createElement("div");
  editor.className = "metadata-editor";

  const label = document.createElement("div");
  label.className = "metadata-editor-label";
  label.textContent = "Metadata";
  editor.appendChild(label);

  const rowsContainer = document.createElement("div");
  editor.appendChild(rowsContainer);

  let rowCounter = 0;

  function addRow(key, value) {
    rowCounter += 1;
    const n = rowCounter;
    const row = document.createElement("div");
    row.className = "metadata-row";

    const keyInput = document.createElement("input");
    keyInput.type = "text";
    keyInput.className = "transcript-input metadata-key-input";
    keyInput.id = `metadataKey-${formId}-${n}`;
    keyInput.setAttribute("aria-label", `Metadata key ${n}`);
    keyInput.placeholder = "key";
    keyInput.value = key || "";
    row.appendChild(keyInput);

    const valueInput = document.createElement("input");
    valueInput.type = "text";
    valueInput.className = "transcript-input metadata-value-input";
    valueInput.id = `metadataValue-${formId}-${n}`;
    valueInput.setAttribute("aria-label", `Metadata value ${n}`);
    valueInput.placeholder = "value";
    valueInput.value = value || "";
    row.appendChild(valueInput);

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "metadata-remove-btn";
    removeBtn.textContent = "×";
    removeBtn.setAttribute("aria-label", "Remove metadata field");
    removeBtn.addEventListener("click", () => row.remove());
    row.appendChild(removeBtn);

    rowsContainer.appendChild(row);
    return row;
  }

  function fill(metadata) {
    clearChildren(rowsContainer);
    rowCounter = 0;
    const entries = metadata ? Object.entries(metadata) : [];
    if (entries.length === 0) {
      addRow("", "");
    } else {
      for (const [key, value] of entries) {
        addRow(key, value);
      }
    }
  }

  fill(initialMetadata);

  const addFieldBtn = document.createElement("button");
  addFieldBtn.type = "button";
  addFieldBtn.className = "action-button none";
  addFieldBtn.textContent = "+ Add field";
  addFieldBtn.addEventListener("click", () => addRow("", ""));
  editor.appendChild(addFieldBtn);

  function getMetadata() {
    const metadata = {};
    for (const row of rowsContainer.children) {
      const keyInput = row.querySelector(".metadata-key-input");
      const valueInput = row.querySelector(".metadata-value-input");
      const key = keyInput.value.trim();
      if (key) {
        metadata[key] = valueInput.value;
      }
    }
    return metadata;
  }

  return { element: editor, getMetadata, reset: fill };
}

async function extractErrorDetail(res) {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch (parseErr) {
    // no JSON body on the error response; fall through to the generic message
  }
  return `Request failed (${res.status})`;
}

function closeOpenForm() {
  const existing = document.querySelector(".chunk-form");
  if (!existing) {
    return;
  }
  const opener = existing._opener;
  existing.remove();
  if (opener) {
    opener.focus();
  }
}

function buildChunkForm(config) {
  formInstanceCounter += 1;
  const formId = formInstanceCounter;

  const form = document.createElement("div");
  form.className = "chunk-form";
  form._opener = config.opener;

  const idFieldWrap = document.createElement("div");
  idFieldWrap.className = "chunk-form-field";
  const idLabel = document.createElement("label");
  idLabel.setAttribute("for", `chunkId-${formId}`);
  idLabel.textContent = "Chunk ID";
  const idInput = document.createElement("input");
  idInput.type = "text";
  idInput.id = `chunkId-${formId}`;
  idInput.className = "transcript-input";
  idInput.required = true;
  if (config.mode === "edit") {
    idInput.value = config.chunk.id;
    idInput.disabled = true;
  }
  idFieldWrap.appendChild(idLabel);
  idFieldWrap.appendChild(idInput);
  form.appendChild(idFieldWrap);

  const effectiveGroupKey = config.groupKey || "sourceDoc";
  let groupValueInput = null;
  if (config.isNewDocument) {
    const groupFieldWrap = document.createElement("div");
    groupFieldWrap.className = "chunk-form-field";
    const groupLabel = document.createElement("label");
    groupLabel.setAttribute("for", `chunkGroupValue-${formId}`);
    groupLabel.textContent = `Group (${effectiveGroupKey})`;
    groupValueInput = document.createElement("input");
    groupValueInput.type = "text";
    groupValueInput.id = `chunkGroupValue-${formId}`;
    groupValueInput.className = "transcript-input";
    groupFieldWrap.appendChild(groupLabel);
    groupFieldWrap.appendChild(groupValueInput);
    form.appendChild(groupFieldWrap);
  }

  const textFieldWrap = document.createElement("div");
  textFieldWrap.className = "chunk-form-field";
  const textLabel = document.createElement("label");
  textLabel.setAttribute("for", `chunkText-${formId}`);
  textLabel.textContent = "Text";
  const textArea = document.createElement("textarea");
  textArea.id = `chunkText-${formId}`;
  textArea.className = "transcript-input";
  textArea.rows = 4;
  if (config.mode === "edit") {
    textArea.value = config.chunk.text || "";
  }
  textFieldWrap.appendChild(textLabel);
  textFieldWrap.appendChild(textArea);
  form.appendChild(textFieldWrap);

  const initialMetadata =
    config.mode === "edit"
      ? config.chunk.metadata
      : config.presetGroupValue && config.groupKey
        ? { [config.groupKey]: config.presetGroupValue }
        : null;

  const metadataEditor = createMetadataEditor(formId, initialMetadata);
  form.appendChild(metadataEditor.element);

  const errorEl = document.createElement("div");
  errorEl.className = "chunk-form-error";
  errorEl.hidden = true;
  form.appendChild(errorEl);

  const actions = document.createElement("div");
  actions.className = "chunk-form-actions";

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "action-button";
  saveBtn.textContent = "Save";
  actions.appendChild(saveBtn);

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "action-button none";
  cancelBtn.textContent = "Cancel";
  cancelBtn.addEventListener("click", () => {
    form.remove();
    if (config.opener) {
      config.opener.focus();
    }
  });
  actions.appendChild(cancelBtn);

  form.appendChild(actions);

  saveBtn.addEventListener("click", async () => {
    errorEl.hidden = true;

    const id = idInput.value.trim();
    if (!id) {
      errorEl.textContent = "Chunk ID is required.";
      errorEl.hidden = false;
      idInput.focus();
      return;
    }

    const text = textArea.value;
    const metadata = metadataEditor.getMetadata();
    const groupValue = groupValueInput ? groupValueInput.value.trim() : "";
    if (config.isNewDocument && groupValue) {
      metadata[effectiveGroupKey] = groupValue;
    }

    const indexName = indexSelect.value;
    const isEdit = config.mode === "edit";
    const existedBefore = currentChunks.some((chunk) => chunk.id === id);

    saveBtn.disabled = true;
    try {
      let res;
      if (isEdit) {
        res = await fetch(
          `/api/indexes/${encodeURIComponent(indexName)}/docs/${encodeURIComponent(id)}`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, metadata }),
          }
        );
      } else {
        res = await fetch(`/api/indexes/${encodeURIComponent(indexName)}/docs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id, text, metadata }),
        });
      }

      if (!res.ok) {
        throw new Error(await extractErrorDetail(res));
      }
    } catch (err) {
      saveBtn.disabled = false;
      errorEl.textContent = err.message || "Failed to save chunk. Please try again.";
      errorEl.hidden = false;
      return;
    }

    saveBtn.disabled = false;
    const wasUpdate = isEdit || existedBefore;
    upsertChunkAndRerender({ id, text, metadata });
    if (!wasUpdate) {
      adjustDocCount(1);
    }
    showToast(wasUpdate ? `Updated existing chunk "${id}"` : `Added new chunk "${id}"`);

    if (isEdit) {
      form.remove();
      focusEditButtonForChunk(id);
    } else {
      idInput.value = "";
      textArea.value = "";
      const resetMetadata =
        config.isNewDocument && groupValue
          ? { [effectiveGroupKey]: groupValue }
          : config.presetGroupValue && config.groupKey
            ? { [config.groupKey]: config.presetGroupValue }
            : null;
      metadataEditor.reset(resetMetadata);

      if (!config.isNewDocument) {
        const targetGroupName = config.presetGroupValue || "Ungrouped";
        reattachFormToGroup(form, targetGroupName);
      }

      idInput.focus();
    }
  });

  return { element: form, idInput, textArea };
}

function openForm(container, config) {
  closeOpenForm();
  const { element, idInput, textArea } = buildChunkForm(config);
  if (config.insertAfter && config.insertAfter.parentElement === container) {
    container.insertBefore(element, config.insertAfter.nextSibling);
  } else {
    container.appendChild(element);
  }
  if (!idInput.disabled) {
    idInput.focus();
  } else {
    textArea.focus();
  }
}

function upsertChunkAndRerender(chunk) {
  const index = currentChunks.findIndex((existing) => existing.id === chunk.id);
  if (index === -1) {
    currentChunks.push(chunk);
  } else {
    currentChunks[index] = chunk;
  }
  renderDocGroups(currentChunks);
}

function focusEditButtonForChunk(chunkId) {
  for (const idEl of docsArea.querySelectorAll(".chunk-id")) {
    if (idEl.textContent === chunkId) {
      const row = idEl.closest(".chunk-row");
      const editBtn = row && row.querySelector(".chunk-row-actions button:first-child");
      if (editBtn) {
        editBtn.focus();
      }
      return;
    }
  }
}

function findGroupCardByName(groupName) {
  for (const card of docsArea.querySelectorAll(".doc-group")) {
    const nameEl = card.querySelector(".doc-group-name");
    if (nameEl && nameEl.textContent === groupName) {
      return card;
    }
  }
  return null;
}

function reattachFormToGroup(form, groupName) {
  const card = findGroupCardByName(groupName);
  if (!card) {
    return;
  }
  const header = card.querySelector(".doc-group-header");
  const body = card.querySelector(".doc-group-body");
  if (!card.classList.contains("expanded")) {
    card.classList.add("expanded");
    header.setAttribute("aria-expanded", "true");
  }
  expandedGroups.add(groupName);
  body.appendChild(form);
}

function removeChunkAndRerender(chunkId) {
  currentChunks = currentChunks.filter((chunk) => chunk.id !== chunkId);
  renderDocGroups(currentChunks);
}

async function handleDeleteChunk(chunk, deleteBtn) {
  const indexName = indexSelect.value;
  deleteBtn.disabled = true;

  try {
    const res = await fetch(
      `/api/indexes/${encodeURIComponent(indexName)}/docs/${encodeURIComponent(chunk.id)}`,
      { method: "DELETE" }
    );
    if (!res.ok) {
      throw new Error(await extractErrorDetail(res));
    }
  } catch (err) {
    deleteBtn.disabled = false;
    showToast(`Failed to delete chunk "${chunk.id}": ${err.message}`, true);
    return;
  }

  const words = chunk.text.trim().split(/\s+/).filter(Boolean);
  const preview = words.slice(0, 6).join(" ") + (words.length > 6 ? "…" : "");
  removeChunkAndRerender(chunk.id);
  adjustDocCount(-1);
  showToast(`Deleted chunk "${chunk.id}" ("${preview}")`);
  newDocumentButton.focus();
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

  const actions = document.createElement("div");
  actions.className = "chunk-row-actions";

  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.className = "action-button none";
  editBtn.textContent = "Edit";
  editBtn.setAttribute("aria-label", `Edit chunk ${chunk.id}`);
  editBtn.addEventListener("click", () => {
    openForm(row.parentElement, {
      mode: "edit",
      chunk,
      isNewDocument: false,
      groupKey: resolveGroupKey(currentChunks),
      opener: editBtn,
      insertAfter: row,
    });
  });
  actions.appendChild(editBtn);

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "action-button none delete-btn";
  deleteBtn.textContent = "Delete";
  deleteBtn.setAttribute("aria-label", `Delete chunk ${chunk.id}`);
  deleteBtn.addEventListener("click", () => handleDeleteChunk(chunk, deleteBtn));
  actions.appendChild(deleteBtn);

  row.appendChild(actions);

  return row;
}

function createDocGroupCard(name, chunks, isExpanded) {
  const card = document.createElement("section");
  card.className = "panel doc-group" + (isExpanded ? " expanded" : "");

  const body = document.createElement("div");
  body.className = "doc-group-body";

  const headerRow = document.createElement("div");
  headerRow.className = "doc-group-header-row";

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
    if (nowExpanded) {
      expandedGroups.add(name);
    } else {
      expandedGroups.delete(name);
    }
  });

  headerRow.appendChild(header);

  const addChunkBtn = document.createElement("button");
  addChunkBtn.type = "button";
  addChunkBtn.className = "action-button none add-chunk-button";
  addChunkBtn.textContent = "+ Add chunk";
  addChunkBtn.setAttribute("aria-label", `Add chunk to ${name}`);
  addChunkBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    if (!card.classList.contains("expanded")) {
      card.classList.add("expanded");
      header.setAttribute("aria-expanded", "true");
      expandedGroups.add(name);
    }
    const groupKey = resolveGroupKey(currentChunks);
    const presetValue = groupKey && name !== "Ungrouped" ? name : null;
    openForm(body, {
      mode: "add",
      isNewDocument: false,
      groupKey,
      presetGroupValue: presetValue,
      opener: addChunkBtn,
    });
  });
  headerRow.appendChild(addChunkBtn);

  card.appendChild(headerRow);

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
  if (expandedGroups.size === 0) {
    const firstName = groups.keys().next().value;
    if (firstName !== undefined) {
      expandedGroups.add(firstName);
    }
  }

  for (const [name, groupChunksList] of groups) {
    docsArea.appendChild(createDocGroupCard(name, groupChunksList, expandedGroups.has(name)));
  }
}

async function loadDocsForSelectedIndex() {
  const name = indexSelect.value;
  if (!name) {
    return;
  }

  hideError();
  closeOpenForm();
  clearChildren(newDocFormSlot);
  expandedGroups = new Set();
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

  currentChunks = Array.isArray(chunks) ? chunks : [];
  renderDocGroups(currentChunks);
}

newDocumentButton.addEventListener("click", () => {
  if (!indexSelect.value) {
    return;
  }
  const groupKey = resolveGroupKey(currentChunks);
  openForm(newDocFormSlot, {
    mode: "add",
    isNewDocument: true,
    groupKey: groupKey || "sourceDoc",
    presetGroupValue: null,
    opener: newDocumentButton,
  });
});

indexSelect.addEventListener("change", () => {
  updateCountBadge();
  loadDocsForSelectedIndex();
});

loadIndexes();
