from types import SimpleNamespace
from unittest.mock import AsyncMock

from starlette.testclient import TestClient

import server
from live_panel import PROTOCOL_INDEX_NAME
from voice_stream import VoiceStreamUnavailable


class FakeStreams:
    """Stands in for server.DeepgramStream. Each instance records its calls; when it
    receives an audio chunk it emits `text` through the callback the server gave it,
    so results arrive on the server's own event loop deterministically."""

    def __init__(self):
        self.instances = []
        self.unavailable_for = set()
        self.text = "hello"

    def factory(self, callback):
        owner = self
        stream = SimpleNamespace(callback=callback, started=False, stopped=0, audio=[])

        async def start():
            if callback.__name__ in owner.unavailable_for:
                raise VoiceStreamUnavailable("no key")
            stream.started = True

        async def stop():
            stream.stopped += 1

        async def send_audio(chunk):
            stream.audio.append(chunk)
            await callback(owner.text, True)

        stream.start, stream.stop, stream.send_audio = start, stop, send_audio
        self.instances.append(stream)
        return stream


class _Moss:
    async def query(self, index, text, options):
        doc = SimpleNamespace(id="choking-1", text="Back blows.", score=0.9, metadata={"priority": "high", "suggestedAction": "EMS"})
        return SimpleNamespace(docs=[doc] if index == PROTOCOL_INDEX_NAME else [], time_taken_ms=1.0)


def _setup(monkeypatch):
    fake = FakeStreams()
    monkeypatch.setattr(server, "DeepgramStream", fake.factory)
    monkeypatch.setattr(server, "moss_client", _Moss())
    monkeypatch.setattr(server, "extract_llm_fields", AsyncMock(return_value=None))
    return fake


def _until(ws, predicate):
    seen = []
    while True:
        message = ws.receive_json()
        seen.append(message)
        if predicate(message):
            return seen


def _status(ws):
    return _until(ws, lambda m: m["type"] == "voice_status")[-1]


def _types(messages):
    return [m["type"] for m in messages]


def test_caller_voice_start_default_channel_unchanged(monkeypatch):
    fake = _setup(monkeypatch)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "voice_start"})
        assert _status(ws) == {"type": "voice_status", "state": "listening"}
        ws.send_json({"type": "voice_stop"})
        assert _status(ws) == {"type": "voice_status", "state": "stopped"}
    assert fake.instances[0].started and fake.instances[0].stopped >= 1


def test_caller_transcript_still_sent_and_triggers_protocol_update(monkeypatch):
    fake = _setup(monkeypatch)
    fake.text = "my dad is choking"
    with TestClient(server.app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "voice_start", "channel": "caller"})
        _status(ws)
        ws.send_bytes(b"\x00\x01")
        seen = _until(ws, lambda m: m["type"] == "protocol_update")
    voice = [m for m in seen if m["type"] == "voice_transcript"]
    assert voice == [{"type": "voice_transcript", "text": "my dad is choking"}]
    assert seen[-1]["transcript"] == "my dad is choking"


def test_dispatcher_start_stop_status_carries_channel(monkeypatch):
    fake = _setup(monkeypatch)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "voice_start", "channel": "dispatcher"})
        assert _status(ws) == {"type": "voice_status", "state": "listening", "channel": "dispatcher"}
        ws.send_json({"type": "voice_stop", "channel": "dispatcher"})
        assert _status(ws) == {"type": "voice_status", "state": "stopped", "channel": "dispatcher"}
    assert fake.instances[0].stopped >= 1


def test_dispatcher_results_use_dispatcher_message_and_skip_caller_state(monkeypatch):
    fake = _setup(monkeypatch)
    fake.text = "give him water"
    with TestClient(server.app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "voice_start", "channel": "dispatcher"})
        _status(ws)
        ws.send_bytes(b"\x00")
        ws.send_json({"type": "voice_stop", "channel": "dispatcher"})
        seen = _until(ws, lambda m: m["type"] == "voice_status" and m["state"] == "stopped")
    assert {"type": "dispatcher_voice_transcript", "text": "give him water", "isFinal": True} in seen
    assert "voice_transcript" not in _types(seen)
    assert "protocol_update" not in _types(seen)


