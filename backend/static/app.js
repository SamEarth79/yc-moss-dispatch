const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const clockEl = document.getElementById("clock");
const transcriptInput = document.getElementById("transcriptInput");
const extractionFields = document.getElementById("extractionFields");
const priorityBadge = document.getElementById("priorityBadge");
const instructionText = document.getElementById("instructionText");
const deviationList = document.getElementById("deviationList");
const actionRow = document.getElementById("actionRow");
const callerSelect = document.getElementById("callerSelect");
const resolvedAddress = document.getElementById("resolvedAddress");
const incidentsHeading = document.getElementById("incidentsHeading");
const incidentList = document.getElementById("incidentList");
const facilityList = document.getElementById("facilityList");
const devFeed = document.getElementById("devFeed");
const micButton = document.getElementById("micButton");
const sampleButton = document.getElementById("sampleButton");
const voiceStatus = document.getElementById("voiceStatus");

const mockFollowsButton = document.getElementById("mockFollowsButton");
const mockDeviatesButton = document.getElementById("mockDeviatesButton");
const dispatcherInput = document.getElementById("dispatcherInput");
const dispatcherReason = document.getElementById("dispatcherReason");
const dispatcherSubmit = document.getElementById("dispatcherSubmit");
const dispatcherHelper = document.getElementById("dispatcherHelper");
const dispatcherMicButton = document.getElementById("dispatcherMicButton");
const dispatcherVoiceStatus = document.getElementById("dispatcherVoiceStatus");
const verdictSlot = document.getElementById("verdictSlot");

const DEV_FEED_MAX_ENTRIES = 40;

const CALLER_ADDRESSES = [
  "7 Maple Court",
  "42 Oak Street",
  "118 Birch Avenue",
  "900 Cedar Boulevard",
  "55 Pine Street",
];

const DEBOUNCE_MS = 50;

let ws;
let currentSuggestedAction = null;

function priorityClass(priority) {
  if (!priority) return "";
  if (priority.startsWith("P1")) return "p1";
  if (priority.startsWith("P2")) return "p2";
  if (priority.startsWith("P3")) return "p3";
  return "";
}

function occupancySeverity(pct) {
  if (pct >= 85) return "critical";
  if (pct >= 65) return "warn";
  return "ok";
}

function renderCallerContext(msg) {
  resolvedAddress.textContent = `${msg.address}${msg.county ? ` (${msg.county} County)` : ""}`;
  incidentsHeading.textContent = `${msg.address}'s Past Incidents`;

  incidentList.innerHTML = "";
  if (msg.incidents.length === 0) {
    incidentList.innerHTML = '<div class="extraction-empty">(none on file)</div>';
  } else {
    for (const inc of msg.incidents) {
      const card = document.createElement("div");
      const hasHazard = inc.hazardFlag !== "none";
      card.className = "incident-card" + (hasHazard ? " incident-card--hazard" : "");
      card.innerHTML = `
        <div class="incident-card-header">
          <span class="incident-type">${inc.incidentType.replaceAll("-", " ")}</span>
          <span class="incident-date">${inc.date}</span>
        </div>
        <div class="incident-outcome">${inc.outcome.replaceAll("-", " ")}</div>
        ${hasHazard ? `<div class="incident-hazard">⚠ ${inc.hazardFlag.replaceAll("-", " ")}</div>` : ""}
      `;
      incidentList.appendChild(card);
    }
  }

  facilityList.innerHTML = "";
  if (msg.nearestFacilities.length === 0) {
    facilityList.innerHTML = '<div class="extraction-empty">(none found)</div>';
  } else {
    for (const f of msg.nearestFacilities) {
      const card = document.createElement("div");
      card.className = "facility-card";
      card.innerHTML = `
        <div class="facility-card-top">
          <span class="facility-distance">${f.distanceLabel}</span>
          <span class="facility-occupancy facility-occupancy--${occupancySeverity(f.occupancyPct)}">${f.occupancyPct}% occupied</span>
        </div>
        <div class="facility-name">${f.name}</div>
        <div class="facility-address">${f.address}, ${f.city}</div>
      `;
      facilityList.appendChild(card);
    }
  }
}

function isEmpty(value) {
  return value === null || value === undefined || value === "";
}

function consciousnessSeverity(value) {
  if (value === "unconscious") return "critical";
  if (value === "conscious") return "ok";
  return "neutral";
}

