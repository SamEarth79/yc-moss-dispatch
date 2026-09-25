const deviationCountBadge = document.getElementById("deviationCountBadge");
const errorBanner = document.getElementById("errorBanner");
const errorBannerText = document.getElementById("errorBannerText");
const retryButton = document.getElementById("retryButton");
const deviationsArea = document.getElementById("deviationsArea");

const CLAMP_MIN_LENGTH = 200;

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

function renderState(className, message) {
  clearChildren(deviationsArea);
  const el = document.createElement("div");
  el.className = className;
  el.textContent = message;
  deviationsArea.appendChild(el);
}

function createClampedText(text) {
  const wrap = document.createElement("div");
  const p = document.createElement("p");
  p.className = "chunk-text deviation-text";
  p.textContent = text;
  wrap.appendChild(p);

  if (text.length > CLAMP_MIN_LENGTH) {
    p.classList.add("clamped");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "show-more-btn";
    btn.textContent = "Show more";
    btn.addEventListener("click", () => {
      const isClamped = p.classList.contains("clamped");
      p.classList.toggle("clamped", !isClamped);
      btn.textContent = isClamped ? "Show less" : "Show more";
    });
    wrap.appendChild(btn);
  }
  return wrap;
}

function createRow(label, valueNode) {
  const row = document.createElement("div");
  row.className = "kv-row deviation-row";

  const key = document.createElement("div");
  key.className = "kv-key";
  key.textContent = label;
  row.appendChild(key);

  const value = document.createElement("div");
  value.className = "deviation-value";
  value.appendChild(valueNode);
  row.appendChild(value);
  return row;
}

function createCallerNode(record) {
  const wrap = document.createElement("div");
  wrap.appendChild(createClampedText(record.callerTranscript || ""));
  const summary = record.callerSummary && record.callerSummary.whatHappened;
  if (summary) {
    const note = document.createElement("p");
    note.className = "deviation-caller-summary";
    note.textContent = summary;
    wrap.appendChild(note);
  }
  return wrap;
}

function createProtocolNode(record) {
  const wrap = document.createElement("div");
  if (record.protocolChunkId) {
    const id = document.createElement("code");
    id.className = "chunk-id";
    id.textContent = record.protocolChunkId;
    wrap.appendChild(id);
  }
  wrap.appendChild(createClampedText(record.protocolChunkText || ""));
  return wrap;
}

function createRecord(record) {
  const card = document.createElement("article");
  card.className = "panel deviation-record";

  const head = document.createElement("div");
  head.className = "deviation-head";

  const title = document.createElement("h2");
  title.className = "deviation-title";
  title.textContent = record.deviationSummary || "Deviation";
  head.appendChild(title);

  if (record.seed === true) {
    const tag = document.createElement("span");
    tag.className = "badge deviation-sample-tag";
    tag.textContent = "sample";
    head.appendChild(tag);
  }
  card.appendChild(head);

  if (record.timestamp) {
    const time = document.createElement("time");
    time.className = "deviation-time";
    time.dateTime = record.timestamp;
    const parsed = new Date(record.timestamp);
    time.textContent = Number.isNaN(parsed.getTime()) ? record.timestamp : parsed.toLocaleString();
    card.appendChild(time);
  }

  const list = document.createElement("div");
  list.className = "kv-list";
  list.appendChild(createRow("Caller", createCallerNode(record)));
  list.appendChild(createRow("Protocol chunk", createProtocolNode(record)));
  list.appendChild(createRow("Dispatcher said", createClampedText(record.dispatcherTranscript || "")));
  if (record.reason) {
    list.appendChild(createRow("Reason", createClampedText(record.reason)));
  }
  card.appendChild(list);

  return card;
}

async function loadDeviations() {
  hideError();
  deviationCountBadge.textContent = "";
  renderState("loading-state", "Loading deviations…");

  let records;
  try {
    const res = await fetch("/api/deviations");
    if (!res.ok) {
      throw new Error(`Request failed (${res.status})`);
    }
    records = await res.json();
  } catch (err) {
    clearChildren(deviationsArea);
    showError("Failed to load deviations.", loadDeviations);
    return;
  }

  if (!Array.isArray(records) || records.length === 0) {
    deviationCountBadge.textContent = "0 deviations";
    renderState(
      "empty-state",
      "No deviations recorded yet. They appear here when a dispatcher's reply departs from protocol."
    );
    return;
  }

  deviationCountBadge.textContent = `${records.length} deviation${records.length === 1 ? "" : "s"}`;
  clearChildren(deviationsArea);
  for (const record of records) {
    deviationsArea.appendChild(createRecord(record));
  }
}

loadDeviations();
