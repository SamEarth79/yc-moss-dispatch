import json
from types import SimpleNamespace

from starlette.testclient import TestClient

import server
from live_panel import DEVIATION_INDEX_NAME

RECORD_KEYS = {
    "id",
    "timestamp",
    "callerTranscript",
    "callerSummary",
    "protocolChunkId",
    "protocolChunkText",
    "dispatcherTranscript",
    "deviationSummary",
    "reason",
    "seed",
}


def _doc(doc_id, timestamp, **overrides):
    metadata = {
        "timestamp": timestamp,
        "callerTranscript": "my dad is choking",
        "callerSummary": json.dumps({"whatHappened": "choking"}),
        "protocolChunkId": "choking-1",
        "protocolChunkText": "Back blows.",
        "dispatcherTranscript": "give him water",
        "deviationSummary": "Gave water instead of back blows",
        "reason": "thirsty",
        "seed": "false",
    }
    metadata.update(overrides)
    return SimpleNamespace(id=doc_id, text="t", metadata=metadata)


class _FakeMoss:
    def __init__(self, docs=None, index_error=None, docs_error=None):
        self.docs = docs or []
        self.index_error = index_error
        self.docs_error = docs_error
        self.indexes_requested = []

    async def get_index(self, name):
        self.indexes_requested.append(name)
        if self.index_error:
            raise self.index_error
        return SimpleNamespace(name=name)

    async def get_docs(self, name):
        if self.docs_error:
            raise self.docs_error
        return self.docs


def _get(monkeypatch, fake):
    monkeypatch.setattr(server, "moss_client", fake)
    return TestClient(server.app).get("/api/deviations")


def test_returns_empty_array_when_index_does_not_exist(monkeypatch):
    response = _get(monkeypatch, _FakeMoss(index_error=RuntimeError("Index not found")))
    assert response.status_code == 200
    assert response.json() == []


def test_returns_empty_array_when_index_has_no_records(monkeypatch):
    fake = _FakeMoss(docs=[])
    response = _get(monkeypatch, fake)
    assert response.status_code == 200
    assert response.json() == []
    assert fake.indexes_requested == [DEVIATION_INDEX_NAME]


def test_sorts_records_newest_first(monkeypatch):
    docs = [
        _doc("old", "2026-01-01T00:00:00Z"),
        _doc("newest", "2026-03-01T00:00:00Z"),
        _doc("mid", "2026-02-01T00:00:00Z"),
    ]
    response = _get(monkeypatch, _FakeMoss(docs=docs))
    assert [r["id"] for r in response.json()] == ["newest", "mid", "old"]


def test_record_has_exact_shape_and_values(monkeypatch):
    response = _get(monkeypatch, _FakeMoss(docs=[_doc("dev-1", "2026-01-01T00:00:00Z")]))
    (record,) = response.json()
    assert set(record) == RECORD_KEYS
    assert record["id"] == "dev-1"
    assert record["callerSummary"] == {"whatHappened": "choking"}
    assert record["protocolChunkId"] == "choking-1"
    assert record["dispatcherTranscript"] == "give him water"
    assert record["reason"] == "thirsty"
    assert record["seed"] is False


def test_missing_metadata_fields_default_to_empty_values(monkeypatch):
    bare = SimpleNamespace(id="bare", text="t", metadata=None)
    (record,) = _get(monkeypatch, _FakeMoss(docs=[bare])).json()
    assert set(record) == RECORD_KEYS
    assert record["callerSummary"] == {}
    assert record["reason"] == ""
    assert record["seed"] is False


def test_malformed_caller_summary_becomes_empty_object(monkeypatch):
    docs = [
        _doc("bad-json", "2026-01-03T00:00:00Z", callerSummary="{not json"),
        _doc("not-object", "2026-01-02T00:00:00Z", callerSummary="[1, 2]"),
        _doc("empty", "2026-01-01T00:00:00Z", callerSummary=""),
    ]
    response = _get(monkeypatch, _FakeMoss(docs=docs))
    assert response.status_code == 200
    assert [r["callerSummary"] for r in response.json()] == [{}, {}, {}]


def test_seed_flag_is_true_only_for_seed_string_true(monkeypatch):
    docs = [
        _doc("seeded", "2026-01-02T00:00:00Z", seed="true"),
        _doc("live", "2026-01-01T00:00:00Z", seed="false"),
    ]
    by_id = {r["id"]: r for r in _get(monkeypatch, _FakeMoss(docs=docs)).json()}
    assert by_id["seeded"]["seed"] is True
    assert by_id["live"]["seed"] is False


def test_returns_500_without_leaking_when_index_lookup_fails(monkeypatch):
    response = _get(monkeypatch, _FakeMoss(index_error=ValueError("secret-key-abc traceback")))
    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to retrieve deviations"}
    assert "secret-key-abc" not in response.text


def test_returns_500_without_leaking_when_get_docs_fails(monkeypatch):
    response = _get(monkeypatch, _FakeMoss(docs_error=ConnectionError("moss://user:pw@host")))
    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to retrieve deviations"}
    assert "pw@host" not in response.text
