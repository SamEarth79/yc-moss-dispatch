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
transcript, not a queue of every debounced keystroke: LLM extraction is much slower
than Moss's sub-10ms retrieval, so processing every message in strict order would mean
the panel keeps changing for seconds after the user stops typing, replaying stale
intermediate states. See transcript_worker below.
"""

import asyncio
import hashlib
import json
import logging
import os
import random
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from moss import DocumentInfo, MossClient, QueryOptions
from pydantic import BaseModel, Field, field_validator
from starlette.websockets import WebSocketState

from live_panel import (
    DEVIATION_INDEX_NAME,
    LIVE_DATA_INDEX_NAME,
    PROTOCOL_INDEX_NAME,
    WINDOW_WORDS,
    trailing_window,
)
from query_nearest_facility import haversine_miles, nearest_facility
from basic_auth import BasicAuthMiddleware
from voice_stream import DeepgramStream, VoiceStreamUnavailable
from deviation_judge import judge_deviation
from structured_extraction import extract_llm_fields, extract_rule_fields

NEAREST_FACILITIES_SHOWN = 3

logger = logging.getLogger(__name__)

# Moss score scale is not documented in the SDK; tune against the seeded deviations.
DEVIATION_MIN_SCORE = 0.3


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

    # cache_path persists the downloaded index to disk and reuses it on the next
    # load if the cloud copy hasn't changed — every dev-server restart otherwise
    # re-downloads both indexes from Moss Cloud for free, which is exactly what
    # burned this project's usage credits during today's restart-heavy debugging.
    cache_path = os.getenv("MOSS_CACHE_DIR") or str(Path(__file__).resolve().parent / ".moss-cache")
    index_names = [PROTOCOL_INDEX_NAME, LIVE_DATA_INDEX_NAME]
    result = await moss_client.load_indexes(index_names, cache_path=cache_path)
    if result.failed:
        # load_indexes is best-effort — it never raises, it just reports per-index
        # failures — so a caller that ignores `.failed` gets a server that claims to
        # be "ready" while some indexes are silently unqueryable. Retry once, then
        # fail loudly rather than starting in that half-broken state.
        print(f"Index load failed for {list(result.failed.keys())}, retrying once: {result.failed}")
        retry = await moss_client.load_indexes(list(result.failed.keys()), cache_path=cache_path)
        if retry.failed:
            raise RuntimeError(f"Failed to load indexes after retry: {retry.failed}")

    loaded_indexes = list(index_names)

    # Optional: a missing or broken deviation index must not take the server down.
    try:
        deviation_result = await moss_client.load_indexes([DEVIATION_INDEX_NAME], cache_path=cache_path)
        if deviation_result.failed:
            logger.warning("Deviation index not loaded: %s", deviation_result.failed)
        else:
            loaded_indexes.append(DEVIATION_INDEX_NAME)
    except Exception:
        logger.warning("Deviation index not loaded", exc_info=True)

    print("Indexes loaded. Ready for connections.")
    yield
    await moss_client.unload_indexes(loaded_indexes)


app = FastAPI(lifespan=lifespan)
app.add_middleware(BasicAuthMiddleware)


async def safe_send_json(websocket: WebSocket, payload: dict, send_lock: asyncio.Lock):
    """A slow in-flight call (LLM, Moss) can finish after the client has
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


async def run_llm_extraction(websocket: WebSocket, send_lock: asyncio.Lock, text: str, rule_fields: dict, llm_state: dict):
    llm_fields, extraction_ms = await timed(extract_llm_fields(text))
    if llm_fields is None:
        summary = "skipped — LLM not configured"
    else:
        llm_state["fields"] = llm_fields
        summary = ", ".join(f"{k}={v}" for k, v in llm_fields.items() if v not in (None, "")) or "no fields extracted"
    await safe_send_json(websocket, {"type": "extraction_update", "fields": {**rule_fields, **llm_state["fields"]}}, send_lock)
    await safe_send_json(websocket, dev_log_payload("llm", "extraction", extraction_ms, summary), send_lock)


async def query_deviations(query_text: str):
    """Returns the Moss result, or None when the deviation index is unavailable, so a
    missing or failing deviation index never breaks the protocol path."""
    try:
        return await moss_client.query(DEVIATION_INDEX_NAME, query_text, QueryOptions(top_k=2))
    except Exception:
        logger.warning("Deviation query failed", exc_info=True)
        return None


