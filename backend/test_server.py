from types import SimpleNamespace
from unittest.mock import AsyncMock

from starlette.testclient import TestClient

import server


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
