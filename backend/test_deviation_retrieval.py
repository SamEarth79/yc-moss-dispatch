from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.testclient import TestClient

import server
from live_panel import DEVIATION_INDEX_NAME, PROTOCOL_INDEX_NAME, WINDOW_WORDS

TRANSCRIPT = "one two three four five six seven eight nine ten my dad is choking"
TRAILING = " ".join(TRANSCRIPT.split(" ")[-WINDOW_WORDS:])
PAYLOAD_KEYS = {"id", "summary", "dispatcherTranscript", "reason", "timestamp", "score"}


def _protocol_result():
    doc = SimpleNamespace(
        id="choking-1", text="Back blows.", score=0.9, metadata={"priority": "high", "suggestedAction": "EMS"}
    )
    return SimpleNamespace(docs=[doc], time_taken_ms=4.0)


def _deviation_doc(doc_id, score, summary="Gave water"):
    return SimpleNamespace(
        id=doc_id,
        text="situation\nsummary",
        score=score,
        metadata={
            "deviationSummary": summary,
            "dispatcherTranscript": "give him water",
            "reason": "thirsty",
            "timestamp": "2026-01-01T00:00:00Z",
            "protocolChunkText": "Back blows.",
        },
    )


class _FakeMoss:
    def __init__(self, deviation_docs=None, deviation_error=None):
        self.deviation_docs = deviation_docs if deviation_docs is not None else []
        self.deviation_error = deviation_error
        self.calls = []

    async def query(self, index, text, options):
        self.calls.append((index, text, options.top_k))
        if index == PROTOCOL_INDEX_NAME:
            return _protocol_result()
        if self.deviation_error:
            raise self.deviation_error
        return SimpleNamespace(docs=self.deviation_docs[: options.top_k], time_taken_ms=7.25)


def _run_transcript(monkeypatch, fake, text=TRANSCRIPT):
    """Sends one transcript over /ws and returns every message up to the first extraction_update."""
    monkeypatch.setattr(server, "moss_client", fake)
    monkeypatch.setattr(server, "extract_llm_fields", AsyncMock(return_value=None))
    messages = []
    with TestClient(server.app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "transcript", "text": text})
        while True:
            message = ws.receive_json()
            messages.append(message)
            if message["type"] == "extraction_update":
                return messages


def _of_type(messages, message_type):
    return [m for m in messages if m["type"] == message_type]


def test_runs_protocol_top1_and_deviation_top2_with_same_trailing_window(monkeypatch):
    fake = _FakeMoss([_deviation_doc("dev-1", 0.8)])
    _run_transcript(monkeypatch, fake)
    assert sorted(fake.calls) == sorted(
        [(PROTOCOL_INDEX_NAME, TRAILING, 1), (DEVIATION_INDEX_NAME, TRAILING, 2)]
    )


def test_drops_deviations_below_min_score_and_keeps_those_at_cutoff(monkeypatch):
    docs = [_deviation_doc("dev-at", server.DEVIATION_MIN_SCORE), _deviation_doc("dev-low", 0.29)]
    messages = _run_transcript(monkeypatch, _FakeMoss(docs))
    (update,) = _of_type(messages, "deviation_update")
    assert [d["id"] for d in update["deviations"]] == ["dev-at"]


def test_all_below_cutoff_sends_empty_list(monkeypatch):
    messages = _run_transcript(monkeypatch, _FakeMoss([_deviation_doc("a", 0.1), _deviation_doc("b", 0.2)]))
    assert _of_type(messages, "deviation_update")[0]["deviations"] == []