def test_dispatcher_transcript_never_reaches_transcript_worker(monkeypatch):
    fake = _setup(monkeypatch)
    fake.text = "give him water"
    moss = _Moss()
    moss.query = AsyncMock(side_effect=moss.query)
    monkeypatch.setattr(server, "moss_client", moss)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "voice_start", "channel": "dispatcher"})
        _status(ws)
        ws.send_bytes(b"\x00")
        ws.send_json({"type": "voice_stop", "channel": "dispatcher"})
        _until(ws, lambda m: m["type"] == "voice_status" and m["state"] == "stopped")
    moss.query.assert_not_called()


def test_unknown_channel_reports_error_and_keeps_session_alive(monkeypatch):
    fake = _setup(monkeypatch)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        for message_type in ("voice_start", "voice_stop"):
            ws.send_json({"type": message_type, "channel": "operator"})
            assert _status(ws) == {"type": "voice_status", "state": "error", "reason": "unknown voice channel"}
        ws.send_json({"type": "voice_start"})
        assert _status(ws)["state"] == "listening"
    assert len(fake.instances) == 1


def test_unavailable_caller_has_no_channel_tag(monkeypatch):
    fake = _setup(monkeypatch)
    fake.unavailable_for = {"handle_voice_transcript"}
    with TestClient(server.app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "voice_start"})
        assert _status(ws) == {"type": "voice_status", "state": "unavailable", "reason": "no key"}


def test_unavailable_dispatcher_is_tagged_and_does_not_open_a_stream(monkeypatch):
    fake = _setup(monkeypatch)
    fake.unavailable_for = {"handle_dispatcher_voice_transcript"}
    with TestClient(server.app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "voice_start", "channel": "dispatcher"})
        assert _status(ws) == {"type": "voice_status", "state": "unavailable", "reason": "no key", "channel": "dispatcher"}
        ws.send_bytes(b"\x00")
        ws.send_json({"type": "voice_stop", "channel": "dispatcher"})
        assert _status(ws)["state"] == "stopped"
    assert fake.instances[0].audio == []


def test_audio_goes_to_whichever_channel_stream_is_open(monkeypatch):
    fake = _setup(monkeypatch)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "voice_start"})
        _status(ws)
        ws.send_bytes(b"to-caller")
        ws.send_json({"type": "voice_stop"})
        _status(ws)
        ws.send_json({"type": "voice_start", "channel": "dispatcher"})
        _status(ws)
        ws.send_bytes(b"to-dispatcher")
        ws.send_json({"type": "voice_stop", "channel": "dispatcher"})
        _status(ws)
    caller, dispatcher = fake.instances
    assert caller.audio == [b"to-caller"]
    assert dispatcher.audio == [b"to-dispatcher"]


def test_restarting_a_channel_stops_its_previous_stream(monkeypatch):
    fake = _setup(monkeypatch)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "voice_start", "channel": "dispatcher"})
        _status(ws)
        ws.send_json({"type": "voice_start", "channel": "dispatcher"})
        _status(ws)
        first, second = fake.instances
        assert first.stopped == 1
        assert second.stopped == 0


def test_disconnect_stops_the_open_stream(monkeypatch):
    fake = _setup(monkeypatch)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "voice_start", "channel": "dispatcher"})
        _status(ws)
    assert [s.stopped for s in fake.instances] == [1]


def test_dispatcher_start_rejected_while_caller_mic_open(monkeypatch):
    fake = _setup(monkeypatch)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "voice_start"})
        assert _status(ws)["state"] == "listening"
        ws.send_json({"type": "voice_start", "channel": "dispatcher"})
        assert _status(ws) == {"type": "voice_status", "state": "unavailable", "reason": "another microphone is already active", "channel": "dispatcher"}
    assert len(fake.instances) == 1


def test_caller_start_rejected_while_dispatcher_mic_open(monkeypatch):
    fake = _setup(monkeypatch)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "voice_start", "channel": "dispatcher"})
        assert _status(ws)["state"] == "listening"
        ws.send_json({"type": "voice_start"})
        assert _status(ws) == {"type": "voice_status", "state": "unavailable", "reason": "another microphone is already active"}
    assert len(fake.instances) == 1


def test_start_allowed_after_other_channel_stops(monkeypatch):
    fake = _setup(monkeypatch)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "voice_start"})
        assert _status(ws)["state"] == "listening"
        ws.send_json({"type": "voice_stop"})
        assert _status(ws)["state"] == "stopped"
        ws.send_json({"type": "voice_start", "channel": "dispatcher"})
        assert _status(ws) == {"type": "voice_status", "state": "listening", "channel": "dispatcher"}
    assert len(fake.instances) == 2
