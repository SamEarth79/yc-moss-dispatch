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


def test_save_deviation_concurrent_first_writes_create_index_once(monkeypatch):
    import asyncio

    created = []

    async def list_indexes():
        await asyncio.sleep(0)
        return [SimpleNamespace(name=DEVIATION_INDEX_NAME)] if created else []

    async def create_index(name, docs):
        await asyncio.sleep(0)
        created.append(name)

    fake = SimpleNamespace(list_indexes=list_indexes, create_index=AsyncMock(side_effect=create_index), add_docs=AsyncMock())
    monkeypatch.setattr(server, "moss_client", fake)

    async def run():
        await asyncio.gather(server.save_deviation("doc-1"), server.save_deviation("doc-2"))

    asyncio.run(run())
    assert fake.create_index.await_count == 1
    assert fake.add_docs.await_count == 1


def _run_build_main(monkeypatch, force, index_exists):
    import asyncio
    import build_deviation_index as build

    fake = SimpleNamespace(
        list_indexes=AsyncMock(return_value=[SimpleNamespace(name=DEVIATION_INDEX_NAME)] if index_exists else []),
        delete_index=AsyncMock(),
        create_index=AsyncMock(return_value=SimpleNamespace(job_id="j", index_name=DEVIATION_INDEX_NAME, doc_count=3)),
    )
    monkeypatch.setenv("MOSS_PROJECT_ID", "test-id")
    monkeypatch.setenv("MOSS_PROJECT_KEY", "test-key")
    monkeypatch.setattr(build, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(build, "MossClient", lambda *args, **kwargs: fake)
    return build, fake, asyncio.run(build.main(force))


def test_build_wants_force_only_with_explicit_flag():
    import build_deviation_index as build

    assert build.wants_force(["--force"]) is True
    assert build.wants_force([]) is False


def test_build_refuses_to_delete_existing_index_without_force(monkeypatch, capsys):
    _, fake, code = _run_build_main(monkeypatch, force=False, index_exists=True)
    assert code == 1
    assert "--force" in capsys.readouterr().out
    fake.delete_index.assert_not_awaited()
    fake.create_index.assert_not_awaited()


def test_build_deletes_and_rebuilds_existing_index_with_force(monkeypatch):
    _, fake, code = _run_build_main(monkeypatch, force=True, index_exists=True)
    assert code == 0
    fake.delete_index.assert_awaited_once_with(DEVIATION_INDEX_NAME)
    fake.create_index.assert_awaited_once()


def test_build_creates_index_without_force_when_none_exists(monkeypatch):
    _, fake, code = _run_build_main(monkeypatch, force=False, index_exists=False)
    assert code == 0
    fake.delete_index.assert_not_awaited()
    fake.create_index.assert_awaited_once()
