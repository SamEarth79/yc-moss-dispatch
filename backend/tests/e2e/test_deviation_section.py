"""E2E tests for the Related Deviations subsection on index.html (MOS-STORY-002-006).

Real Chromium against the shipped static files. The server is a stub: /ws
accepts the socket and pushes protocol_update / deviation_update on demand.
No real Moss, LLM, or backend WebSocket logic is involved.
"""

import asyncio
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import expect

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"

CHUNK_TEXT = "Give five back blows, then five abdominal thrusts."
PLACEHOLDER = "Related deviations appear as the call develops…"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class WsStub:
    def __init__(self):
        self.loop = None
        self.queues = []

    def push(self, message):
        for queue in list(self.queues):
            self.loop.call_soon_threadsafe(queue.put_nowait, message)


def _build_app(stub: WsStub) -> FastAPI:
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

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


@pytest.fixture
def ws_stub():
    return WsStub()


@pytest.fixture
def app_url(ws_stub):
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(_build_app(ws_stub), host="127.0.0.1", port=port, log_level="warning"))
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


def _deviation(n=1, **overrides):
    base = {
        "id": f"dev-{n}",
        "summary": f"Gave water instead of back blows {n}.",
        "dispatcherTranscript": f"give him water {n}",
        "reason": f"he seemed thirsty {n}",
        "timestamp": "2026-09-25T12:00:00+00:00",
        "score": 0.8,
        "protocolChunkText": f"Give five back blows {n}.",
    }
    base.update(overrides)
    return base


def _push_deviations(stub, page, deviations):
    stub.push({"type": "deviation_update", "deviations": deviations})
    if deviations:
        expect(page.locator(".deviation-card")).to_have_count(min(len(deviations), 2))
    else:
        expect(page.locator("#deviationList .instruction-placeholder")).to_have_text(PLACEHOLDER)


def _push_chunk(stub, page, text=CHUNK_TEXT, priority="P1"):
    stub.push({"type": "protocol_update", "matchId": "choking-1", "matchText": text, "priority": priority, "suggestedAction": "none"})
    expect(page.locator("#instructionText")).to_contain_text(text.split(",")[0])


def test_section_sits_between_instruction_text_and_action_row(app_page):
    page = app_page
    order = page.evaluate(
        """() => {
            const panel = document.querySelector('.instruction-panel');
            const kids = [...panel.children].map(c => c.id);
            return kids;
        }"""
    )
    assert order.index("instructionText") < order.index("deviationSection") < order.index("actionRow")


def test_heading_tag_and_unreviewed_label_and_initial_placeholder(app_page):
    page = app_page
    heading = page.locator("#deviationHeading")
    expect(heading).to_contain_text("Related Deviations")
    expect(heading.locator(".source-tag--moss")).to_have_text("Moss retrieved")
    expect(heading.locator(".deviation-unreviewed")).to_have_text("unreviewed")
    expect(page.locator("#deviationList .instruction-placeholder")).to_have_text(PLACEHOLDER)
    expect(page.locator(".deviation-card")).to_have_count(0)


def test_section_is_labelled_region_and_not_aria_live(app_page, ws_stub):
    page = app_page
    section = page.locator("#deviationSection")
    expect(section).to_have_attribute("aria-labelledby", "deviationHeading")
    _push_deviations(ws_stub, page, [_deviation(1)])
    has_live = page.evaluate(
        """() => {
            const s = document.getElementById('deviationSection');
            return s.hasAttribute('aria-live') || s.querySelector('[aria-live]') !== null
                || s.closest('[aria-live]') !== null;
        }"""
    )
    assert has_live is False
    expect(page.get_by_role("region", name="Related Deviations")).to_have_count(1)


