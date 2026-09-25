"""E2E tests for Jev calls in the developer feed (MOS-STORY-003-006).

Real Chromium against the shipped static files. The server is a stub: /ws pushes
messages on demand and POST /api/deviations/judge returns a configured response
(including devLog). No real LLM, Jev, Moss, or WebSocket backend is involved.
"""

import asyncio
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import expect

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
CHUNK_TEXT = "Give five back blows, then five abdominal thrusts."

JEV_ENTRY = {"service": "jev", "callType": "verdict", "latencyMs": 312, "summary": "P(follows)=0.87 → followed"}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Stub:
    def __init__(self):
        self.status = 200
        self.result = {"verdict": "followed", "devLog": [JEV_ENTRY]}
        self.loop = None
        self.queues = []

    def push(self, message):
        for queue in list(self.queues):
            self.loop.call_soon_threadsafe(queue.put_nowait, message)


def _build_app(stub: Stub) -> FastAPI:
    app = FastAPI()

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        stub.loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        stub.queues.append(queue)

        async def drain_incoming():
            try:
                while True:
                    await websocket.receive()
            except (WebSocketDisconnect, RuntimeError):
                pass

        receiver = asyncio.create_task(drain_incoming())
        try:
            while not receiver.done():
                getter = asyncio.create_task(queue.get())
                done, _ = await asyncio.wait({getter, receiver}, return_when=asyncio.FIRST_COMPLETED)
                if getter in done:
                    await websocket.send_json(getter.result())
                else:
                    getter.cancel()
        except Exception:
            pass
        finally:
            stub.queues.remove(queue)
            receiver.cancel()

    @app.post("/api/deviations/judge")
    async def judge(request: Request):
        await request.json()
        return JSONResponse(stub.result, status_code=stub.status)

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


@pytest.fixture
def stub():
    return Stub()


