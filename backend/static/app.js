const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const transcriptInput = document.getElementById("transcriptInput");
const latencyEl = document.getElementById("latency");
const extractionFields = document.getElementById("extractionFields");
const priorityBadge = document.getElementById("priorityBadge");
const instructionText = document.getElementById("instructionText");
const actionRow = document.getElementById("actionRow");
const callerSelect = document.getElementById("callerSelect");
const resolvedAddress = document.getElementById("resolvedAddress");
const incidentsHeading = document.getElementById("incidentsHeading");
const incidentList = document.getElementById("incidentList");
const facilityList = document.getElementById("facilityList");
const unitList = document.getElementById("unitList");
const devFeed = document.getElementById("devFeed");

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
  if (isEmpty(value)) return "neutral";
  const v = String(value).toLowerCase();
  if (v.includes("unconscious") || v.includes("unresponsive")) return "critical";
  if (v.includes("conscious")) return "ok";
  return "neutral";
}

function weaponsSeverity(value) {
  if (value === true) return "critical";
  if (value === false) return "ok";
  return "neutral";
}

function patientsSeverity(value) {
  if (typeof value === "number" && value > 1) return "warn";
  return "neutral";
}

function injuriesSeverity(value) {
  return isEmpty(value) ? "neutral" : "warn";
}

function makeTile(label, value, severity) {
  const tile = document.createElement("div");
  tile.className = `ex-tile ex-tile--${severity}`;
  tile.innerHTML = `
    <span class="ex-label">${label}</span>
    <span class="ex-value">${isEmpty(value) ? "—" : String(value)}</span>
  `;
  return tile;
}

function makeRow(label, value, severity) {
  const row = document.createElement("div");
  row.className = `ex-row ex-row--${severity}`;
  row.innerHTML = `<span class="ex-row-label">${label}</span><span class="ex-row-value">${isEmpty(value) ? "—" : String(value)}</span>`;
  return row;
}

function renderExtraction(fields) {
  extractionFields.innerHTML = "";

  if (!fields) {
    extractionFields.innerHTML = '<div class="extraction-empty">DEEPSEEK_API_KEY not set — extraction skipped.</div>';
    return;
  }

  const headline = document.createElement("div");
  headline.className = "ex-headline";
  headline.textContent = isEmpty(fields.whatHappened) ? "Awaiting details…" : fields.whatHappened;
  extractionFields.appendChild(headline);

  extractionFields.appendChild(makeTile("# of Patients", fields.numberOfPatients, patientsSeverity(fields.numberOfPatients)));
  extractionFields.appendChild(makeTile("Consciousness", fields.consciousness, consciousnessSeverity(fields.consciousness)));
  extractionFields.appendChild(makeTile("Weapons", fields.weapons === true ? "Yes" : fields.weapons === false ? "No" : null, weaponsSeverity(fields.weapons)));

  extractionFields.appendChild(makeRow("Location", fields.location, "neutral"));
  extractionFields.appendChild(makeRow("Injuries", fields.injuries, injuriesSeverity(fields.injuries)));
}

function renderProtocolUpdate(msg) {
  latencyEl.textContent = `${msg.latencyMs}ms`;

  priorityBadge.textContent = msg.priority ?? "—";
  priorityBadge.className = "badge " + priorityClass(msg.priority);

  instructionText.textContent = msg.matchText;
  currentSuggestedAction = msg.suggestedAction;
  renderActionButton();
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
  unitList.innerHTML = "";
  for (const unit of msg.units) {
    const li = document.createElement("li");
    const statusLabel = unit.status === "en route" && unit.eta != null ? `en route (${unit.eta}m)` : unit.status;
    li.innerHTML = `
      <span class="unit-id">${unit.id}</span>
      <span class="unit-type">${unit.type}</span>
      <span class="unit-status ${unit.status.replace(" ", "-")}">${statusLabel}</span>
    `;
    unitList.appendChild(li);
  }

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
  ws = new WebSocket(`ws://${location.host}/ws`);

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
    } else if (msg.type === "extraction_update") {
      renderExtraction(msg.fields);
    } else if (msg.type === "unit_status") {
      renderUnitStatus(msg);
    } else if (msg.type === "dev_log") {
      renderDevLog(msg);
    }
  };

  ws.onclose = () => {
    statusDot.className = "dot";
    statusText.textContent = "Disconnected";
  };
}

setupCallerSelect();
transcriptInput.addEventListener("input", (e) => sendTranscript(e.target.value));
connect();
