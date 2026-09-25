"""E2E tests for the Jev tag, row cues and status in the summary panel (MOS-STORY-003-005).

Real Chromium against the shipped static files. The server is a stub: /ws
accepts the socket, pushes extraction_update on demand and records set_caller.
No real Moss, LLM, or Jev is involved.
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
JEV_LABEL = "Some values refined by Jev decision model"
ROW_LABELS = ["What", "Where", "Department", "Patients", "Weapons", "Conscious"]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class WsStub:
    def __init__(self):
        self.loop = None
        self.queues = []
        self.received = []

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
                    message = await websocket.receive()
                    if message.get("text"):
                        stub.received.append(json.loads(message["text"]))
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


def _fields(**overrides):
    base = {
        "whatHappened": "Man collapsed",
        "departments": ["EMS"],
        "numberOfPatients": 1,
        "weapons": False,
        "consciousness": "conscious",
    }
    base.update(overrides)
    return base


def _push(stub, page, fields, expected_what=None):
    stub.push({"type": "extraction_update", "fields": fields})
    expect(page.locator("#extractionFields .kv-row").first).to_be_visible()
    if expected_what is not None:
        expect(_row(page, "What").locator(".kv-value")).to_have_text(expected_what)


def _push_and_wait(stub, page, fields, row, value):
    stub.push({"type": "extraction_update", "fields": fields})
    expect(_row(page, row).locator(".kv-value")).to_contain_text(value)


def _row(page, label):
    return page.locator(".kv-row").filter(has=page.locator(".kv-key", has_text=label)).first


def _tag_hidden(page):
    return page.locator("#jevTag").evaluate("el => el.hidden")


def test_no_tag_before_any_override(app_page):
    assert _tag_hidden(app_page)
    expect(app_page.locator("#jevTag")).not_to_be_visible()
    expect(app_page.locator(".jev-dot")).to_have_count(0)
    expect(app_page.locator("#jevStatus")).to_have_text("")
    expect(app_page.locator(".source-tag--llm")).to_be_visible()


def test_row_labels_present(app_page, ws_stub):
    _push(ws_stub, app_page, _fields(), "Man collapsed")
    labels = app_page.locator(".kv-row .kv-key").all_text_contents()
    assert labels == ROW_LABELS


@pytest.mark.parametrize("sources", [{}, None])
def test_no_tag_when_sources_empty_or_absent(app_page, ws_stub, sources):
    fields = _fields() if sources is None else _fields(sources=sources)
    _push(ws_stub, app_page, fields, "Man collapsed")
    assert _tag_hidden(app_page)
    expect(app_page.locator("#jevTag")).not_to_be_visible()
    expect(app_page.locator(".jev-dot")).to_have_count(0)
    expect(app_page.locator(".kv-row--changed")).to_have_count(0)
    expect(app_page.locator("#jevStatus")).to_have_text("")


def test_tag_appears_with_accessible_name_and_llm_tag_remains(app_page, ws_stub):
    _push(ws_stub, app_page, _fields(weapons=True, sources={"weapons": "jev"}), "Man collapsed")
    tag = app_page.locator("#jevTag")
    expect(tag).to_be_visible()
    expect(tag).to_have_text("Jev")
    expect(tag).to_have_attribute("title", JEV_LABEL)
    expect(tag).to_have_attribute("aria-label", JEV_LABEL)
    expect(app_page.get_by_label(JEV_LABEL)).to_be_visible()
    expect(app_page.locator(".source-tag--llm")).to_be_visible()
    expect(app_page.locator(".source-tag-group .source-tag")).to_have_count(2)


def test_dots_only_on_jev_sourced_rows(app_page, ws_stub):
    _push(ws_stub, app_page, _fields(weapons=True, sources={"weapons": "jev"}), "Man collapsed")
    expect(app_page.locator(".jev-dot")).to_have_count(1)
    weapons = _row(app_page, "Weapons")
    expect(weapons.locator(".jev-dot")).to_have_attribute("title", "Refined by Jev")
    expect(weapons.locator(".visually-hidden")).to_have_text("refined by Jev")
    for label in ["What", "Where", "Department", "Patients", "Conscious"]:
        expect(_row(app_page, label).locator(".jev-dot")).to_have_count(0)
        expect(_row(app_page, label).locator(".visually-hidden")).to_have_count(0)


def test_changed_cue_only_on_jev_sourced_changed_row(app_page, ws_stub):
    _push(ws_stub, app_page, _fields(), "Man collapsed")
    expect(app_page.locator(".kv-row--changed")).to_have_count(0)
    _push_and_wait(ws_stub, app_page, _fields(weapons=True, sources={"weapons": "jev"}), "Weapons", "Yes")
    changed = app_page.locator(".kv-row--changed")
    expect(changed).to_have_count(1)
    expect(changed.locator(".kv-key")).to_have_text("Weapons")


def test_plain_rule_change_does_not_flash_or_announce(app_page, ws_stub):
    _push(ws_stub, app_page, _fields(), "Man collapsed")
    _push_and_wait(ws_stub, app_page, _fields(numberOfPatients=2), "Patients", "2")
    expect(app_page.locator(".kv-row--changed")).to_have_count(0)
    expect(app_page.locator("#jevStatus")).to_have_text("")
    assert _tag_hidden(app_page)


def test_plain_change_alongside_jev_change_flashes_only_jev_row(app_page, ws_stub):
    _push(ws_stub, app_page, _fields(), "Man collapsed")
    _push_and_wait(
        ws_stub, app_page,
        _fields(numberOfPatients=2, weapons=True, sources={"weapons": "jev"}), "Patients", "2",
    )
    changed = app_page.locator(".kv-row--changed")
    expect(changed).to_have_count(1)
    expect(changed.locator(".kv-key")).to_have_text("Weapons")


def test_unchanged_jev_row_on_later_update_does_not_flash(app_page, ws_stub):
    _push(ws_stub, app_page, _fields(), "Man collapsed")
    jev = {"weapons": "jev"}
    _push_and_wait(ws_stub, app_page, _fields(weapons=True, sources=jev), "Weapons", "Yes")
    _push_and_wait(ws_stub, app_page, _fields(weapons=True, sources=jev, whatHappened="Man down"), "What", "Man down")
    expect(app_page.locator(".kv-row--changed")).to_have_count(0)
    expect(app_page.locator(".jev-dot")).to_have_count(1)


def test_status_announces_jev_change_only(app_page, ws_stub):
    status = app_page.locator("#jevStatus")
    expect(status).to_have_attribute("role", "status")
    expect(status).to_have_attribute("aria-live", "polite")
    expect(status).to_have_text("")
    _push(ws_stub, app_page, _fields(), "Man collapsed")
    expect(status).to_have_text("")
    _push_and_wait(ws_stub, app_page, _fields(numberOfPatients=3), "Patients", "3")
    expect(status).to_have_text("")
    _push_and_wait(ws_stub, app_page, _fields(numberOfPatients=3, weapons=True, sources={"weapons": "jev"}), "Weapons", "Yes")
    expect(status).to_have_text("Weapons updated to Yes by Jev")
    assert "visually-hidden" in status.get_attribute("class")


def test_status_not_set_on_first_render_after_reset(app_page, ws_stub):
    _push(ws_stub, app_page, _fields(weapons=True, sources={"weapons": "jev"}), "Man collapsed")
    app_page.locator("#callerSelect").select_option(index=1)
    expect(app_page.locator("#jevStatus")).to_have_text("")
    _push(ws_stub, app_page, _fields(weapons=True, sources={"weapons": "jev"}), "Man collapsed")
    expect(app_page.locator(".kv-row--changed")).to_have_count(0)
    expect(app_page.locator("#jevStatus")).to_have_text("")
    expect(app_page.locator(".jev-dot")).to_have_count(1)


def test_caller_change_clears_tag_dots_status_and_sends_set_caller(app_page, ws_stub):
    _push(ws_stub, app_page, _fields(), "Man collapsed")
    _push_and_wait(ws_stub, app_page, _fields(weapons=True, sources={"weapons": "jev"}), "Weapons", "Yes")
    expect(app_page.locator("#jevTag")).to_be_visible()
    expect(app_page.locator("#jevStatus")).to_have_text("Weapons updated to Yes by Jev")

    select = app_page.locator("#callerSelect")
    target = select.locator("option").nth(1).get_attribute("value")
    select.select_option(index=1)

    assert _tag_hidden(app_page)
    expect(app_page.locator("#jevTag")).not_to_be_visible()
    expect(app_page.locator(".jev-dot")).to_have_count(0)
    expect(app_page.locator(".kv-row--changed")).to_have_count(0)
    expect(app_page.locator("#jevStatus")).to_have_text("")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and {"type": "set_caller", "address": target} not in ws_stub.received:
        app_page.wait_for_timeout(50)
    assert {"type": "set_caller", "address": target} in ws_stub.received


def test_reduced_motion_disables_fade(app_page, ws_stub):
    app_page.emulate_media(reduced_motion="reduce")
    _push(ws_stub, app_page, _fields(), "Man collapsed")
    _push_and_wait(ws_stub, app_page, _fields(weapons=True, sources={"weapons": "jev"}), "Weapons", "Yes")
    changed = app_page.locator(".kv-row--changed")
    expect(changed).to_have_count(1)
    assert changed.evaluate("el => getComputedStyle(el).animationName") == "none"


def test_fade_animation_runs_without_reduced_motion(app_page, ws_stub):
    app_page.emulate_media(reduced_motion="no-preference")
    _push(ws_stub, app_page, _fields(), "Man collapsed")
    _push_and_wait(ws_stub, app_page, _fields(weapons=True, sources={"weapons": "jev"}), "Weapons", "Yes")
    changed = app_page.locator(".kv-row--changed")
    assert changed.evaluate("el => getComputedStyle(el).animationName") == "kv-row-flash"
    assert changed.evaluate("el => getComputedStyle(el).animationDuration") == "0.6s"


def _row_heights(page):
    return page.locator(".kv-row").evaluate_all("els => els.map(e => e.getBoundingClientRect().height)")


def test_no_row_height_shift_with_dots_and_tag(app_page, ws_stub):
    _push(ws_stub, app_page, _fields(), "Man collapsed")
    before = _row_heights(app_page)
    panel_before = app_page.locator(".summary-panel").bounding_box()["height"]
    _push_and_wait(
        ws_stub, app_page,
        _fields(sources={"weapons": "jev", "consciousness": "jev", "numberOfPatients": "jev"}), "Weapons", "No",
    )
    expect(app_page.locator(".jev-dot")).to_have_count(3)
    expect(app_page.locator("#jevTag")).to_be_visible()
    assert _row_heights(app_page) == pytest.approx(before, abs=0.5)
    assert app_page.locator(".summary-panel").bounding_box()["height"] == pytest.approx(panel_before, abs=0.5)


def test_heading_and_tag_group_do_not_overlap(app_page, ws_stub):
    _push(ws_stub, app_page, _fields(sources={"weapons": "jev"}), "Man collapsed")
    expect(app_page.locator("#jevTag")).to_be_visible()
    heading_text = app_page.locator(".summary-panel > h2").evaluate(
        """el => {
            const range = document.createRange();
            range.selectNodeContents(el);
            const r = range.getBoundingClientRect();
            return {left: r.left, right: r.right, top: r.top, bottom: r.bottom};
        }"""
    )
    group = app_page.locator(".source-tag-group").bounding_box()
    heading = app_page.locator(".summary-panel > h2").bounding_box()
    assert heading_text["right"] <= group["x"] or heading_text["bottom"] <= group["y"]
    assert heading["x"] + heading["width"] <= app_page.locator(".summary-panel").bounding_box()["x"] + app_page.locator(".summary-panel").bounding_box()["width"] + 0.5
    jev = app_page.locator("#jevTag").bounding_box()
    llm = app_page.locator(".source-tag--llm").bounding_box()
    assert jev["x"] + jev["width"] <= llm["x"] + 0.5


def test_what_happened_renders_as_text_not_html(app_page, ws_stub):
    payload = "<img src=x onerror=window.__pwned=1> & <b>bold</b>"
    _push(ws_stub, app_page, _fields(whatHappened=payload), payload)
    expect(_row(app_page, "What").locator(".kv-value")).to_have_text(payload)
    expect(app_page.locator("#extractionFields img")).to_have_count(0)
    expect(app_page.locator("#extractionFields b")).to_have_count(0)
    assert app_page.evaluate("() => window.__pwned === undefined")
