"""E2E tests for the dispatcher panel + verdict card on index.html (MOS-STORY-002-004).

Real Chromium against the shipped static files. The server is a stub: /ws
accepts the socket and pushes protocol_update on demand, and
POST /api/deviations/judge records its body and returns a configured response.
No real LLM, Moss, or WebSocket backend is involved.
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

CHUNK_ID = "choking-1"
CHUNK_TEXT = "Give five back blows, then five abdominal thrusts."


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class JudgeStub:
    def __init__(self):
        self.status = 200
        self.result = {"verdict": "followed", "deviationSummary": "", "retrievable": True}
        self.requests = []
        self.hold = None  # threading.Event; when set, response waits for it
        self.loop = None
        self.queues = []

    def push(self, message):
        for queue in list(self.queues):
            self.loop.call_soon_threadsafe(queue.put_nowait, message)


def _build_app(stub: JudgeStub) -> FastAPI:
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
        stub.requests.append(await request.json())
        if stub.hold is not None:
            await asyncio.to_thread(stub.hold.wait)
        return JSONResponse(stub.result, status_code=stub.status)

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


@pytest.fixture
def judge_stub():
    return JudgeStub()


@pytest.fixture
def app_url(judge_stub):
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(_build_app(judge_stub), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("stub server failed to start")
    yield f"http://127.0.0.1:{port}"
    if judge_stub.hold is not None:
        judge_stub.hold.set()
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def app_page(page, app_url):
    page.route("**/fonts.googleapis.com/**", lambda route: route.abort())
    page.route("**/fonts.gstatic.com/**", lambda route: route.abort())
    page.goto(app_url)
    expect(page.locator("#statusText")).to_have_text("Connected")
    return page


def _push_chunk(stub, page, chunk_id=CHUNK_ID, text=CHUNK_TEXT):
    stub.push({"type": "protocol_update", "matchId": chunk_id, "matchText": text, "priority": "P1", "suggestedAction": "none"})
    expect(page.locator("#instructionText")).to_contain_text(text.split(",")[0])


def _ready(stub, page, text="give him water"):
    _push_chunk(stub, page)
    page.fill("#dispatcherInput", text)
    expect(page.locator("#dispatcherSubmit")).to_have_attribute("aria-disabled", "false")


def test_panel_renders_with_labelled_controls(app_page):
    page = app_page
    expect(page.get_by_role("heading", name="Dispatcher Transcript")).to_be_visible()
    expect(page.get_by_label("Dispatcher reply")).to_be_visible()
    expect(page.get_by_label("Reason for deviating (optional)")).to_be_visible()
    expect(page.get_by_role("button", name="Demo: simulate reply that follows protocol")).to_be_visible()
    expect(page.get_by_role("button", name="Demo: simulate reply that deviates")).to_be_visible()
    expect(page.get_by_role("button", name="Submit")).to_be_visible()
    expect(page.locator("#mockFollowsButton")).to_have_attribute("aria-pressed", "false")


def test_mock_buttons_fill_without_submitting_and_typing_clears_selection(app_page, judge_stub):
    page = app_page
    _push_chunk(judge_stub, page)
    page.fill("#dispatcherInput", "old text")
    page.click("#mockFollowsButton")
    follows_text = page.input_value("#dispatcherInput")
    assert follows_text and follows_text != "old text"
    expect(page.locator("#mockFollowsButton")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#mockDeviatesButton")).to_have_attribute("aria-pressed", "false")

    page.click("#mockDeviatesButton")
    assert page.input_value("#dispatcherInput") != follows_text
    expect(page.locator("#mockDeviatesButton")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#mockFollowsButton")).to_have_attribute("aria-pressed", "false")

    page.locator("#dispatcherInput").press_sequentially("!")
    expect(page.locator("#mockDeviatesButton")).to_have_attribute("aria-pressed", "false")
    assert judge_stub.requests == []
    expect(page.locator(".verdict-card")).to_have_count(0)


def test_submit_disabled_with_no_chunk_shows_helper(app_page):
    page = app_page
    expect(page.locator("#dispatcherHelper")).to_be_visible()
    expect(page.locator("#dispatcherHelper")).to_have_text("Waiting for a protocol match…")
    page.fill("#dispatcherInput", "some reply")
    expect(page.locator("#dispatcherSubmit")).to_have_attribute("aria-disabled", "true")


def test_submit_disabled_with_empty_or_blank_text_and_helper_hides_with_chunk(app_page, judge_stub):
    page = app_page
    _push_chunk(judge_stub, page)
    expect(page.locator("#dispatcherHelper")).to_be_hidden()
    expect(page.locator("#dispatcherSubmit")).to_have_attribute("aria-disabled", "true")
    page.fill("#dispatcherInput", "   ")
    expect(page.locator("#dispatcherSubmit")).to_have_attribute("aria-disabled", "true")
    page.click("#dispatcherSubmit", force=True)
    page.fill("#dispatcherInput", "real reply")
    expect(page.locator("#dispatcherSubmit")).to_have_attribute("aria-disabled", "false")
    assert judge_stub.requests == []


def test_in_flight_state_and_double_click_sends_one_request(app_page, judge_stub):
    page = app_page
    judge_stub.hold = threading.Event()
    _ready(judge_stub, page)
    page.click("#dispatcherSubmit")
    expect(page.locator("#dispatcherSubmit")).to_have_text("Checking…")
    expect(page.locator("#dispatcherSubmit")).to_have_attribute("aria-disabled", "true")
    page.click("#dispatcherSubmit", force=True)
    page.locator("#dispatcherInput").press("Control+Enter")
    judge_stub.hold.set()
    expect(page.locator(".verdict-card")).to_be_visible()
    expect(page.locator("#dispatcherSubmit")).to_have_text("Submit")
    assert len(judge_stub.requests) == 1


def test_request_body_uses_chunk_snapshotted_at_click_time(app_page, judge_stub):
    page = app_page
    judge_stub.hold = threading.Event()
    page.fill("#transcriptInput", "my dad is choking")
    _ready(judge_stub, page, "  give him water  ")
    page.fill("#dispatcherReason", "he seemed thirsty")
    page.click("#dispatcherSubmit")
    expect(page.locator("#dispatcherSubmit")).to_have_text("Checking…")
    _push_chunk(judge_stub, page, "bleeding-2", "Apply direct pressure to the wound.")
    judge_stub.hold.set()
    expect(page.locator(".verdict-card")).to_be_visible()

    body = judge_stub.requests[0]
    assert body["protocolChunkId"] == CHUNK_ID
    assert body["protocolChunkText"] == CHUNK_TEXT
    assert body["dispatcherText"] == "give him water"
    assert body["callerTranscript"] == "my dad is choking"
    assert body["reason"] == "he seemed thirsty"
    expect(page.locator(".verdict-card code")).to_have_text(CHUNK_ID)


def test_reason_omitted_from_body_when_empty(app_page, judge_stub):
    page = app_page
    _ready(judge_stub, page)
    page.fill("#dispatcherReason", "   ")
    page.click("#dispatcherSubmit")
    expect(page.locator(".verdict-card")).to_be_visible()
    assert "reason" not in judge_stub.requests[0]


def test_followed_card_and_inputs_cleared(app_page, judge_stub):
    page = app_page
    _ready(judge_stub, page, "back blows then thrusts")
    page.fill("#dispatcherReason", "r")
    page.click("#mockFollowsButton")
    page.click("#dispatcherSubmit")
    card = page.locator(".verdict-card")
    expect(card).to_have_class("verdict-card verdict-card--followed")
    expect(card).to_have_attribute("role", "status")
    expect(card).to_contain_text("Followed protocol")
    expect(card).to_contain_text(CHUNK_ID)
    expect(card).to_contain_text("Submitted: ")
    expect(card.locator(".source-tag--llm")).to_have_count(0)
    expect(page.locator("#dispatcherInput")).to_have_value("")
    expect(page.locator("#dispatcherReason")).to_have_value("")
    expect(page.locator("#mockFollowsButton")).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#dispatcherSubmit")).to_have_attribute("aria-disabled", "true")


def test_deviated_card_shows_summary_tag_and_saved_line(app_page, judge_stub):
    page = app_page
    judge_stub.result = {"verdict": "deviated", "deviationSummary": "Gave water instead of back blows.", "retrievable": True}
    _ready(judge_stub, page, "give him water")
    page.click("#dispatcherSubmit")
    card = page.locator(".verdict-card")
    expect(card).to_have_class("verdict-card verdict-card--deviated")
    expect(card).to_have_attribute("role", "status")
    expect(card).to_contain_text("Deviated")
    expect(card).to_contain_text("Gave water instead of back blows.")
    expect(card.locator(".source-tag--llm")).to_have_text("LLM generated")
    expect(card).to_contain_text("Saved to deviation index")
    expect(card.locator(".verdict-warning")).to_have_count(0)
    expect(page.locator("#dispatcherInput")).to_have_value("")


def test_deviated_not_retrievable_shows_warning(app_page, judge_stub):
    page = app_page
    judge_stub.result = {"verdict": "deviated", "deviationSummary": "Wrong step.", "retrievable": False}
    _ready(judge_stub, page)
    page.click("#dispatcherSubmit")
    card = page.locator(".verdict-card--deviated")
    expect(card.locator(".verdict-warning")).to_have_text("Saved, but not retrievable for future calls.")
    expect(card).not_to_contain_text("Saved to deviation index")


@pytest.mark.parametrize(
    "status,copy",
    [
        (503, "Reply check is not configured."),
        (502, "Couldn't check this reply. Try again."),
        (500, "Couldn't check this reply. Try again."),
    ],
)
def test_error_cards_preserve_inputs_and_reenable_submit(app_page, judge_stub, status, copy):
    page = app_page
    judge_stub.status = status
    judge_stub.result = {"detail": "boom"}
    _ready(judge_stub, page, "give him water")
    page.fill("#dispatcherReason", "thirsty")
    page.click("#dispatcherSubmit")
    card = page.locator(".verdict-card")
    expect(card).to_have_class("verdict-card verdict-card--error")
    expect(card).to_have_attribute("role", "alert")
    expect(card).to_have_text(copy)
    expect(page.locator("#dispatcherInput")).to_have_value("give him water")
    expect(page.locator("#dispatcherReason")).to_have_value("thirsty")
    expect(page.locator("#dispatcherSubmit")).to_have_attribute("aria-disabled", "false")
    expect(page.locator("#dispatcherSubmit")).to_have_text("Submit")


def test_ctrl_enter_submits(app_page, judge_stub):
    page = app_page
    _ready(judge_stub, page)
    page.locator("#dispatcherInput").press("Control+Enter")
    expect(page.locator(".verdict-card")).to_be_visible()
    assert len(judge_stub.requests) == 1


def test_plain_enter_does_not_submit(app_page, judge_stub):
    page = app_page
    _ready(judge_stub, page)
    page.locator("#dispatcherInput").press("Enter")
    expect(page.locator("#dispatcherSubmit")).to_have_attribute("aria-disabled", "false")
    assert judge_stub.requests == []


def test_caller_change_clears_inputs_and_card(app_page, judge_stub):
    page = app_page
    _ready(judge_stub, page)
    page.click("#dispatcherSubmit")
    expect(page.locator(".verdict-card")).to_be_visible()
    page.click("#mockDeviatesButton")
    page.fill("#dispatcherReason", "why")
    page.select_option("#callerSelect", "42 Oak Street")
    expect(page.locator(".verdict-card")).to_have_count(0)
    expect(page.locator("#dispatcherInput")).to_have_value("")
    expect(page.locator("#dispatcherReason")).to_have_value("")
    expect(page.locator("#mockDeviatesButton")).to_have_attribute("aria-pressed", "false")


def test_card_persists_until_next_submit_then_is_replaced(app_page, judge_stub):
    page = app_page
    _ready(judge_stub, page)
    page.click("#dispatcherSubmit")
    expect(page.locator(".verdict-card--followed")).to_be_visible()
    page.fill("#dispatcherInput", "next reply")
    _push_chunk(judge_stub, page, "bleeding-2", "Apply direct pressure to the wound.")
    expect(page.locator(".verdict-card--followed")).to_be_visible()

    judge_stub.result = {"verdict": "deviated", "deviationSummary": "Different.", "retrievable": True}
    page.click("#dispatcherSubmit")
    expect(page.locator(".verdict-card--deviated")).to_be_visible()
    expect(page.locator(".verdict-card")).to_have_count(1)