function weaponsSeverity(value) {
  if (value === true) return "critical";
  if (value === false) return "ok";
  return "neutral";
}

function patientsSeverity(value) {
  return typeof value === "number" && value > 1 ? "warn" : "neutral";
}

function makeRow(label, value, severity) {
  const row = document.createElement("div");
  row.className = `kv-row kv-row--${severity}`;
  row.innerHTML = `<span class="kv-key">${label}</span><span class="kv-value">${isEmpty(value) ? "—" : String(value)}</span>`;
  return row;
}

function yesNo(value, yesWhen) {
  return value === yesWhen ? "Yes" : value === null || value === undefined ? null : "No";
}

let latestFields = {};

function renderExtraction(fields) {
  latestFields = fields;
  extractionFields.innerHTML = "";

  const departments = fields.departments ?? [];
  extractionFields.appendChild(makeRow("What", fields.whatHappened, "neutral"));
  extractionFields.appendChild(makeRow("Where", callerSelect.value, "neutral"));
  extractionFields.appendChild(makeRow("Department", departments.join(", "), "neutral"));
  extractionFields.appendChild(makeRow("Patients", fields.numberOfPatients, patientsSeverity(fields.numberOfPatients)));
  extractionFields.appendChild(makeRow("Weapons", yesNo(fields.weapons, true), weaponsSeverity(fields.weapons)));
  extractionFields.appendChild(makeRow("Conscious", yesNo(fields.consciousness, "conscious"), consciousnessSeverity(fields.consciousness)));
}

function renderInstructionSteps(text) {
  const steps = text.split(/(?<=[.!?])\s+(?=[A-Z"])/).map((s) => s.trim()).filter(Boolean);
  const list = document.createElement("ul");
  list.className = "instruction-steps";
  for (const step of steps) {
    const li = document.createElement("li");
    li.textContent = step;
    list.appendChild(li);
  }
  instructionText.replaceChildren(list);
}

function renderProtocolUpdate(msg) {
  onScreenChunk = { id: msg.matchId, text: msg.matchText };
  updateSubmitState();

  priorityBadge.textContent = msg.priority ?? "—";
  priorityBadge.className = "badge " + priorityClass(msg.priority);

  renderInstructionSteps(msg.matchText);
  currentSuggestedAction = msg.suggestedAction;
  renderActionButton();
}

const DEVIATION_PLACEHOLDER = "Related deviations appear as the call develops…";
const MAX_DEVIATION_CARDS = 2;

function formatDeviationDate(timestamp) {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function makeDeviationLine(label, text) {
  const line = makeEl("div", "deviation-line");
  line.title = text;
  line.append(makeEl("span", "deviation-line-label", label), document.createTextNode(` ${text}`));
  return line;
}

function makeDeviationCard(deviation) {
  const card = makeEl("div", "deviation-card");
  const header = makeEl("div", "incident-card-header");
  const summary = makeEl("span", "deviation-summary", deviation.summary ?? "");
  summary.title = deviation.summary ?? "";
  header.append(summary, makeEl("span", "incident-date", formatDeviationDate(deviation.timestamp)));
  card.append(
    header,
    makeDeviationLine("Protocol said:", deviation.protocolChunkText ?? ""),
    makeDeviationLine("Dispatcher said:", deviation.dispatcherTranscript ?? ""),
  );
  if (deviation.reason) {
    const reason = makeEl("div", "deviation-line deviation-reason", `Reason: ${deviation.reason}`);
    reason.title = deviation.reason;
    card.appendChild(reason);
  }
  return card;
}

function renderDeviations(deviations) {
  const shown = Array.isArray(deviations) ? deviations.slice(0, MAX_DEVIATION_CARDS) : [];
  if (shown.length === 0) {
    deviationList.replaceChildren(makeEl("p", "instruction-placeholder", DEVIATION_PLACEHOLDER));
    return;
  }
  deviationList.replaceChildren(...shown.map(makeDeviationCard));
}

function renderActionButton() {
  actionRow.innerHTML = "";
  const isNone = !currentSuggestedAction || currentSuggestedAction === "none" || currentSuggestedAction === "monitor-no-dispatch";

  const btn = document.createElement(isNone ? "span" : "button");
  btn.className = "action-button" + (isNone ? " none" : "");
  btn.textContent = isNone
    ? currentSuggestedAction === "monitor-no-dispatch"
      ? "Monitor — no dispatch needed"
      : "No action required yet"
    : currentSuggestedAction.replaceAll("-", " ");

  if (!isNone) {
    btn.onclick = () => {
      btn.disabled = true;
      btn.textContent = "Dispatching…";
      ws.send(JSON.stringify({ type: "dispatch", action: currentSuggestedAction }));
    };
  }

  actionRow.appendChild(btn);
}

function renderUnitStatus(msg) {
  if (msg.assignedUnit) {
    const btn = actionRow.querySelector("button.action-button");
    if (btn) {
      btn.textContent = `✓ ${msg.assignedUnit} dispatched`;
      btn.classList.add("confirmed");
    }
  } else if ("assignedUnit" in msg && msg.assignedUnit === null) {
    const btn = actionRow.querySelector("button.action-button");
    if (btn) {
      btn.textContent = "No units available";
      btn.disabled = true;
    }
  }
}

function renderDevLog(msg) {
  const empty = devFeed.querySelector(".extraction-empty");
  if (empty) empty.remove();

  const time = new Date().toLocaleTimeString("en-US", { hour12: false });
  const entry = document.createElement("div");
  entry.className = `dev-log-entry dev-log-entry--${msg.service}`;
  entry.innerHTML = `
    <span class="dev-log-time">${time}</span>
    <span class="dev-log-service dev-log-service--${msg.service}">${msg.service}</span>
    <span class="dev-log-type">${msg.callType}</span>
    <span class="dev-log-latency">${msg.latencyMs != null ? `${msg.latencyMs}ms` : "—"}</span>
    <span class="dev-log-summary">${msg.summary}</span>
  `;
  devFeed.prepend(entry);

  while (devFeed.children.length > DEV_FEED_MAX_ENTRIES) {
    devFeed.removeChild(devFeed.lastChild);
  }
}

function setupCallerSelect() {
  for (const addr of CALLER_ADDRESSES) {
    const opt = document.createElement("option");
    opt.value = addr;
    opt.textContent = addr;
    callerSelect.appendChild(opt);
  }
  callerSelect.onchange = () => {
    renderExtraction(latestFields);
    resetDispatcherPanel();
    renderDeviations([]);
    ws.send(JSON.stringify({ type: "set_caller", address: callerSelect.value }));
  };
}

function debounce(fn, ms) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

const sendTranscript = debounce((text) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "transcript", text }));
  }
}, DEBOUNCE_MS);

