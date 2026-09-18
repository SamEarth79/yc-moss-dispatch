"""
FastAPI + WebSocket server for the interactive dispatcher UI.

Per transcript update from the client (a debounced text field standing in for live
ASR): fires a Moss query against the protocol index, AND (if DEEPSEEK_API_KEY is set)
an LLM call to extract structured fields (#5). Dispatching a unit (#2) actually claims
an available unit of the right type and assigns it a mocked ETA that counts down (#9),
rather than being a no-op UI toggle. Caller location (#4) is picked from the seeded
demo addresses.

Both Moss indexes are loaded once at server startup, same "load once, query many times
locally" pattern as everywhere else in backend/.

Transcript updates are handled by a dedicated worker that only ever acts on the LATEST
transcript, not a queue of every debounced keystroke: DeepSeek extraction is much slower
than Moss's sub-10ms retrieval, so processing every message in strict order would mean
the panel keeps changing for seconds after the user stops typing, replaying stale
intermediate states. See transcript_worker below.
"""

import asyncio
import hashlib
import os
import random
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from moss import MossClient, QueryOptions
from starlette.websockets import WebSocketState

from live_panel import LIVE_DATA_INDEX_NAME, PROTOCOL_INDEX_NAME, WINDOW_WORDS, trailing_window
from query_nearest_facility import haversine_miles, nearest_facility
from structured_extraction import extract_structured_fields

NEAREST_FACILITIES_SHOWN = 3


def distance_label(miles: float) -> str:
    meters = miles * 1609.34
    if meters < 1000:
        return f"{round(meters / 10) * 10}m"
    return f"{meters / 1000:.1f}km"


def static_occupancy_pct(facility_id: str) -> int:
    """Deterministic (not random-per-request) occupancy % per facility — no real bed-
    census data is available, so this is a stable stand-in derived from the facility's
    own id, same value every time rather than reshuffling on each request."""
    digest = hashlib.md5(facility_id.encode()).hexdigest()
    return 40 + (int(digest[:8], 16) % 56)

moss_client: MossClient | None = None

# Fictional caller locations (quick-pick demo addresses) placed in Albany County, NY so
# facility routing has real hospital density to rank against. Reuses the seeded incident
# addresses so the address-history lookup has real data to surface for each one.
CALLER_LOCATIONS = {
    "42 Oak Street": {"county": "Albany", "lat": 42.6600, "lon": -73.7550},
    "118 Birch Avenue": {"county": "Albany", "lat": 42.6450, "lon": -73.7600},
    "7 Maple Court": {"county": "Albany", "lat": 42.6526, "lon": -73.7562},
    "900 Cedar Boulevard": {"county": "Albany", "lat": 42.6700, "lon": -73.7700},
    "55 Pine Street": {"county": "Albany", "lat": 42.6380, "lon": -73.7480},
}

UNITS = [
    {"id": "Engine 4", "type": "FD"},
    {"id": "Engine 9", "type": "FD"},
    {"id": "Medic 12", "type": "EMS"},
    {"id": "Medic 3", "type": "EMS"},
    {"id": "Patrol 21", "type": "PD"},
    {"id": "Patrol 8", "type": "PD"},
]


def unit_type_for_action(action: str | None) -> str:
    a = (action or "").lower()
    if "fd" in a or "fire" in a:
        return "FD"
    if "pd" in a or "police" in a:
        return "PD"
    return "EMS"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global moss_client
    load_dotenv(Path(__file__).resolve().parent / ".env")
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")
    if not project_id or not project_key:
        raise RuntimeError("Missing MOSS_PROJECT_ID / MOSS_PROJECT_KEY in .env")

    moss_client = MossClient(project_id, project_key)
    print("Loading protocol-index and live-data-index into memory...")
    await moss_client.load_indexes([PROTOCOL_INDEX_NAME, LIVE_DATA_INDEX_NAME])
    print("Indexes loaded. Ready for connections.")
    yield
    await moss_client.unload_indexes([PROTOCOL_INDEX_NAME, LIVE_DATA_INDEX_NAME])


