from types import SimpleNamespace
from unittest.mock import AsyncMock

from starlette.testclient import TestClient

import server
from live_panel import LIVE_DATA_INDEX_NAME, PROTOCOL_INDEX_NAME


def _fake_index(name="protocol-index", doc_count=10, status="ready", model_id="moss-minilm", updated_at="2026-01-01T00:00:00Z"):
    return SimpleNamespace(
        name=name,
        doc_count=doc_count,
        status=status,
        model=SimpleNamespace(id=model_id),
        updated_at=updated_at,
    )


def _fake_doc(doc_id="chunk-1", text="some chunk text", metadata=None):
    return SimpleNamespace(id=doc_id, text=text, metadata=metadata or {"sourceDoc": "example.md"})


def test_list_indexes_returns_mapped_shape(monkeypatch):
    fake_client = SimpleNamespace(list_indexes=AsyncMock(return_value=[_fake_index()]))
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.get("/api/indexes")

    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "protocol-index",
            "docCount": 10,
            "status": "ready",
            "model": "moss-minilm",
            "updatedAt": "2026-01-01T00:00:00Z",
        }
    ]


def test_get_index_docs_returns_mapped_shape_when_index_exists(monkeypatch):
    fake_client = SimpleNamespace(
        get_index=AsyncMock(return_value=_fake_index()),
        get_docs=AsyncMock(return_value=[_fake_doc()]),
    )
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.get("/api/indexes/protocol-index/docs")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "chunk-1", "text": "some chunk text", "metadata": {"sourceDoc": "example.md"}}
    ]


def test_get_index_docs_returns_404_when_index_missing(monkeypatch):
    fake_client = SimpleNamespace(
        get_index=AsyncMock(side_effect=RuntimeError("index not found")),
        get_docs=AsyncMock(),
    )
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.get("/api/indexes/nonexistent/docs")

    assert response.status_code == 404
    assert "nonexistent" in response.json()["detail"]
    fake_client.get_docs.assert_not_called()


def test_list_indexes_returns_500_without_leaking_details_on_unexpected_error(monkeypatch):
    fake_client = SimpleNamespace(
        list_indexes=AsyncMock(side_effect=RuntimeError("secret-connection-string-leak"))
    )
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.get("/api/indexes")

    assert response.status_code == 500
    assert "secret-connection-string-leak" not in response.text


def test_get_index_docs_returns_500_when_get_docs_fails_after_index_found(monkeypatch):
    fake_client = SimpleNamespace(
        get_index=AsyncMock(return_value=_fake_index()),
        get_docs=AsyncMock(side_effect=RuntimeError("secret-connection-string-leak")),
    )
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.get("/api/indexes/protocol-index/docs")

    assert response.status_code == 500
    assert "secret-connection-string-leak" not in response.text


# --- MOS-STORY-001-002: chunk mutation endpoints + live-reload ---