def deviation_payload(doc) -> dict:
    metadata = doc.metadata or {}
    return {
        "id": doc.id,
        "summary": metadata.get("deviationSummary", ""),
        "dispatcherTranscript": metadata.get("dispatcherTranscript", ""),
        "reason": metadata.get("reason", ""),
        "timestamp": metadata.get("timestamp", ""),
        "score": doc.score,
        "protocolChunkText": metadata.get("protocolChunkText", ""),
    }


async def transcript_worker(websocket: WebSocket, send_lock: asyncio.Lock, latest: dict, ready: asyncio.Event):
    """Waits for a transcript to process, always picking up whatever is CURRENTLY the
    latest one when it becomes free — not a FIFO queue. Rule fields and the Moss query
    answer immediately; the slow local-LLM call runs in the background and is cancelled
    when a newer transcript arrives, so stale results never overwrite fresh ones."""
    llm_state = {"fields": {"whatHappened": None}, "task": None}
    try:
        while True:
            await ready.wait()
            ready.clear()
            text = latest["text"]
            if not text:
                continue

            if llm_state["task"] is not None:
                llm_state["task"].cancel()

            query_text = trailing_window(text, WINDOW_WORDS)
            result, deviation_result = await asyncio.gather(
                moss_client.query(PROTOCOL_INDEX_NAME, query_text, QueryOptions(top_k=1)),
                query_deviations(query_text),
            )
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

            deviation_docs = (
                [doc for doc in deviation_result.docs if doc.score >= DEVIATION_MIN_SCORE]
                if deviation_result is not None
                else []
            )
            await safe_send_json(
                websocket,
                {"type": "deviation_update", "deviations": [deviation_payload(doc) for doc in deviation_docs]},
                send_lock,
            )
            if deviation_result is not None:
                await safe_send_json(
                    websocket,
                    dev_log_payload(
                        "moss",
                        "deviation-query",
                        deviation_result.time_taken_ms,
                        f"{len(deviation_result.docs)} retrieved → {len(deviation_docs)} above {DEVIATION_MIN_SCORE}",
                    ),
                    send_lock,
                )

            rule_fields = extract_rule_fields(text)
            await safe_send_json(websocket, {"type": "extraction_update", "fields": {**rule_fields, **llm_state["fields"]}}, send_lock)
            llm_state["task"] = asyncio.create_task(run_llm_extraction(websocket, send_lock, text, rule_fields, llm_state))
    finally:
        if llm_state["task"] is not None:
            llm_state["task"].cancel()


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

    voice = {"caller": None, "dispatcher": None}

    async def handle_dispatcher_voice_transcript(full_text: str, is_final: bool):
        await safe_send_json(websocket, {"type": "dispatcher_voice_transcript", "text": full_text, "isFinal": is_final}, send_lock)

    async def handle_voice_transcript(full_text: str, is_final: bool):
        latest_transcript["text"] = full_text
        transcript_ready.set()
        await safe_send_json(websocket, {"type": "voice_transcript", "text": full_text}, send_lock)
        if is_final:
            await safe_send_json(websocket, dev_log_payload("asr", "final-phrase", None, f'"{full_text[-60:]}"'), send_lock)

    try:
        while True:
            frame = await websocket.receive()
            if frame["type"] == "websocket.disconnect":
                break
            if frame.get("bytes") is not None:
                # Binary frames carry no channel tag; the frontend runs only one mic at a time,
                # so they go to the dispatcher stream when open, otherwise the caller stream.
                active_stream = voice["dispatcher"] or voice["caller"]
                if active_stream is not None:
                    await active_stream.send_audio(frame["bytes"])
                continue
            msg = json.loads(frame["text"])

            if msg["type"] in ("voice_start", "voice_stop"):
                channel = msg.get("channel", "caller")
                if channel not in voice:
                    await safe_send_json(websocket, {"type": "voice_status", "state": "error", "reason": "unknown voice channel"}, send_lock)
                    continue
                status_extra = {"channel": "dispatcher"} if channel == "dispatcher" else {}

            if msg["type"] == "voice_start":
                on_transcript = handle_dispatcher_voice_transcript if channel == "dispatcher" else handle_voice_transcript
                stream = DeepgramStream(on_transcript)
                try:
                    await stream.start()
                except VoiceStreamUnavailable as exc:
                    await safe_send_json(websocket, {"type": "voice_status", "state": "unavailable", "reason": str(exc), **status_extra}, send_lock)
                    continue
                if voice[channel] is not None:
                    await voice[channel].stop()
                voice[channel] = stream
                await safe_send_json(websocket, {"type": "voice_status", "state": "listening", **status_extra}, send_lock)
                await safe_send_json(websocket, dev_log_payload("asr", "stream-open", None, "live speech-to-text connected"), send_lock)

            elif msg["type"] == "voice_stop":
                if voice[channel] is not None:
                    await voice[channel].stop()
                    voice[channel] = None
                await safe_send_json(websocket, {"type": "voice_status", "state": "stopped", **status_extra}, send_lock)

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
        for stream in voice.values():
            if stream is not None:
                await stream.stop()
        status_task.cancel()
        worker_task.cancel()