app = FastAPI(lifespan=lifespan)


async def safe_send_json(websocket: WebSocket, payload: dict, send_lock: asyncio.Lock):
    """A slow in-flight call (DeepSeek, Nominatim, Moss) can finish after the client has
    already disconnected — send_json would otherwise raise. send_lock also serializes
    sends across the transcript worker, the unit-status ticker, and the main message
    loop, since Starlette doesn't allow concurrent sends on one WebSocket."""
    async with send_lock:
        if websocket.application_state != WebSocketState.CONNECTED:
            return
        try:
            await websocket.send_json(payload)
        except RuntimeError:
            pass


def dev_log_payload(service: str, call_type: str, latency_ms: float | None, summary: str):
    return {
        "type": "dev_log",
        "service": service,
        "callType": call_type,
        "latencyMs": round(latency_ms, 1) if latency_ms is not None else None,
        "summary": summary,
    }


async def caller_context_payload(address: str, lat: float, lon: float, county: str | None, websocket: WebSocket, send_lock: asyncio.Lock):
    history = await moss_client.query(
        LIVE_DATA_INDEX_NAME,
        "prior incidents",
        QueryOptions(top_k=5, filter={"field": "address", "condition": {"$eq": address}}),
    )
    await safe_send_json(
        websocket,
        dev_log_payload("moss", "incident-lookup", history.time_taken_ms, f'address="{address}" → {len(history.docs)} records'),
        send_lock,
    )
    incidents = [
        {
            "date": d.metadata.get("date"),
            "incidentType": d.metadata.get("incidentType"),
            "outcome": d.metadata.get("outcome"),
            "hazardFlag": d.metadata.get("hazardFlag"),
        }
        for d in history.docs
    ]

    facility_start = time.monotonic()
    ranked = await nearest_facility(moss_client, lat, lon, county)
    facility_ms = (time.monotonic() - facility_start) * 1000

    top_facilities = ranked[:NEAREST_FACILITIES_SHOWN]
    facilities = [
        {
            "name": f.metadata["name"],
            "address": f.metadata["address"],
            "city": f.metadata["city"],
            "distanceLabel": distance_label(
                haversine_miles(lat, lon, float(f.metadata["lat"]), float(f.metadata["lon"]))
            ),
            "occupancyPct": static_occupancy_pct(f.id),
        }
        for f in top_facilities
    ]

    await safe_send_json(
        websocket,
        dev_log_payload(
            "moss",
            "facility-lookup",
            facility_ms,
            f'county={county or "none"} → {len(ranked)} candidates → nearest: {facilities[0]["name"] if facilities else "none"}',
        ),
        send_lock,
    )

    return {
        "type": "caller_context",
        "address": address,
        "county": county,
        "incidents": incidents,
        "nearestFacilities": facilities,
    }


def units_payload(unit_state):
    return {
        "type": "unit_status",
        "units": [
            {"id": u["id"], "type": u["type"], "status": unit_state[u["id"]]["status"], "eta": unit_state[u["id"]]["eta"]}
            for u in UNITS
        ],
    }


async def unit_status_ticker(websocket: WebSocket, unit_state: dict, send_lock: asyncio.Lock):
    """Background loop (#9): counts down ETA for dispatched units, and occasionally
    flips an idle unit's status for liveliness."""
    while True:
        await asyncio.sleep(3)
        any_countdown = False
        for uid, s in unit_state.items():
            if s["status"] == "en route" and s["eta"] is not None:
                s["eta"] = max(0, s["eta"] - 1)
                any_countdown = True
                if s["eta"] == 0:
                    s["status"] = "on scene"
                    s["eta"] = None

        if not any_countdown:
            idle = [uid for uid, s in unit_state.items() if s["status"] != "en route"]
            if idle:
                uid = random.choice(idle)
                unit_state[uid]["status"] = random.choice(["available", "on scene", "returning"])

        await safe_send_json(websocket, units_payload(unit_state), send_lock)


