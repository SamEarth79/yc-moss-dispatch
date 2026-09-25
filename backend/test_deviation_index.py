import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.testclient import TestClient

import server
from deviation_seed import DEVIATION_SEEDS
from live_panel import DEVIATION_INDEX_NAME, LIVE_DATA_INDEX_NAME, PROTOCOL_INDEX_NAME
from protocol_chunks import PROTOCOL_CHUNKS

REQUIRED = [PROTOCOL_INDEX_NAME, LIVE_DATA_INDEX_NAME]


def _result(failed=None):
    return SimpleNamespace(failed=failed or {})


def _install_fake_client(monkeypatch, load_side_effect):
    fake = SimpleNamespace(
        load_indexes=AsyncMock(side_effect=load_side_effect),
        unload_indexes=AsyncMock(),
        load_index=AsyncMock(),
        list_indexes=AsyncMock(return_value=[]),
    )
    monkeypatch.setenv("MOSS_PROJECT_ID", "test-id")
    monkeypatch.setenv("MOSS_PROJECT_KEY", "test-key")
    monkeypatch.setattr(server, "MossClient", lambda *args, **kwargs: fake)
    monkeypatch.setattr(server, "load_dotenv", lambda *args, **kwargs: None)
    return fake


def test_deviation_index_name_constant_value():
    assert DEVIATION_INDEX_NAME == "deviation-index"
    assert server.DEVIATION_INDEX_NAME is DEVIATION_INDEX_NAME


def test_seed_has_three_or_four_records():
    assert 3 <= len(DEVIATION_SEEDS) <= 4


def test_seed_records_are_deviation_typed_seed_flagged_with_string_only_metadata():
    for record in DEVIATION_SEEDS:
        assert record["id"] and record["text"].strip()
        metadata = record["metadata"]
        assert metadata["type"] == "deviation"
        assert metadata["seed"] == "true"
        for key, value in metadata.items():
            assert isinstance(key, str) and isinstance(value, str), key


def test_seed_metadata_has_architecture_fields():
    expected = {
        "type", "callerTranscript", "callerSummary", "protocolChunkId", "protocolChunkText",
        "dispatcherTranscript", "deviationSummary", "reason", "timestamp", "seed",
    }
    for record in DEVIATION_SEEDS:
        assert expected <= set(record["metadata"])


def test_seed_protocol_chunk_ids_reference_real_protocol_chunks():
    chunk_ids = {chunk["id"] for chunk in PROTOCOL_CHUNKS}
    for record in DEVIATION_SEEDS:
        assert record["metadata"]["protocolChunkId"] in chunk_ids


def test_seed_ids_are_unique():
    ids = [record["id"] for record in DEVIATION_SEEDS]
    assert len(ids) == len(set(ids))


def test_lifespan_loads_deviation_index_and_unloads_all_on_shutdown(monkeypatch):
    fake = _install_fake_client(monkeypatch, lambda names, **kw: _result())

    with TestClient(server.app):
        loaded_calls = [call.args[0] for call in fake.load_indexes.await_args_list]
        assert loaded_calls == [REQUIRED, [DEVIATION_INDEX_NAME]]

    fake.unload_indexes.assert_awaited_once_with(REQUIRED + [DEVIATION_INDEX_NAME])


def test_lifespan_starts_and_unloads_only_required_when_deviation_load_reports_failure(monkeypatch, caplog):
    def load(names, **kw):
        if names == [DEVIATION_INDEX_NAME]:
            return _result({DEVIATION_INDEX_NAME: "not found"})
        return _result()

    fake = _install_fake_client(monkeypatch, load)

    with caplog.at_level(logging.WARNING, logger="server"):
        with TestClient(server.app) as client:
            assert client.get("/api/indexes").status_code == 200

    assert any("Deviation index not loaded" in r.message for r in caplog.records)
    fake.unload_indexes.assert_awaited_once_with(REQUIRED)


def test_lifespan_starts_and_unloads_only_required_when_deviation_load_raises(monkeypatch, caplog):
    def load(names, **kw):
        if names == [DEVIATION_INDEX_NAME]:
            raise RuntimeError("index missing")
        return _result()

    fake = _install_fake_client(monkeypatch, load)

    with caplog.at_level(logging.WARNING, logger="server"):
        with TestClient(server.app):
            pass

    assert any("Deviation index not loaded" in r.message for r in caplog.records)
    fake.unload_indexes.assert_awaited_once_with(REQUIRED)


def test_lifespan_still_raises_when_required_index_fails_after_retry(monkeypatch):
    def load(names, **kw):
        if names == REQUIRED or names == [PROTOCOL_INDEX_NAME]:
            return _result({PROTOCOL_INDEX_NAME: "boom"})
        return _result()

    fake = _install_fake_client(monkeypatch, load)

    with pytest.raises(RuntimeError, match="Failed to load indexes after retry"):
        with TestClient(server.app):
            pass

    assert [DEVIATION_INDEX_NAME] not in [c.args[0] for c in fake.load_indexes.await_args_list]


def test_deviation_index_is_in_live_loaded_indexes():
    assert DEVIATION_INDEX_NAME in server.LIVE_LOADED_INDEXES
    assert {PROTOCOL_INDEX_NAME, LIVE_DATA_INDEX_NAME} <= server.LIVE_LOADED_INDEXES


def test_adding_doc_to_deviation_index_reloads_it(monkeypatch):
    fake = SimpleNamespace(add_docs=AsyncMock(), load_index=AsyncMock())
    monkeypatch.setattr(server, "moss_client", fake)

    response = TestClient(server.app).post(
        f"/api/indexes/{DEVIATION_INDEX_NAME}/docs", json={"id": "d1", "text": "t", "metadata": {"type": "deviation"}}
    )

    assert response.status_code == 200
    fake.load_index.assert_awaited_once_with(DEVIATION_INDEX_NAME)


def test_deleting_doc_from_deviation_index_reloads_it(monkeypatch):
    fake = SimpleNamespace(delete_docs=AsyncMock(), load_index=AsyncMock())
    monkeypatch.setattr(server, "moss_client", fake)

    response = TestClient(server.app).delete(f"/api/indexes/{DEVIATION_INDEX_NAME}/docs/d1")

    assert response.status_code == 204
    fake.load_index.assert_awaited_once_with(DEVIATION_INDEX_NAME)


def test_api_indexes_lists_deviation_index(monkeypatch):
    index = SimpleNamespace(
        name=DEVIATION_INDEX_NAME, doc_count=3, status="ready",
        model=SimpleNamespace(id="moss-minilm"), updated_at="2026-01-01T00:00:00Z",
    )
    monkeypatch.setattr(server, "moss_client", SimpleNamespace(list_indexes=AsyncMock(return_value=[index])))

    response = TestClient(server.app).get("/api/indexes")

    assert [i["name"] for i in response.json()] == [DEVIATION_INDEX_NAME]
    assert response.json()[0]["docCount"] == 3
