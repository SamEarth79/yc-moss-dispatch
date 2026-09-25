"""E2E tests for the dispatcher mic on index.html (MOS-STORY-002-005).

Real Chromium against the shipped static files. Microphone path: Chromium's fake
media flags (--use-fake-ui-for-media-stream, --use-fake-device-for-media-stream) plus
a granted microphone permission, so the real getUserMedia / AudioContext / AudioWorklet
path in app.js runs (no JS override), except the denial test, which overrides
navigator.mediaDevices.getUserMedia to reject. The server is a stub /ws that records
client JSON messages and binary frame counts, auto-answers voice_start with a
configurable voice_status, and can push arbitrary messages. No Deepgram or real
microphone is involved.
"""

import asyncio
import json
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
FAKE_MEDIA_ARGS = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"]
BUSY_HINT = "Stop the caller mic or sample call to use the dispatcher mic"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class VoiceStub:
    def __init__(self):
        self.messages = []
        self.binary_frames = 0
        self.start_reply = {}  # channel -> voice_status override (e.g. unavailable)
        self.loop = None
        self.queues = []

    def push(self, message):
        for queue in list(self.queues):
            self.loop.call_soon_threadsafe(queue.put_nowait, message)

    def sent(self, message_type, channel=None):
        return [m for m in self.messages if m["type"] == message_type and m.get("channel") == channel]


def _build_app(stub: VoiceStub) -> FastAPI:
    app = FastAPI()

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        stub.loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        stub.queues.append(queue)

        async def handle_incoming():
            try:
                while True:
                    frame = await websocket.receive()
                    if frame["type"] == "websocket.disconnect":
                        return
                    if frame.get("bytes") is not None:
                        stub.binary_frames += 1
                        continue
                    message = json.loads(frame["text"])
                    stub.messages.append(message)
                    if message["type"] == "voice_start":
                        channel = message.get("channel")
                        base = {"channel": "dispatcher"} if channel == "dispatcher" else {}
                        reply = stub.start_reply.get(channel) or {"state": "listening"}
                        await websocket.send_json({"type": "voice_status", **reply, **base})
            except (WebSocketDisconnect, RuntimeError):
                pass

        receiver = asyncio.create_task(handle_incoming())
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
def voice_stub():
    return VoiceStub()


@pytest.fixture
def app_url(voice_stub):
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(_build_app(voice_stub), host="127.0.0.1", port=port, log_level="warning"))
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
def app_page(playwright, app_url):
    browser = playwright.chromium.launch(args=FAKE_MEDIA_ARGS)
    context = browser.new_context(permissions=["microphone"])
    page = context.new_page()
    page.route("**/fonts.googleapis.com/**", lambda route: route.abort())
    page.route("**/fonts.gstatic.com/**", lambda route: route.abort())
    page.goto(app_url)
    expect(page.locator("#statusText")).to_have_text("Connected")
    yield page
    browser.close()


def _wait_for(predicate, what):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for {what}")


def _start_dispatcher(page):
    page.click("#dispatcherMicButton")
    expect(page.locator("#dispatcherMicButton")).to_have_attribute("aria-pressed", "true")


def _push_chunk(stub, page):
    stub.push({"type": "protocol_update", "matchId": "c1", "matchText": "Give five back blows.", "priority": "P1", "suggestedAction": "none"})
    expect(page.locator("#instructionText")).to_contain_text("Give five back blows")


def test_dispatcher_mic_initial_accessible_state(app_page):
    button = app_page.get_by_role("button", name="Start dispatcher mic")
    expect(button).to_be_enabled()
    expect(button).to_have_attribute("aria-pressed", "false")
    expect(app_page.locator("#dispatcherVoiceStatus")).to_have_attribute("role", "status")


def test_start_sends_dispatcher_voice_start_and_shows_listening(app_page, voice_stub):
    _start_dispatcher(app_page)
    expect(app_page.locator("#dispatcherMicButton")).to_have_text("Stop dispatcher mic")
    expect(app_page.locator("#dispatcherVoiceStatus")).to_have_text("Listening…")
    assert voice_stub.sent("voice_start", "dispatcher") == [{"type": "voice_start", "channel": "dispatcher"}]
    assert voice_stub.sent("voice_start") == []
    _wait_for(lambda: voice_stub.binary_frames > 0, "PCM audio frames from the fake microphone")


def test_live_text_appends_after_existing_text_and_updates(app_page, voice_stub):
    app_page.fill("#dispatcherInput", "Existing reply.")
    _start_dispatcher(app_page)
    voice_stub.push({"type": "dispatcher_voice_transcript", "text": "give him", "isFinal": False})
    expect(app_page.locator("#dispatcherInput")).to_have_value("Existing reply. give him")
    voice_stub.push({"type": "dispatcher_voice_transcript", "text": "give him water", "isFinal": True})
    expect(app_page.locator("#dispatcherInput")).to_have_value("Existing reply. give him water")
    expect(app_page.locator("#transcriptInput")).to_have_value("")


def test_live_text_fills_empty_textarea_without_leading_space(app_page, voice_stub):
    _start_dispatcher(app_page)
    voice_stub.push({"type": "dispatcher_voice_transcript", "text": "hello there", "isFinal": True})
    expect(app_page.locator("#dispatcherInput")).to_have_value("hello there")