@app.get("/api/indexes")
async def list_indexes():
    try:
        indexes = await moss_client.list_indexes()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list indexes")

    return [
        {
            "name": index.name,
            "docCount": index.doc_count,
            "status": index.status,
            "model": index.model.id,
            "updatedAt": index.updated_at,
        }
        for index in indexes
    ]


@app.get("/api/indexes/{name}/docs")
async def get_index_docs(name: str):
    try:
        await moss_client.get_index(name)
    except RuntimeError:
        raise HTTPException(status_code=404, detail=f"Index '{name}' not found")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to look up index")

    try:
        docs = await moss_client.get_docs(name)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to retrieve index documents")

    return [{"id": doc.id, "text": doc.text, "metadata": doc.metadata} for doc in docs]


class AddDocRequest(BaseModel):
    id: str
    text: str
    metadata: Optional[dict[str, str]] = None

    @field_validator("id", "text")
    @classmethod
    def not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be a non-empty string")
        return value


class UpdateDocRequest(BaseModel):
    text: str
    metadata: Optional[dict[str, str]] = None

    @field_validator("text")
    @classmethod
    def not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be a non-empty string")
        return value


LIVE_LOADED_INDEXES = {PROTOCOL_INDEX_NAME, LIVE_DATA_INDEX_NAME, DEVIATION_INDEX_NAME}


async def _reload_if_live(name: str) -> None:
    """Refresh the in-memory copy of a live-loaded index after a mutation.

    The SDK's cloud-mutation path and local-query path are fully decoupled,
    so without this, edits would silently not appear in the live dispatch
    demo. The mutation itself already succeeded by the time this runs, so a
    reload failure here is logged and swallowed rather than surfaced as a
    request failure — the caller's write did go through.
    """
    if name not in LIVE_LOADED_INDEXES:
        return

    try:
        await moss_client.load_index(name)
    except Exception:
        logger.exception("Failed to reload live index '%s' after mutation", name)


@app.post("/api/indexes/{name}/docs")
async def add_index_doc(name: str, body: AddDocRequest):
    doc = DocumentInfo(id=body.id, text=body.text, metadata=body.metadata)

    try:
        await moss_client.add_docs(name, [doc])
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to add document")

    await _reload_if_live(name)

    return {"id": body.id}


@app.put("/api/indexes/{name}/docs/{doc_id}")
async def update_index_doc(name: str, doc_id: str, body: UpdateDocRequest):
    doc = DocumentInfo(id=doc_id, text=body.text, metadata=body.metadata)

    try:
        await moss_client.add_docs(name, [doc])
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to update document")

    await _reload_if_live(name)

    return {"id": doc_id}


@app.delete("/api/indexes/{name}/docs/{doc_id}", status_code=204)
async def delete_index_doc(name: str, doc_id: str):
    try:
        await moss_client.delete_docs(name, [doc_id])
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to delete document")

    await _reload_if_live(name)


class CallerSummary(BaseModel):
    whatHappened: Optional[str] = None

    model_config = {"extra": "allow"}