@pytest.mark.parametrize("count", [1, 2])
def test_renders_cards_with_full_structure(app_page, ws_stub, count):
    page = app_page
    _push_deviations(ws_stub, page, [_deviation(i + 1) for i in range(count)])
    expect(page.locator("#deviationList .instruction-placeholder")).to_have_count(0)
    card = page.locator(".deviation-card").first
    expect(card.locator(".incident-card-header .deviation-summary")).to_have_text("Gave water instead of back blows 1.")
    expect(card.locator(".incident-card-header .incident-date")).to_have_text("Sep 25, 2026")
    lines = card.locator(".deviation-line")
    expect(lines).to_have_count(3)
    expect(lines.nth(0).locator(".deviation-line-label")).to_have_text("Protocol said:")
    expect(lines.nth(0)).to_contain_text("Give five back blows 1.")
    expect(lines.nth(1).locator(".deviation-line-label")).to_have_text("Dispatcher said:")
    expect(lines.nth(1)).to_contain_text("give him water 1")
    expect(lines.nth(2)).to_have_class("deviation-line deviation-reason")
    expect(lines.nth(2)).to_have_text("Reason: he seemed thirsty 1")


def test_more_than_two_deviations_shows_only_two(app_page, ws_stub):
    page = app_page
    ws_stub.push({"type": "deviation_update", "deviations": [_deviation(i) for i in (1, 2, 3)]})
    expect(page.locator(".deviation-card")).to_have_count(2)


def test_empty_list_shows_placeholder_and_later_empty_update_clears_cards(app_page, ws_stub):
    page = app_page
    _push_deviations(ws_stub, page, [_deviation(1), _deviation(2)])
    _push_deviations(ws_stub, page, [])
    expect(page.locator(".deviation-card")).to_have_count(0)
    expect(page.locator("#deviationList .instruction-placeholder")).to_have_text(PLACEHOLDER)


def test_reason_line_only_when_present(app_page, ws_stub):
    page = app_page
    _push_deviations(ws_stub, page, [_deviation(1, reason=""), _deviation(2)])
    cards = page.locator(".deviation-card")
    expect(cards.nth(0).locator(".deviation-line")).to_have_count(2)
    expect(cards.nth(0).locator(".deviation-reason")).to_have_count(0)
    expect(cards.nth(1).locator(".deviation-reason")).to_have_count(1)


def test_neutral_wording(app_page, ws_stub):
    page = app_page
    _push_deviations(ws_stub, page, [_deviation(1)])
    text = page.locator("#deviationSection").inner_text().lower()
    assert "wrong" not in text
    assert "violation" not in text


def test_clamp_css_and_full_text_in_title(app_page, ws_stub):
    page = app_page
    long_summary = "S" + " summary words" * 60
    long_protocol = "P" + " protocol words" * 60
    long_dispatcher = "D" + " dispatcher words" * 60
    long_reason = "R" + " reason words" * 60
    _push_deviations(
        ws_stub,
        page,
        [_deviation(1, summary=long_summary, protocolChunkText=long_protocol, dispatcherTranscript=long_dispatcher, reason=long_reason)],
    )
    card = page.locator(".deviation-card")
    summary = card.locator(".deviation-summary")
    expect(summary).to_have_attribute("title", long_summary)
    expect(summary).to_have_css("-webkit-line-clamp", "2")
    expect(summary).to_have_css("overflow", "hidden")
    lines = card.locator(".deviation-line")
    for index, full in enumerate([long_protocol, long_dispatcher, long_reason]):
        line = lines.nth(index)
        expect(line).to_have_attribute("title", full)
        expect(line).to_have_css("-webkit-line-clamp", "2")
        expect(line).to_have_css("overflow", "hidden")
    line_height_ok = page.evaluate(
        """() => { const el = document.querySelector('.deviation-line'); return el.scrollHeight > el.clientHeight; }"""
    )
    assert line_height_ok is True


def test_very_long_unbroken_string_does_not_overflow_panel(app_page, ws_stub):
    page = app_page
    blob = "x" * 600
    _push_deviations(
        ws_stub,
        page,
        [_deviation(1, summary=blob, protocolChunkText=blob, dispatcherTranscript=blob, reason=blob)],
    )
    overflow = page.evaluate(
        """() => {
            const panel = document.querySelector('.instruction-panel').getBoundingClientRect();
            return [...document.querySelectorAll('.deviation-card, .deviation-card *')].filter(el => {
                const r = el.getBoundingClientRect();
                return r.right > panel.right + 1 || r.left < panel.left - 1;
            }).length;
        }"""
    )
    assert overflow == 0
    assert page.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth")