def test_add_index_doc_returns_id_and_calls_add_docs_with_matching_document(monkeypatch):
    fake_client = SimpleNamespace(
        add_docs=AsyncMock(return_value=None),
        load_index=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.post(
        "/api/indexes/some-other-index/docs",
        json={"id": "chunk-1", "text": "some chunk text", "metadata": {"sourceDoc": "example.md"}},
    )

    assert response.status_code == 200
    assert response.json() == {"id": "chunk-1"}

    fake_client.add_docs.assert_awaited_once()
    called_name, called_docs = fake_client.add_docs.await_args.args
    assert called_name == "some-other-index"
    assert len(called_docs) == 1
    doc = called_docs[0]
    assert doc.id == "chunk-1"
    assert doc.text == "some chunk text"
    assert doc.metadata == {"sourceDoc": "example.md"}


def test_update_index_doc_returns_id_on_success(monkeypatch):
    fake_client = SimpleNamespace(
        add_docs=AsyncMock(return_value=None),
        load_index=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.put(
        "/api/indexes/some-other-index/docs/chunk-1",
        json={"text": "updated text", "metadata": {"sourceDoc": "example.md"}},
    )

    assert response.status_code == 200
    assert response.json() == {"id": "chunk-1"}

    fake_client.add_docs.assert_awaited_once()
    called_name, called_docs = fake_client.add_docs.await_args.args
    assert called_name == "some-other-index"
    assert called_docs[0].id == "chunk-1"
    assert called_docs[0].text == "updated text"


def test_delete_index_doc_returns_204_on_success(monkeypatch):
    fake_client = SimpleNamespace(
        delete_docs=AsyncMock(return_value=None),
        load_index=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.delete("/api/indexes/some-other-index/docs/chunk-1")

    assert response.status_code == 204
    assert response.content == b""
    fake_client.delete_docs.assert_awaited_once_with("some-other-index", ["chunk-1"])


def test_add_index_doc_reloads_live_index_when_name_is_protocol_index(monkeypatch):
    fake_client = SimpleNamespace(
        add_docs=AsyncMock(return_value=None),
        load_index=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.post(
        f"/api/indexes/{PROTOCOL_INDEX_NAME}/docs",
        json={"id": "chunk-1", "text": "some text", "metadata": None},
    )

    assert response.status_code == 200
    fake_client.load_index.assert_awaited_once_with(PROTOCOL_INDEX_NAME)


def test_update_index_doc_reloads_live_index_when_name_is_live_data_index(monkeypatch):
    fake_client = SimpleNamespace(
        add_docs=AsyncMock(return_value=None),
        load_index=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.put(
        f"/api/indexes/{LIVE_DATA_INDEX_NAME}/docs/chunk-1",
        json={"text": "updated", "metadata": None},
    )

    assert response.status_code == 200
    fake_client.load_index.assert_awaited_once_with(LIVE_DATA_INDEX_NAME)


def test_delete_index_doc_reloads_live_index_when_name_is_protocol_index(monkeypatch):
    fake_client = SimpleNamespace(
        delete_docs=AsyncMock(return_value=None),
        load_index=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.delete(f"/api/indexes/{PROTOCOL_INDEX_NAME}/docs/chunk-1")

    assert response.status_code == 204
    fake_client.load_index.assert_awaited_once_with(PROTOCOL_INDEX_NAME)


def test_add_index_doc_does_not_reload_when_index_is_not_live_loaded(monkeypatch):
    fake_client = SimpleNamespace(
        add_docs=AsyncMock(return_value=None),
        load_index=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.post(
        "/api/indexes/some-other-index/docs",
        json={"id": "chunk-1", "text": "some text", "metadata": None},
    )

    assert response.status_code == 200
    fake_client.load_index.assert_not_called()


def test_update_index_doc_does_not_reload_when_index_is_not_live_loaded(monkeypatch):
    fake_client = SimpleNamespace(
        add_docs=AsyncMock(return_value=None),
        load_index=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.put(
        "/api/indexes/some-other-index/docs/chunk-1",
        json={"text": "updated", "metadata": None},
    )

    assert response.status_code == 200
    fake_client.load_index.assert_not_called()


def test_delete_index_doc_does_not_reload_when_index_is_not_live_loaded(monkeypatch):
    fake_client = SimpleNamespace(
        delete_docs=AsyncMock(return_value=None),
        load_index=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.delete("/api/indexes/some-other-index/docs/chunk-1")

    assert response.status_code == 204
    fake_client.load_index.assert_not_called()


def test_add_index_doc_rejects_empty_id(monkeypatch):
    fake_client = SimpleNamespace(add_docs=AsyncMock(), load_index=AsyncMock())
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.post(
        "/api/indexes/some-index/docs",
        json={"id": "  ", "text": "some text", "metadata": None},
    )

    assert response.status_code == 422
    fake_client.add_docs.assert_not_called()


def test_add_index_doc_rejects_empty_text(monkeypatch):
    fake_client = SimpleNamespace(add_docs=AsyncMock(), load_index=AsyncMock())
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.post(
        "/api/indexes/some-index/docs",
        json={"id": "chunk-1", "text": "", "metadata": None},
    )

    assert response.status_code == 422
    fake_client.add_docs.assert_not_called()


def test_add_index_doc_rejects_metadata_as_array(monkeypatch):
    fake_client = SimpleNamespace(add_docs=AsyncMock(), load_index=AsyncMock())
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.post(
        "/api/indexes/some-index/docs",
        json={"id": "chunk-1", "text": "some text", "metadata": ["not", "an", "object"]},
    )

    assert response.status_code == 422
    fake_client.add_docs.assert_not_called()


def test_add_index_doc_rejects_metadata_as_string(monkeypatch):
    fake_client = SimpleNamespace(add_docs=AsyncMock(), load_index=AsyncMock())
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.post(
        "/api/indexes/some-index/docs",
        json={"id": "chunk-1", "text": "some text", "metadata": "not an object"},
    )

    assert response.status_code == 422
    fake_client.add_docs.assert_not_called()


def test_add_index_doc_returns_500_without_leaking_details_and_skips_reload(monkeypatch):
    fake_client = SimpleNamespace(
        add_docs=AsyncMock(side_effect=RuntimeError("secret-connection-string-leak")),
        load_index=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)
    response = client.post(
        f"/api/indexes/{PROTOCOL_INDEX_NAME}/docs",
        json={"id": "chunk-1", "text": "some text", "metadata": None},
    )

    assert response.status_code == 500
    assert "secret-connection-string-leak" not in response.text
    fake_client.load_index.assert_not_called()


class _StatefulFakeMossClient:
    """Minimal stateful stand-in for MossClient's add_docs/get_docs, keyed by doc id,
    so upsert-by-id (AC7) can be proven end to end rather than asserted against a
    memoryless mock."""

    def __init__(self):
        self._docs_by_id: dict[str, SimpleNamespace] = {}
        self.load_index = AsyncMock(return_value=None)

    async def add_docs(self, name, docs):
        for doc in docs:
            self._docs_by_id[doc.id] = SimpleNamespace(id=doc.id, text=doc.text, metadata=doc.metadata)

    async def get_index(self, name):
        return _fake_index(name=name)

    async def get_docs(self, name):
        return list(self._docs_by_id.values())


def test_add_index_doc_with_existing_id_upserts_in_place_instead_of_duplicating(monkeypatch):
    fake_client = _StatefulFakeMossClient()
    monkeypatch.setattr(server, "moss_client", fake_client)

    client = TestClient(server.app)

    first = client.post(
        "/api/indexes/some-index/docs",
        json={"id": "x", "text": "first version", "metadata": None},
    )
    assert first.status_code == 200

    docs_after_first = client.get("/api/indexes/some-index/docs").json()
    matching_first = [d for d in docs_after_first if d["id"] == "x"]
    assert len(matching_first) == 1
    assert matching_first[0]["text"] == "first version"

    second = client.post(
        "/api/indexes/some-index/docs",
        json={"id": "x", "text": "second version", "metadata": None},
    )
    assert second.status_code == 200

    docs_after_second = client.get("/api/indexes/some-index/docs").json()
    matching_second = [d for d in docs_after_second if d["id"] == "x"]
    assert len(matching_second) == 1
    assert matching_second[0]["text"] == "second version"