def test_sends_at_most_two_deviations_with_documented_shape(monkeypatch):
    docs = [_deviation_doc("a", 0.9), _deviation_doc("b", 0.5), _deviation_doc("c", 0.4)]
    messages = _run_transcript(monkeypatch, _FakeMoss(docs))
    deviations = _of_type(messages, "deviation_update")[0]["deviations"]
    assert [d["id"] for d in deviations] == ["a", "b"]
    assert PAYLOAD_KEYS <= set(deviations[0])
    assert deviations[0]["summary"] == "Gave water"
    assert deviations[0]["dispatcherTranscript"] == "give him water"
    assert deviations[0]["reason"] == "thirsty"
    assert deviations[0]["timestamp"] == "2026-01-01T00:00:00Z"
    assert deviations[0]["score"] == 0.9


def test_deviation_update_is_sent_after_protocol_update(monkeypatch):
    messages = _run_transcript(monkeypatch, _FakeMoss([_deviation_doc("a", 0.9)]))
    types = [m["type"] for m in messages]
    assert types.index("protocol_update") < types.index("deviation_update")


def test_sends_deviation_query_dev_log_with_latency(monkeypatch):
    messages = _run_transcript(monkeypatch, _FakeMoss([_deviation_doc("a", 0.9), _deviation_doc("b", 0.1)]))
    (entry,) = [m for m in _of_type(messages, "dev_log") if m["callType"] == "deviation-query"]
    assert entry["service"] == "moss"
    assert entry["latencyMs"] == pytest.approx(7.25, abs=0.1)
    assert "2 retrieved" in entry["summary"] and "1 above" in entry["summary"]


def test_deviation_query_failure_sends_empty_update_and_leaves_protocol_path_intact(monkeypatch):
    healthy = _run_transcript(monkeypatch, _FakeMoss([_deviation_doc("a", 0.9)]))
    failing = _run_transcript(monkeypatch, _FakeMoss(deviation_error=RuntimeError("index not loaded")))
    assert _of_type(failing, "deviation_update")[0]["deviations"] == []
    assert not [m for m in _of_type(failing, "dev_log") if m["callType"] == "deviation-query"]
    assert _of_type(failing, "protocol_update") == _of_type(healthy, "protocol_update")
    assert len(_of_type(failing, "protocol_update")) == 1
    assert [m for m in _of_type(failing, "dev_log") if m["callType"] == "protocol-query"]


class _StatefulMoss(_FakeMoss):
    """Stores a deviation on add_docs/create_index and makes it queryable only after load_index."""

    def __init__(self):
        super().__init__()
        self.stored = []
        self.loaded = []
        self.list_indexes = AsyncMock(return_value=[])
        self.create_index = AsyncMock(side_effect=self._store)

    async def _store(self, name, docs):
        self.stored.extend(docs)

    async def load_index(self, name):
        self.loaded = list(self.stored)
        self.deviation_docs = [
            SimpleNamespace(id=d.id, text=d.text, score=0.9, metadata=d.metadata) for d in self.loaded
        ]


def test_deviation_from_judge_endpoint_is_retrieved_on_later_transcript_without_restart(monkeypatch):
    fake = _StatefulMoss()
    monkeypatch.setattr(server, "moss_client", fake)
    monkeypatch.setattr(
        server, "judge_deviation", AsyncMock(return_value={"verdict": "deviated", "deviationSummary": "Gave water", "devLog": []})
    )
    before = _run_transcript(monkeypatch, fake)
    assert _of_type(before, "deviation_update")[0]["deviations"] == []

    body = {
        "dispatcherText": "Give him some water",
        "reason": "he looks thirsty",
        "protocolChunkId": "choking-1",
        "protocolChunkText": "Back blows.",
        "callerTranscript": TRANSCRIPT,
    }
    response = TestClient(server.app).post("/api/deviations/judge", json=body)
    assert response.status_code == 200
    saved_id = response.json()["id"]

    after = _run_transcript(monkeypatch, fake)
    (deviation,) = _of_type(after, "deviation_update")[0]["deviations"]
    assert deviation["id"] == saved_id
    assert deviation["summary"] == "Gave water"
    assert deviation["dispatcherTranscript"] == "Give him some water"
    assert deviation["reason"] == "he looks thirsty"