@pytest.mark.parametrize("timestamp", ["not-a-date", "", None])
def test_invalid_or_empty_timestamp_renders_empty_date(app_page, ws_stub, timestamp):
    page = app_page
    _push_deviations(ws_stub, page, [_deviation(1, timestamp=timestamp)])
    expect(page.locator(".deviation-card .incident-date")).to_have_text("")
    expect(page.locator(".deviation-card")).to_contain_text("Gave water instead of back blows 1.")
    expect(page.locator(".deviation-card")).not_to_contain_text("Invalid Date")


def test_missing_timestamp_key_renders_empty_date(app_page, ws_stub):
    page = app_page
    item = _deviation(1)
    del item["timestamp"]
    _push_deviations(ws_stub, page, [item])
    expect(page.locator(".deviation-card .incident-date")).to_have_text("")


def test_deviation_update_before_and_after_protocol_update_leaves_chunk_untouched(app_page, ws_stub):
    page = app_page
    _push_deviations(ws_stub, page, [_deviation(1)])
    expect(page.locator("#priorityBadge")).to_have_text("—")
    _push_chunk(ws_stub, page)
    expect(page.locator("#priorityBadge")).to_contain_text("P1")
    before = page.locator("#instructionText").inner_text()
    expect(page.locator("#instructionText")).to_contain_text(CHUNK_TEXT)
    expect(page.locator(".deviation-card")).to_have_count(1)

    _push_deviations(ws_stub, page, [_deviation(2), _deviation(3)])
    assert page.locator("#instructionText").inner_text() == before
    expect(page.locator("#priorityBadge")).to_contain_text("P1")
    _push_deviations(ws_stub, page, [])
    assert page.locator("#instructionText").inner_text() == before
    expect(page.locator("#instructionText")).not_to_contain_text("water")
    expect(page.locator("#deviationSection")).to_be_visible()


def test_protocol_update_does_not_clear_or_reorder_cards(app_page, ws_stub):
    page = app_page
    _push_deviations(ws_stub, page, [_deviation(1), _deviation(2)])
    _push_chunk(ws_stub, page, "Apply direct pressure to the wound.", priority="P2")
    summaries = page.locator(".deviation-card .deviation-summary")
    expect(summaries).to_have_text(["Gave water instead of back blows 1.", "Gave water instead of back blows 2."])


def test_caller_change_resets_to_placeholder(app_page, ws_stub):
    page = app_page
    _push_deviations(ws_stub, page, [_deviation(1)])
    page.select_option("#callerSelect", "42 Oak Street")
    expect(page.locator(".deviation-card")).to_have_count(0)
    expect(page.locator("#deviationList .instruction-placeholder")).to_have_text(PLACEHOLDER)


def test_clearing_transcript_resets_but_typing_does_not(app_page, ws_stub):
    page = app_page
    page.fill("#transcriptInput", "my dad is choking")
    _push_deviations(ws_stub, page, [_deviation(1)])
    page.locator("#transcriptInput").press_sequentially("!")
    expect(page.locator(".deviation-card")).to_have_count(1)
    page.fill("#transcriptInput", "   ")
    expect(page.locator(".deviation-card")).to_have_count(0)
    expect(page.locator("#deviationList .instruction-placeholder")).to_have_text(PLACEHOLDER)


def test_html_in_fields_renders_as_text_not_markup(app_page, ws_stub):
    page = app_page
    payload = '<img src=x onerror="window.__pwned=1">'
    _push_deviations(
        ws_stub,
        page,
        [_deviation(1, summary=payload, protocolChunkText=payload, dispatcherTranscript=payload, reason=payload)],
    )
    expect(page.locator(".deviation-summary")).to_have_text(payload)
    expect(page.locator("#deviationList img")).to_have_count(0)
    expect(page.locator(".deviation-reason")).to_have_text(f"Reason: {payload}")
    assert page.evaluate("() => window.__pwned === undefined")