class JudgeDeviationRequest(BaseModel):
    dispatcherText: str = Field(max_length=2000)
    reason: Optional[str] = Field(default=None, max_length=500)
    protocolChunkId: str = Field(max_length=200)
    protocolChunkText: str = Field(max_length=4000)
    callerTranscript: str = Field(max_length=10000)
    callerSummary: Optional[CallerSummary] = None

    @field_validator("dispatcherText", "protocolChunkId", "protocolChunkText", "callerTranscript")
    @classmethod
    def not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be a non-empty string")
        return value


def deviation_caller_situation(body: JudgeDeviationRequest) -> str:
    transcript_tail = trailing_window(body.callerTranscript.strip(), WINDOW_WORDS)
    what_happened = (body.callerSummary.whatHappened or "").strip() if body.callerSummary else ""
    if not what_happened:
        return transcript_tail
    return f"{what_happened} {transcript_tail}"


async def save_deviation(doc: DocumentInfo) -> None:
    existing = await moss_client.list_indexes()
    if any(index.name == DEVIATION_INDEX_NAME for index in existing):
        await moss_client.add_docs(DEVIATION_INDEX_NAME, [doc])
    else:
        await moss_client.create_index(DEVIATION_INDEX_NAME, [doc])


@app.post("/api/deviations/judge")
async def judge_dispatcher_deviation(body: JudgeDeviationRequest):
    reason = (body.reason or "").strip()

    try:
        verdict = await judge_deviation(
            body.dispatcherText.strip(), reason or None, body.protocolChunkText, body.callerTranscript
        )
    except Exception:
        logger.exception("Deviation judge call failed")
        raise HTTPException(status_code=502, detail="Could not judge response")

    if verdict is None:
        raise HTTPException(status_code=503, detail="LLM not configured")

    if verdict["verdict"] == "followed":
        return {"verdict": "followed"}

    summary = verdict["deviationSummary"]
    doc_id = f"dev-{uuid.uuid4().hex}"
    doc = DocumentInfo(
        id=doc_id,
        text=f"{deviation_caller_situation(body)}\n{summary}",
        metadata={
            "type": "deviation",
            "callerTranscript": body.callerTranscript,
            "callerSummary": json.dumps(body.callerSummary.model_dump() if body.callerSummary else {}),
            "protocolChunkId": body.protocolChunkId,
            "protocolChunkText": body.protocolChunkText,
            "dispatcherTranscript": body.dispatcherText.strip(),
            "deviationSummary": summary,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "seed": "false",
        },
    )

    try:
        await save_deviation(doc)
    except Exception:
        logger.exception("Failed to save deviation")
        raise HTTPException(status_code=500, detail="Failed to save deviation")

    try:
        await moss_client.load_index(DEVIATION_INDEX_NAME)
        retrievable = True
    except Exception:
        logger.exception("Failed to reload deviation index after save")
        retrievable = False

    return {"verdict": "deviated", "deviationSummary": summary, "id": doc_id, "retrievable": retrievable}


def parse_caller_summary(raw: str | None) -> dict:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def deviation_record(doc) -> dict:
    metadata = doc.metadata or {}
    return {
        "id": doc.id,
        "timestamp": metadata.get("timestamp", ""),
        "callerTranscript": metadata.get("callerTranscript", ""),
        "callerSummary": parse_caller_summary(metadata.get("callerSummary")),
        "protocolChunkId": metadata.get("protocolChunkId", ""),
        "protocolChunkText": metadata.get("protocolChunkText", ""),
        "dispatcherTranscript": metadata.get("dispatcherTranscript", ""),
        "deviationSummary": metadata.get("deviationSummary", ""),
        "reason": metadata.get("reason", ""),
        "seed": metadata.get("seed") == "true",
    }


@app.get("/api/deviations")
async def list_deviations():
    try:
        await moss_client.get_index(DEVIATION_INDEX_NAME)
    except RuntimeError:
        return []
    except Exception:
        logger.exception("Failed to look up deviation index")
        raise HTTPException(status_code=500, detail="Failed to retrieve deviations")

    try:
        docs = await moss_client.get_docs(DEVIATION_INDEX_NAME)
    except Exception:
        logger.exception("Failed to retrieve deviations")
        raise HTTPException(status_code=500, detail="Failed to retrieve deviations")

    return sorted((deviation_record(doc) for doc in docs), key=lambda record: record["timestamp"], reverse=True)


STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