@pytest.fixture
def app_url(stub):
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(_build_app(stub), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("stub server failed to start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def app_page(page, app_url):
    page.route("**/fonts.googleapis.com/**", lambda route: route.abort())
    page.route("**/fonts.gstatic.com/**", lambda route: route.abort())
    page.goto(app_url)
    expect(page.locator("#statusText")).to_have_text("Connected")
    return page


def _submit(stub, page):
    stub.push({"type": "protocol_update", "matchId": "choking-1", "matchText": CHUNK_TEXT, "priority": "P1", "suggestedAction": "none"})
    expect(page.locator("#instructionText")).to_contain_text("Give five back blows")
    page.fill("#dispatcherInput", "give him water")
    expect(page.locator("#dispatcherSubmit")).to_have_attribute("aria-disabled", "false")
    page.click("#dispatcherSubmit")
    expect(page.locator(".verdict-card")).to_be_visible()


def _entries(page):
    return page.locator("#devFeed .dev-log-entry")


def test_jev_entry_appears_after_submit(app_page, stub):
    page = app_page
    _submit(stub, page)
    entry = _entries(page)
    expect(entry).to_have_count(1)
    expect(entry).to_have_class("dev-log-entry dev-log-entry--jev")
    expect(entry.locator(".dev-log-service")).to_have_text("jev")
    expect(entry.locator(".dev-log-service")).to_have_class("dev-log-service dev-log-service--jev")
    expect(entry.locator(".dev-log-type")).to_have_text("verdict")
    expect(entry.locator(".dev-log-latency")).to_have_text("312ms")
    expect(entry.locator(".dev-log-summary")).to_have_text("P(follows)=0.87 → followed")


def test_null_latency_renders_dash(app_page, stub):
    page = app_page
    stub.result = {"verdict": "followed", "devLog": [{**JEV_ENTRY, "latencyMs": None}]}
    _submit(stub, page)
    expect(_entries(page).locator(".dev-log-latency")).to_have_text("—")


def test_multiple_entries_newest_first(app_page, stub):
    page = app_page
    stub.result = {
        "verdict": "followed",
        "devLog": [
            {**JEV_ENTRY, "summary": "first"},
            {**JEV_ENTRY, "summary": "second"},
            {**JEV_ENTRY, "summary": "third"},
        ],
    }
    _submit(stub, page)
    expect(_entries(page).locator(".dev-log-summary")).to_have_text(["third", "second", "first"])


def test_deviated_response_also_renders_entry(app_page, stub):
    page = app_page
    stub.result = {
        "verdict": "deviated",
        "deviationSummary": "Gave water.",
        "id": "dev-1",
        "retrievable": True,
        "devLog": [{**JEV_ENTRY, "summary": "P(follows)=0.12 → deviated"}],
    }
    _submit(stub, page)
    expect(_entries(page).locator(".dev-log-summary")).to_have_text(["P(follows)=0.12 → deviated"])


@pytest.mark.parametrize("status", [503, 502, 500])
def test_error_responses_add_nothing(app_page, stub, status):
    page = app_page
    stub.status = status
    stub.result = {"detail": "boom", "devLog": [JEV_ENTRY]}
    _submit(stub, page)
    expect(page.locator(".verdict-card--error")).to_be_visible()
    expect(_entries(page)).to_have_count(0)


def test_missing_or_non_array_devlog_adds_nothing(app_page, stub):
    page = app_page
    stub.result = {"verdict": "followed"}
    _submit(stub, page)
    expect(_entries(page)).to_have_count(0)
    stub.result = {"verdict": "followed", "devLog": "nope"}
    page.fill("#dispatcherInput", "again")
    page.click("#dispatcherSubmit")
    expect(page.locator(".verdict-card--followed")).to_be_visible()
    expect(_entries(page)).to_have_count(0)


def test_invalid_entries_skipped_without_breaking(app_page, stub):
    page = app_page
    stub.result = {
        "verdict": "followed",
        "devLog": [
            {"service": "jev", "callType": "verdict", "latencyMs": 1},
            {"callType": "verdict", "latencyMs": 1, "summary": "no service"},
            {"service": 5, "callType": "verdict", "latencyMs": 1, "summary": "num service"},
            {"service": "jev", "callType": None, "latencyMs": 1, "summary": "null type"},
            {"service": "jev", "callType": "verdict", "latencyMs": "12", "summary": "string latency"},
            {"service": "jev", "callType": "verdict", "latencyMs": 1, "summary": {"a": 1}},
            None,
            "text",
            42,
            {**JEV_ENTRY, "summary": "valid one"},
        ],
    }
    _submit(stub, page)
    expect(_entries(page)).to_have_count(1)
    expect(_entries(page).locator(".dev-log-summary")).to_have_text("valid one")


def test_html_in_entry_fields_renders_as_text(app_page, stub):
    page = app_page
    payload = "<img src=x onerror=alert(1)>"
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    stub.result = {
        "verdict": "followed",
        "devLog": [{"service": "jev", "callType": payload, "latencyMs": 5, "summary": payload}],
    }
    _submit(stub, page)
    entry = _entries(page)
    expect(entry.locator(".dev-log-summary")).to_have_text(payload)
    expect(entry.locator(".dev-log-type")).to_have_text(payload)
    expect(page.locator("#devFeed img")).to_have_count(0)
    page.wait_for_timeout(200)
    assert dialogs == []


def test_service_class_suffix_is_sanitized(app_page, stub):
    page = app_page
    stub.result = {
        "verdict": "followed",
        "devLog": [{**JEV_ENTRY, "service": 'JEV<x> onclick="1"'}],
    }
    _submit(stub, page)
    entry = _entries(page)
    expect(entry).to_have_count(1)
    expect(entry).to_have_class("dev-log-entry dev-log-entry--jevxonclick1")
    expect(entry.locator(".dev-log-service")).to_have_class("dev-log-service dev-log-service--jevxonclick1")
    expect(entry.locator(".dev-log-service")).to_have_text('JEV<x> onclick="1"')
    assert entry.locator("*").count() == 5
    assert entry.get_attribute("onclick") is None
    expect(page.locator("#devFeed x")).to_have_count(0)


@pytest.mark.parametrize("service", ["moss", "llm", "asr", "jev"])
def test_ws_dev_log_entries_render_with_same_markup(app_page, stub, service):
    page = app_page
    stub.push({"type": "dev_log", "service": service, "callType": "search", "latencyMs": 42.5, "summary": "hello <b>x</b>"})
    entry = _entries(page)
    expect(entry).to_have_count(1)
    expect(entry).to_have_class(f"dev-log-entry dev-log-entry--{service}")
    spans = entry.locator("> span")
    expect(spans).to_have_count(5)
    expect(spans.nth(0)).to_have_class("dev-log-time")
    expect(spans.nth(1)).to_have_class(f"dev-log-service dev-log-service--{service}")
    expect(spans.nth(1)).to_have_text(service)
    expect(spans.nth(2)).to_have_class("dev-log-type")
    expect(spans.nth(2)).to_have_text("search")
    expect(spans.nth(3)).to_have_class("dev-log-latency")
    expect(spans.nth(3)).to_have_text("42.5ms")
    expect(spans.nth(4)).to_have_class("dev-log-summary")
    expect(spans.nth(4)).to_have_text("hello <b>x</b>")
    expect(page.locator("#devFeed b")).to_have_count(0)


def test_jev_label_has_lavender_styling_matching_source_tag(app_page, stub):
    page = app_page
    stub.push({"type": "dev_log", "service": "jev", "callType": "verdict", "latencyMs": 1, "summary": "s"})
    stub.push({"type": "dev_log", "service": "other", "callType": "verdict", "latencyMs": 1, "summary": "s"})
    expect(_entries(page)).to_have_count(2)
    jev = page.locator(".dev-log-service--jev")
    neutral = page.locator(".dev-log-service--other")
    read = "el => { const s = getComputedStyle(el); return [s.color, s.backgroundColor]; }"
    jev_style = jev.evaluate(read)
    neutral_style = neutral.evaluate(read)
    assert jev_style != neutral_style
    assert jev_style[0] != neutral_style[0] and jev_style[1] != neutral_style[1]
    tag_style = page.evaluate(
        """() => {
            const el = document.createElement('span');
            el.className = 'source-tag--jev';
            document.body.append(el);
            const s = getComputedStyle(el);
            const out = [s.color, s.backgroundColor];
            el.remove();
            return out;
        }"""
    )
    assert jev_style == tag_style
    lavender = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--color-lavender').trim()")
    probe = page.evaluate(
        """(v) => { const el = document.createElement('span'); el.style.color = v; document.body.append(el);
                   const c = getComputedStyle(el).color; el.remove(); return c; }""",
        lavender,
    )
    assert jev_style[0] == probe
    latency_color = page.locator(".dev-log-entry--jev .dev-log-latency").evaluate("el => getComputedStyle(el).color")
    assert latency_color == probe


def test_feed_trims_to_max_entries_with_jev_entries(app_page, stub):
    page = app_page
    stub.result = {"verdict": "followed", "devLog": [{**JEV_ENTRY, "summary": f"entry-{i}"} for i in range(45)]}
    _submit(stub, page)
    expect(_entries(page)).to_have_count(40)
    summaries = _entries(page).locator(".dev-log-summary")
    expect(summaries.first).to_have_text("entry-44")
    expect(summaries.last).to_have_text("entry-5")
    for i in range(3):
        stub.push({"type": "dev_log", "service": "moss", "callType": "search", "latencyMs": 1, "summary": f"ws-{i}"})
    expect(summaries.first).to_have_text("ws-2")
    expect(_entries(page)).to_have_count(40)
