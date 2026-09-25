import asyncio
import json
import re
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.testclient import TestClient

import deviation_judge
import server
from live_panel import DEVIATION_INDEX_NAME

VALID_BODY = {
    "dispatcherText": "Give him some water",
    "reason": "he looks thirsty",
    "protocolChunkId": "choking-1",
    "protocolChunkText": "Perform back blows and abdominal thrusts.",
    "callerTranscript": "my dad is choking and cannot breathe",
    "callerSummary": {"whatHappened": "Adult choking", "extra": "x"},
}


def _fake_llm(content):
    create = AsyncMock(
        return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return client, create


def _judge(monkeypatch, content):
    client, create = _fake_llm(content)
    monkeypatch.setattr(deviation_judge, "_get_client", lambda: client)
    result = asyncio.run(deviation_judge.judge_deviation("reply", None, "chunk", "transcript"))
    return result, create


def test_judge_returns_none_when_llm_not_configured(monkeypatch):
    monkeypatch.setattr(deviation_judge, "_get_client", lambda: None)
    assert asyncio.run(deviation_judge.judge_deviation("a", None, "b", "c")) is None


def test_judge_returns_followed_with_empty_summary(monkeypatch):
    result, create = _judge(monkeypatch, json.dumps({"verdict": "followed", "deviationSummary": "ignored"}))
    assert result == {"verdict": "followed", "deviationSummary": ""}
    kwargs = create.await_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["max_tokens"] == 200


def test_judge_returns_deviated_with_trimmed_summary(monkeypatch):
    result, _ = _judge(monkeypatch, json.dumps({"verdict": "deviated", "deviationSummary": "  Gave water.  "}))
    assert result == {"verdict": "deviated", "deviationSummary": "Gave water."}


def test_judge_includes_reason_in_prompt_only_when_given(monkeypatch):
    client, create = _fake_llm(json.dumps({"verdict": "followed"}))
    monkeypatch.setattr(deviation_judge, "_get_client", lambda: client)
    asyncio.run(deviation_judge.judge_deviation("reply", "because", "chunk", "t"))
    asyncio.run(deviation_judge.judge_deviation("reply", None, "chunk", "t"))
    with_reason = create.await_args_list[0].kwargs["messages"][1]["content"]
    without_reason = create.await_args_list[1].kwargs["messages"][1]["content"]
    assert "because" in with_reason
    assert "stated reason" not in without_reason


@pytest.mark.parametrize(
    "content",
    [
        json.dumps({"verdict": "maybe", "deviationSummary": "x"}),
        json.dumps({"deviationSummary": "x"}),
        "",
        None,
        "not json at all",
        json.dumps({"verdict": "deviated", "deviationSummary": ""}),
        json.dumps({"verdict": "deviated", "deviationSummary": "   "}),
        json.dumps({"verdict": "deviated"}),
    ],
)
def test_judge_raises_on_bad_output(monkeypatch, content):
    client, _ = _fake_llm(content)
    monkeypatch.setattr(deviation_judge, "_get_client", lambda: client)
    with pytest.raises(ValueError):
        asyncio.run(deviation_judge.judge_deviation("a", None, "b", "c"))


def _setup(monkeypatch, verdict, indexes=(DEVIATION_INDEX_NAME,), **overrides):
    fake = SimpleNamespace(
        list_indexes=AsyncMock(return_value=[SimpleNamespace(name=name) for name in indexes]),
        add_docs=AsyncMock(),
        create_index=AsyncMock(),
        load_index=AsyncMock(),
    )
    for name, value in overrides.items():
        setattr(fake, name, value)
    if isinstance(verdict, Exception):
        judge = AsyncMock(side_effect=verdict)
    else:
        judge = AsyncMock(return_value=verdict)
    monkeypatch.setattr(server, "moss_client", fake)
    monkeypatch.setattr(server, "judge_deviation", judge)
    return fake, judge


def _post(**changes):
    body = {**VALID_BODY, **changes}
    return TestClient(server.app).post("/api/deviations/judge", json=body)


DEVIATED = {"verdict": "deviated", "deviationSummary": "Advised water instead of thrusts."}


@pytest.mark.parametrize(
    "changes",
    [
        {"dispatcherText": ""},
        {"dispatcherText": "   "},
        {"protocolChunkId": ""},
        {"protocolChunkText": ""},
        {"callerTranscript": " "},
        {"dispatcherText": "x" * 2001},
        {"reason": "x" * 501},
        {"protocolChunkId": "x" * 201},
        {"protocolChunkText": "x" * 4001},
        {"callerTranscript": "x" * 10001},
    ],
)
def test_invalid_body_returns_422_and_skips_judge(monkeypatch, changes):
    fake, judge = _setup(monkeypatch, DEVIATED)
    assert _post(**changes).status_code == 422
    judge.assert_not_awaited()
    fake.add_docs.assert_not_awaited()


def test_missing_field_returns_422(monkeypatch):
    _setup(monkeypatch, DEVIATED)
    body = {k: v for k, v in VALID_BODY.items() if k != "callerTranscript"}
    assert TestClient(server.app).post("/api/deviations/judge", json=body).status_code == 422


def test_llm_not_configured_returns_503_and_writes_nothing(monkeypatch):
    fake, _ = _setup(monkeypatch, None)
    response = _post()
    assert response.status_code == 503
    assert response.json()["detail"] == "LLM not configured"
    fake.add_docs.assert_not_awaited()
    fake.create_index.assert_not_awaited()


@pytest.mark.parametrize("error", [ValueError("bad output"), RuntimeError("provider secret sk-123 stack")])
def test_judge_error_returns_502_without_leak_and_writes_nothing(monkeypatch, error):
    fake, _ = _setup(monkeypatch, error)
    response = _post()
    assert response.status_code == 502
    assert response.json()["detail"] == "Could not judge response"
    assert "sk-123" not in response.text and "Traceback" not in response.text
    fake.add_docs.assert_not_awaited()
    fake.create_index.assert_not_awaited()


def test_followed_returns_verdict_only_and_writes_nothing(monkeypatch):
    fake, _ = _setup(monkeypatch, {"verdict": "followed", "deviationSummary": ""})
    response = _post()
    assert response.status_code == 200
    assert response.json() == {"verdict": "followed"}
    fake.add_docs.assert_not_awaited()
    fake.create_index.assert_not_awaited()
    fake.load_index.assert_not_awaited()


def test_deviated_writes_one_document_with_expected_shape(monkeypatch):
    fake, _ = _setup(monkeypatch, DEVIATED)
    response = _post(reason=None)
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "deviated"
    assert data["deviationSummary"] == DEVIATED["deviationSummary"]
    assert data["retrievable"] is True
    assert re.fullmatch(r"dev-[0-9a-f]{32}", data["id"])

    fake.add_docs.assert_awaited_once()
    index_name, docs = fake.add_docs.await_args.args
    assert index_name == DEVIATION_INDEX_NAME
    assert len(docs) == 1
    doc = docs[0]
    assert doc.id == data["id"]
    situation, summary = doc.text.split("\n")
    assert situation.startswith("Adult choking")
    assert summary == DEVIATED["deviationSummary"]
    for key, value in doc.metadata.items():
        assert isinstance(key, str) and isinstance(value, str), key
    assert doc.metadata["type"] == "deviation"
    assert doc.metadata["reason"] == ""
    assert doc.metadata["protocolChunkId"] == VALID_BODY["protocolChunkId"]
    assert doc.metadata["dispatcherTranscript"] == VALID_BODY["dispatcherText"]
    assert doc.metadata["deviationSummary"] == DEVIATED["deviationSummary"]
    assert doc.metadata["seed"] == "false"
    assert json.loads(doc.metadata["callerSummary"])["whatHappened"] == "Adult choking"
    parsed = datetime.strptime(doc.metadata["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
    assert parsed.year >= 2026
    fake.create_index.assert_not_awaited()


def test_deviated_stores_reason_when_given(monkeypatch):
    fake, _ = _setup(monkeypatch, DEVIATED)
    _post()
    assert fake.add_docs.await_args.args[1][0].metadata["reason"] == "he looks thirsty"


def test_situation_is_transcript_tail_without_summary(monkeypatch):
    fake, _ = _setup(monkeypatch, DEVIATED)
    _post(callerSummary=None)
    text = fake.add_docs.await_args.args[1][0].text
    assert text.startswith("my dad is choking")
    assert json.loads(fake.add_docs.await_args.args[1][0].metadata["callerSummary"]) == {}


def test_creates_index_when_missing(monkeypatch):
    fake, _ = _setup(monkeypatch, DEVIATED, indexes=("other-index",))
    assert _post().status_code == 200
    fake.create_index.assert_awaited_once()
    name, docs = fake.create_index.await_args.args
    assert name == DEVIATION_INDEX_NAME and len(docs) == 1
    fake.add_docs.assert_not_awaited()


def test_adds_docs_when_index_present(monkeypatch):
    fake, _ = _setup(monkeypatch, DEVIATED)
    _post()
    fake.add_docs.assert_awaited_once()
    fake.create_index.assert_not_awaited()


def test_index_reloaded_after_write(monkeypatch):
    fake, _ = _setup(monkeypatch, DEVIATED)
    _post()
    fake.load_index.assert_awaited_once_with(DEVIATION_INDEX_NAME)


def test_retrievable_false_when_reload_fails(monkeypatch):
    fake, _ = _setup(monkeypatch, DEVIATED, load_index=AsyncMock(side_effect=RuntimeError("reload boom")))
    response = _post()
    assert response.status_code == 200
    assert response.json()["retrievable"] is False
    assert "reload boom" not in response.text


@pytest.mark.parametrize("failing", ["add_docs", "create_index", "list_indexes"])
def test_write_failure_returns_500_without_leak(monkeypatch, failing):
    indexes = ("other-index",) if failing == "create_index" else (DEVIATION_INDEX_NAME,)
    fake, _ = _setup(monkeypatch, DEVIATED, indexes=indexes, **{failing: AsyncMock(side_effect=RuntimeError("moss secret key-9"))})
    response = _post()
    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to save deviation"
    assert "key-9" not in response.text and "Traceback" not in response.text
    fake.load_index.assert_not_awaited()