function connect() {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${scheme}://${location.host}/ws`);

  ws.onopen = () => {
    statusDot.className = "dot connected";
    statusText.textContent = "Connected";
    ws.send(JSON.stringify({ type: "set_caller", address: callerSelect.value }));
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "caller_context") {
      renderCallerContext(msg);
    } else if (msg.type === "protocol_update") {
      renderProtocolUpdate(msg);
    } else if (msg.type === "deviation_update") {
      renderDeviations(msg.deviations);
    } else if (msg.type === "extraction_update") {
      renderExtraction(msg.fields);
    } else if (msg.type === "unit_status") {
      renderUnitStatus(msg);
    } else if (msg.type === "dev_log") {
      renderDevLog(msg);
    } else if (msg.type === "voice_transcript") {
      transcriptInput.value = msg.text;
    } else if (msg.type === "dispatcher_voice_transcript") {
      handleDispatcherTranscript(msg);
    } else if (msg.type === "voice_status") {
      if (msg.channel === "dispatcher") handleDispatcherVoiceStatus(msg);
      else handleVoiceStatus(msg);
    }
  };

  ws.onclose = () => {
    statusDot.className = "dot";
    statusText.textContent = "Disconnected";
  };
}

function tickClock() {
  clockEl.textContent = new Date().toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

const SAMPLE_CALL_URL = "samples/sample-call.wav";
const AUDIO_CHUNK_BYTES = 3200;
const AUDIO_CHUNK_MS = 100;

let stopActiveVoice = null;
let voiceReadyResolver = null;
let isCallerVoiceBusy = false;
let dispatcherVoice = null;
let dispatcherReadyResolver = null;
let dispatcherBaseText = "";
const CALLER_BUSY_HINT = "Stop the caller mic or sample call to use the dispatcher mic";

function setVoiceStatus(text, isError = false) {
  voiceStatus.textContent = text;
  voiceStatus.className = "voice-status" + (isError ? " error" : "");
}

function handleVoiceStatus(msg) {
  if (msg.state === "listening" && voiceReadyResolver) {
    voiceReadyResolver(true);
  } else if (msg.state === "unavailable") {
    setVoiceStatus(msg.reason, true);
    if (voiceReadyResolver) voiceReadyResolver(false);
  }
}

async function beginVoiceSession() {
  const ready = new Promise((resolve) => {
    voiceReadyResolver = resolve;
  });
  transcriptInput.value = "";
  ws.send(JSON.stringify({ type: "voice_start" }));
  const ok = await ready;
  voiceReadyResolver = null;
  return ok;
}

function endVoiceSession() {
  if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "voice_stop" }));
  stopActiveVoice = null;
  micButton.classList.remove("active");
  micButton.textContent = "Start mic";
  sampleButton.classList.remove("active");
  sampleButton.textContent = "Play sample call";
  micButton.disabled = false;
  sampleButton.disabled = false;
  setVoiceStatus("");
  setCallerVoiceBusy(false);
}