async def timed(coro):
    start = time.monotonic()
    value = await coro
    return value, (time.monotonic() - start) * 1000


async def transcript_worker(websocket: WebSocket, send_lock: asyncio.Lock, latest: dict, ready: asyncio.Event):
    """Waits for a transcript to process, always picking up whatever is CURRENTLY the
    latest one when it becomes free — not a FIFO queue. If several keystrokes arrived
    while a previous (slow) extraction call was in flight, all but the newest are
    dropped here rather than being processed one by one after the fact."""
    while True:
        await ready.wait()
        ready.clear()
        text = latest["text"]
        if not text:
            continue

        query_text = trailing_window(text, WINDOW_WORDS)
        protocol_task = moss_client.query(PROTOCOL_INDEX_NAME, query_text, QueryOptions(top_k=1))
        extraction_task = timed(extract_structured_fields(text))
        result, (fields, extraction_ms) = await asyncio.gather(protocol_task, extraction_task)
        top = result.docs[0]

        await safe_send_json(
            websocket,
            {
                "type": "protocol_update",
                "transcript": text,
                "latencyMs": result.time_taken_ms,
                "matchId": top.id,
                "matchText": top.text,
                "priority": top.metadata.get("priority"),
                "suggestedAction": top.metadata.get("suggestedAction"),
            },
            send_lock,
        )
        await safe_send_json(
            websocket,
            dev_log_payload("moss", "protocol-query", result.time_taken_ms, f'"{query_text}" → {top.id} ({top.score:.2f})'),
            send_lock,
        )

        await safe_send_json(websocket, {"type": "extraction_update", "fields": fields}, send_lock)
        if fields is None:
            extraction_summary = "skipped — DEEPSEEK_API_KEY not set"
        else:
            set_fields = [f"{k}={v}" for k, v in fields.items() if v not in (None, "")]
            extraction_summary = ", ".join(set_fields[:3]) or "no fields extracted"
        await safe_send_json(websocket, dev_log_payload("deepseek", "extraction", extraction_ms, extraction_summary), send_lock)


@app.websocket("/ws")
async def ws_session(websocket: WebSocket):
    await websocket.accept()
    send_lock = asyncio.Lock()

    unit_state = {u["id"]: {"status": random.choice(["available", "available", "on scene"]), "eta": None} for u in UNITS}
    await safe_send_json(websocket, units_payload(unit_state), send_lock)
    status_task = asyncio.create_task(unit_status_ticker(websocket, unit_state, send_lock))

    latest_transcript = {"text": None}
    transcript_ready = asyncio.Event()
    worker_task = asyncio.create_task(transcript_worker(websocket, send_lock, latest_transcript, transcript_ready))

    try:
        while True:
            msg = await websocket.receive_json()

            if msg["type"] == "set_caller":
                address = msg["address"]
                loc = CALLER_LOCATIONS[address]
                payload = await caller_context_payload(address, loc["lat"], loc["lon"], loc["county"], websocket, send_lock)
                await safe_send_json(websocket, payload, send_lock)

            elif msg["type"] == "transcript":
                text = msg["text"].strip()
                latest_transcript["text"] = text
                transcript_ready.set()

            elif msg["type"] == "dispatch":
                unit_type = unit_type_for_action(msg.get("action"))
                candidate = next(
                    (u for u in UNITS if u["type"] == unit_type and unit_state[u["id"]]["status"] == "available"),
                    None,
                )
                if candidate:
                    unit_state[candidate["id"]]["status"] = "en route"
                    unit_state[candidate["id"]]["eta"] = random.randint(4, 12)
                    assigned_id = candidate["id"]
                else:
                    assigned_id = None

                payload = units_payload(unit_state)
                payload["assignedUnit"] = assigned_id
                await safe_send_json(websocket, payload, send_lock)

    except WebSocketDisconnect:
        pass
    finally:
        status_task.cancel()
        worker_task.cancel()


STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