def test_stop_sends_dispatcher_voice_stop_and_restores_controls(app_page, voice_stub):
    _push_chunk(voice_stub, app_page)
    _start_dispatcher(app_page)
    voice_stub.push({"type": "dispatcher_voice_transcript", "text": "keep him calm", "isFinal": True})
    expect(app_page.locator("#dispatcherInput")).to_have_value("keep him calm")
    app_page.click("#dispatcherMicButton")
    expect(app_page.locator("#dispatcherMicButton")).to_have_attribute("aria-pressed", "false")
    expect(app_page.locator("#dispatcherMicButton")).to_have_text("Start dispatcher mic")
    assert voice_stub.sent("voice_stop", "dispatcher") == [{"type": "voice_stop", "channel": "dispatcher"}]
    for selector in ("#micButton", "#sampleButton", "#mockFollowsButton", "#mockDeviatesButton"):
        expect(app_page.locator(selector)).to_be_enabled()
    expect(app_page.locator("#dispatcherSubmit")).to_have_attribute("aria-disabled", "false")
    expect(app_page.locator("#dispatcherInput")).to_have_value("keep him calm")


def test_dispatcher_mic_listening_blocks_caller_mic_sample_mocks_and_submit(app_page, voice_stub):
    _push_chunk(voice_stub, app_page)
    app_page.fill("#dispatcherInput", "a reply")
    expect(app_page.locator("#dispatcherSubmit")).to_have_attribute("aria-disabled", "false")
    _start_dispatcher(app_page)
    for selector in ("#micButton", "#sampleButton", "#mockFollowsButton", "#mockDeviatesButton"):
        expect(app_page.locator(selector)).to_be_disabled()
    expect(app_page.locator("#dispatcherSubmit")).to_have_attribute("aria-disabled", "true")
    app_page.click("#dispatcherSubmit", force=True)
    app_page.wait_for_function("document.getElementById('dispatcherSubmit').textContent === 'Submit'")
    assert voice_stub.sent("voice_start") == []


def test_caller_mic_active_disables_dispatcher_mic_with_reason_then_restores(app_page, voice_stub):
    app_page.click("#micButton")
    expect(app_page.locator("#voiceStatus")).to_have_text("Listening…")
    dispatcher_button = app_page.locator("#dispatcherMicButton")
    expect(dispatcher_button).to_be_disabled()
    expect(dispatcher_button).to_have_attribute("title", BUSY_HINT)
    expect(app_page.locator("#dispatcherVoiceStatus")).to_have_text(BUSY_HINT)
    assert voice_stub.sent("voice_start", "dispatcher") == []
    app_page.click("#micButton")
    expect(dispatcher_button).to_be_enabled()
    expect(dispatcher_button).to_have_attribute("title", "")
    expect(app_page.locator("#dispatcherVoiceStatus")).to_have_text("")


def test_caller_mic_regression_start_stop_messages_and_status(app_page, voice_stub):
    app_page.click("#micButton")
    expect(app_page.locator("#voiceStatus")).to_have_text("Listening…")
    assert voice_stub.sent("voice_start") == [{"type": "voice_start"}]
    _wait_for(lambda: voice_stub.binary_frames > 0, "caller PCM frames")
    voice_stub.push({"type": "voice_transcript", "text": "my dad is choking"})
    expect(app_page.locator("#transcriptInput")).to_have_value("my dad is choking")
    expect(app_page.locator("#dispatcherInput")).to_have_value("")
    app_page.click("#micButton")
    expect(app_page.locator("#voiceStatus")).to_have_text("")
    assert voice_stub.sent("voice_stop") == [{"type": "voice_stop"}]
    expect(app_page.locator("#micButton")).to_be_enabled()
    expect(app_page.locator("#sampleButton")).to_be_enabled()


def test_denied_mic_error_only_in_dispatcher_status_line(app_page, voice_stub):
    app_page.evaluate(
        "() => { navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException('denied', 'NotAllowedError')); }"
    )
    app_page.click("#dispatcherMicButton")
    expect(app_page.locator("#dispatcherVoiceStatus")).to_have_text("Microphone access was denied")
    expect(app_page.locator("#dispatcherVoiceStatus")).to_have_class("voice-status error")
    expect(app_page.locator("#voiceStatus")).to_have_text("")
    expect(app_page.locator("#dispatcherMicButton")).to_have_attribute("aria-pressed", "false")
    expect(app_page.locator("#dispatcherMicButton")).to_be_enabled()
    expect(app_page.locator("#micButton")).to_be_enabled()
    assert voice_stub.sent("voice_start", "dispatcher") == []


def test_unavailable_status_shows_only_in_dispatcher_line_and_restores(app_page, voice_stub):
    voice_stub.start_reply["dispatcher"] = {"state": "unavailable", "reason": "Deepgram key missing"}
    app_page.click("#dispatcherMicButton")
    expect(app_page.locator("#dispatcherVoiceStatus")).to_have_text("Deepgram key missing")
    expect(app_page.locator("#voiceStatus")).to_have_text("")
    expect(app_page.locator("#dispatcherMicButton")).to_have_attribute("aria-pressed", "false")
    expect(app_page.locator("#dispatcherMicButton")).to_be_enabled()
    for selector in ("#micButton", "#sampleButton", "#mockFollowsButton", "#mockDeviatesButton"):
        expect(app_page.locator(selector)).to_be_enabled()


def test_caller_unavailable_status_stays_in_caller_line(app_page, voice_stub):
    voice_stub.start_reply[None] = {"state": "unavailable", "reason": "caller ASR down"}
    app_page.click("#micButton")
    expect(app_page.locator("#voiceStatus")).to_have_text("caller ASR down")
    expect(app_page.locator("#dispatcherVoiceStatus")).to_have_text("")
    expect(app_page.locator("#dispatcherMicButton")).to_be_enabled()