function requestMicStream() {
  return navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
}

async function startPcmCapture(mediaStream) {
  const audioContext = new AudioContext({ sampleRate: 16000 });
  await audioContext.audioWorklet.addModule("pcm-worklet.js");
  const source = audioContext.createMediaStreamSource(mediaStream);
  const worklet = new AudioWorkletNode(audioContext, "pcm-processor");
  worklet.port.onmessage = (event) => ws.send(event.data);
  source.connect(worklet);
  return () => {
    mediaStream.getTracks().forEach((track) => track.stop());
    audioContext.close();
  };
}

async function startMic() {
  micButton.disabled = true;
  sampleButton.disabled = true;
  setCallerVoiceBusy(true);
  let mediaStream;
  try {
    mediaStream = await requestMicStream();
  } catch {
    setVoiceStatus("Microphone access was denied", true);
    micButton.disabled = false;
    sampleButton.disabled = false;
    setCallerVoiceBusy(false);
    return;
  }
  if (!(await beginVoiceSession())) {
    mediaStream.getTracks().forEach((track) => track.stop());
    micButton.disabled = false;
    sampleButton.disabled = false;
    setCallerVoiceBusy(false);
    return;
  }

  const stopCapture = await startPcmCapture(mediaStream);

  stopActiveVoice = () => {
    stopCapture();
    endVoiceSession();
  };
  micButton.disabled = false;
  micButton.classList.add("active");
  micButton.textContent = "Stop mic";
  setVoiceStatus("Listening…");
}

function findWavPcmData(buffer) {
  const view = new DataView(buffer);
  let offset = 12;
  while (offset + 8 <= view.byteLength) {
    const chunkId = String.fromCharCode(...new Uint8Array(buffer, offset, 4));
    const chunkSize = view.getUint32(offset + 4, true);
    if (chunkId === "data") return new Uint8Array(buffer, offset + 8, Math.min(chunkSize, view.byteLength - offset - 8));
    offset += 8 + chunkSize + (chunkSize % 2);
  }
  throw new Error("WAV data chunk not found");
}

async function startSample() {
  micButton.disabled = true;
  sampleButton.disabled = true;
  setCallerVoiceBusy(true);
  const wavBuffer = await (await fetch(SAMPLE_CALL_URL)).arrayBuffer();
  const pcm = findWavPcmData(wavBuffer);
  if (!(await beginVoiceSession())) {
    micButton.disabled = false;
    sampleButton.disabled = false;
    setCallerVoiceBusy(false);
    return;
  }

  const audio = new Audio(SAMPLE_CALL_URL);
  audio.play();
  let position = 0;
  const timer = setInterval(() => {
    if (position >= pcm.length) {
      clearInterval(timer);
      setTimeout(() => stopActiveVoice && stopActiveVoice(), 1500);
      return;
    }
    ws.send(pcm.slice(position, position + AUDIO_CHUNK_BYTES));
    position += AUDIO_CHUNK_BYTES;
  }, AUDIO_CHUNK_MS);

  stopActiveVoice = () => {
    clearInterval(timer);
    audio.pause();
    endVoiceSession();
  };
  sampleButton.disabled = false;
  sampleButton.classList.add("active");
  sampleButton.textContent = "Stop sample";
  setVoiceStatus("Playing sample call…");
}

micButton.onclick = () => (stopActiveVoice ? stopActiveVoice() : startMic());
sampleButton.onclick = () => (stopActiveVoice ? stopActiveVoice() : startSample());

function setDispatcherVoiceStatus(text, isError = false) {
  dispatcherVoiceStatus.textContent = text;
  dispatcherVoiceStatus.className = "voice-status" + (isError ? " error" : "");
}

function refreshVoiceLocks() {
  const isDispatcherActive = dispatcherVoice !== null;
  const isDispatcherStarting = isDispatcherActive && !dispatcherVoice.stop;
  const isBlockedByCaller = isCallerVoiceBusy && !isDispatcherActive;
  dispatcherMicButton.disabled = isBlockedByCaller || isDispatcherStarting;
  dispatcherMicButton.title = isBlockedByCaller ? CALLER_BUSY_HINT : "";
  dispatcherMicButton.classList.toggle("active", isDispatcherActive && !isDispatcherStarting);
  dispatcherMicButton.setAttribute("aria-pressed", String(isDispatcherActive && !isDispatcherStarting));
  dispatcherMicButton.textContent = isDispatcherActive && !isDispatcherStarting ? "Stop dispatcher mic" : "Start dispatcher mic";
  if (isBlockedByCaller) setDispatcherVoiceStatus(CALLER_BUSY_HINT);
  else if (dispatcherVoiceStatus.textContent === CALLER_BUSY_HINT) setDispatcherVoiceStatus("");
  if (isDispatcherActive) {
    micButton.disabled = true;
    sampleButton.disabled = true;
  }
  mockFollowsButton.disabled = isDispatcherActive;
  mockDeviatesButton.disabled = isDispatcherActive;
  updateSubmitState();
}

function setCallerVoiceBusy(isBusy) {
  isCallerVoiceBusy = isBusy;
  refreshVoiceLocks();
}

function endDispatcherVoice({ notifyServer }) {
  if (dispatcherVoice === null) return;
  if (dispatcherVoice.stop) dispatcherVoice.stop();
  if (notifyServer && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "voice_stop", channel: "dispatcher" }));
  }
  dispatcherVoice = null;
  micButton.disabled = false;
  sampleButton.disabled = false;
  refreshVoiceLocks();
}

function handleDispatcherVoiceStatus(msg) {
  if (msg.state === "listening") {
    if (dispatcherReadyResolver) dispatcherReadyResolver(true);
    return;
  }
  if (msg.state === "unavailable" || msg.state === "error") {
    setDispatcherVoiceStatus(msg.reason || "Dispatcher voice is unavailable", true);
  }
  if (dispatcherReadyResolver) dispatcherReadyResolver(false);
  else endDispatcherVoice({ notifyServer: false });
}

function handleDispatcherTranscript(msg) {
  if (dispatcherVoice === null) return;
  dispatcherInput.value = dispatcherBaseText ? `${dispatcherBaseText} ${msg.text}` : msg.text;
  clearMockSelection();
  updateSubmitState();
}

async function startDispatcherMic() {
  dispatcherVoice = { stop: null };
  refreshVoiceLocks();
  setDispatcherVoiceStatus("");
  let mediaStream;
  try {
    mediaStream = await requestMicStream();
  } catch {
    setDispatcherVoiceStatus("Microphone access was denied", true);
    endDispatcherVoice({ notifyServer: false });
    return;
  }
  const ready = new Promise((resolve) => {
    dispatcherReadyResolver = resolve;
  });
  dispatcherBaseText = dispatcherInput.value.trim();
  ws.send(JSON.stringify({ type: "voice_start", channel: "dispatcher" }));
  const ok = await ready;
  dispatcherReadyResolver = null;
  if (!ok) {
    mediaStream.getTracks().forEach((track) => track.stop());
    endDispatcherVoice({ notifyServer: false });
    return;
  }
  dispatcherVoice.stop = await startPcmCapture(mediaStream);
  setDispatcherVoiceStatus("Listening…");
  refreshVoiceLocks();
}

dispatcherMicButton.onclick = () => {
  if (dispatcherVoice === null) startDispatcherMic();
  else endDispatcherVoice({ notifyServer: true });
  if (dispatcherVoice === null) setDispatcherVoiceStatus("");
};

const MOCK_REPLY_FOLLOWS =
  "Lean him forward and give five firm back blows, then five abdominal thrusts. Keep alternating until he coughs it out.";
const MOCK_REPLY_DEVIATES = "Give him a glass of water to wash it down and have him sit and rest.";

let onScreenChunk = null;
let isJudging = false;

function canSubmitReply() {
  return !isJudging && dispatcherVoice === null && onScreenChunk !== null && dispatcherInput.value.trim() !== "";
}

function updateSubmitState() {
  dispatcherSubmit.setAttribute("aria-disabled", String(!canSubmitReply()));
  dispatcherHelper.hidden = onScreenChunk !== null;
}

function clearMockSelection() {
  mockFollowsButton.setAttribute("aria-pressed", "false");
  mockDeviatesButton.setAttribute("aria-pressed", "false");
}

function fillMockReply(button, text) {
  dispatcherInput.value = text;
  clearMockSelection();
  button.setAttribute("aria-pressed", "true");
  updateSubmitState();
}

function resetDispatcherPanel() {
  dispatcherInput.value = "";
  dispatcherReason.value = "";
  clearMockSelection();
  verdictSlot.replaceChildren();
  updateSubmitState();
}

function makeEl(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function renderVerdictCard(result, chunkId, submittedText) {
  const deviated = result.verdict === "deviated";
  const card = makeEl("div", `verdict-card verdict-card--${deviated ? "deviated" : "followed"}`);
  card.setAttribute("role", "status");

  const title = makeEl("div", "verdict-title");
  title.appendChild(makeEl("span", "", deviated ? "Deviated" : "Followed protocol"));
  if (deviated) title.appendChild(makeEl("span", "source-tag source-tag--llm source-tag--inline", "LLM generated"));
  card.appendChild(title);

  const compared = makeEl("p", "verdict-meta", "Compared with protocol chunk ");
  compared.appendChild(makeEl("code", "", chunkId));
  card.appendChild(compared);
  card.appendChild(makeEl("p", "verdict-meta", `Submitted: ${submittedText}`));

  if (deviated) {
    card.appendChild(makeEl("p", "verdict-meta", result.deviationSummary));
    if (result.retrievable === false) {
      card.appendChild(makeEl("p", "verdict-warning", "Saved, but not retrievable for future calls."));
    } else {
      card.appendChild(makeEl("p", "verdict-meta", "Saved to deviation index"));
    }
  }
  verdictSlot.replaceChildren(card);
}

function renderVerdictError(status) {
  const card = makeEl("div", "verdict-card verdict-card--error");
  card.setAttribute("role", "alert");
  card.appendChild(
    makeEl("div", "verdict-title", status === 503 ? "Reply check is not configured." : "Couldn't check this reply. Try again."),
  );
  verdictSlot.replaceChildren(card);
}

async function submitDispatcherReply() {
  if (!canSubmitReply()) return;
  const chunk = onScreenChunk;
  const dispatcherText = dispatcherInput.value.trim();
  const reason = dispatcherReason.value.trim();
  const body = {
    dispatcherText,
    protocolChunkId: chunk.id,
    protocolChunkText: chunk.text,
    callerTranscript: transcriptInput.value,
  };
  if (reason) body.reason = reason;
  if (latestFields.whatHappened) body.callerSummary = { whatHappened: latestFields.whatHappened };

  isJudging = true;
  dispatcherSubmit.textContent = "Checking…";
  updateSubmitState();
  try {
    const response = await fetch("/api/deviations/judge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      renderVerdictError(response.status);
      return;
    }
    const result = await response.json();
    renderVerdictCard(result, chunk.id, dispatcherText);
    dispatcherInput.value = "";
    dispatcherReason.value = "";
    clearMockSelection();
  } catch {
    renderVerdictError(0);
  } finally {
    isJudging = false;
    dispatcherSubmit.textContent = "Submit";
    updateSubmitState();
  }
}

mockFollowsButton.onclick = () => fillMockReply(mockFollowsButton, MOCK_REPLY_FOLLOWS);
mockDeviatesButton.onclick = () => fillMockReply(mockDeviatesButton, MOCK_REPLY_DEVIATES);
dispatcherInput.addEventListener("input", () => {
  clearMockSelection();
  updateSubmitState();
});
dispatcherInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    submitDispatcherReply();
  }
});
dispatcherSubmit.onclick = submitDispatcherReply;

setupCallerSelect();
updateSubmitState();
renderExtraction({});
transcriptInput.addEventListener("input", (e) => {
  if (e.target.value.trim() === "") renderDeviations([]);
  sendTranscript(e.target.value);
});
tickClock();
setInterval(tickClock, 1000);
connect();
