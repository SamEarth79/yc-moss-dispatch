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
    assert {k: v for k, v in result.items() if k != "devLog"} == {"verdict": "followed", "deviationSummary": ""}
    kwargs = create.await_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["max_tokens"] == 200


def test_judge_returns_deviated_with_trimmed_summary(monkeypatch):
    result, _ = _judge(monkeypatch, json.dumps({"verdict": "deviated", "deviationSummary": "  Gave water.  "}))
    assert {k: v for k, v in result.items() if k != "devLog"} == {"verdict": "deviated", "deviationSummary": "Gave water."}


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


DEVIATED = {"verdict": "deviated", "deviationSummary": "Advised water instead of thrusts.", "devLog": []}


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
    fake, _ = _setup(monkeypatch, {"verdict": "followed", "deviationSummary": "", "devLog": []})
    response = _post()
    assert response.status_code == 200
    assert response.json() == {"verdict": "followed", "devLog": []}
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


def _stub_jev(monkeypatch, probability):
    decide = AsyncMock(return_value=probability)
    monkeypatch.setattr(deviation_judge, "decide_follows", decide)
    return decide


def _judge_with_jev(monkeypatch, probability, content=None, reason=None):
    decide = _stub_jev(monkeypatch, probability)
    client, create = _fake_llm(content)
    monkeypatch.setattr(deviation_judge, "_get_client", lambda: client)
    result = asyncio.run(deviation_judge.judge_deviation("the reply", reason, "the chunk", "the transcript"))
    return result, create, decide


SUMMARY_JSON = json.dumps({"deviationSummary": "  Advised water instead of thrusts.  "})


def test_jev_above_threshold_is_followed_without_deepseek(monkeypatch):
    result, create, decide = _judge_with_jev(monkeypatch, 0.87)
    assert {k: v for k, v in result.items() if k != "devLog"} == {"verdict": "followed", "deviationSummary": ""}
    create.assert_not_awaited()
    decide.assert_awaited_once()


def test_jev_below_threshold_is_deviated_with_summary_only_call(monkeypatch):
    result, create, _ = _judge_with_jev(monkeypatch, 0.01, SUMMARY_JSON)
    assert {k: v for k, v in result.items() if k != "devLog"} == {"verdict": "deviated", "deviationSummary": "Advised water instead of thrusts."}
    create.assert_awaited_once()
    messages = create.await_args.kwargs["messages"]
    assert messages[0]["content"] == deviation_judge.SUMMARY_SYSTEM_PROMPT
    assert "the chunk" in messages[1]["content"]
    assert "the reply" in messages[1]["content"]
    assert create.await_args.kwargs["max_tokens"] == 150


def test_threshold_boundary_is_followed(monkeypatch):
    result, create, _ = _judge_with_jev(monkeypatch, deviation_judge.JEV_FOLLOW_THRESHOLD)
    assert result["verdict"] == "followed"
    create.assert_not_awaited()


def test_just_below_threshold_is_deviated(monkeypatch):
    result, create, _ = _judge_with_jev(monkeypatch, 0.29, SUMMARY_JSON)
    assert result["verdict"] == "deviated"
    create.assert_awaited_once()


def test_grey_zone_is_followed(monkeypatch):
    result, create, _ = _judge_with_jev(monkeypatch, 0.4)
    assert result["verdict"] == "followed"
    create.assert_not_awaited()


def test_jev_none_uses_full_deepseek_path_unchanged(monkeypatch):
    content = json.dumps({"verdict": "deviated", "deviationSummary": "  Gave water.  "})
    result, create, _ = _judge_with_jev(monkeypatch, None, content)
    assert {k: v for k, v in result.items() if k != "devLog"} == {"verdict": "deviated", "deviationSummary": "Gave water."}
    kwargs = create.await_args.kwargs
    assert kwargs["messages"][0]["content"] == deviation_judge.SYSTEM_PROMPT
    assert "Caller transcript: the transcript" in kwargs["messages"][1]["content"]
    assert kwargs["max_tokens"] == 200


@pytest.mark.parametrize(
    "content",
    ["", None, "not json at all", json.dumps({}), json.dumps({"deviationSummary": ""}), json.dumps({"deviationSummary": "  "}), json.dumps({"deviationSummary": 5})],
)
def test_deviated_with_invalid_summary_raises(monkeypatch, content):
    _stub_jev(monkeypatch, 0.05)
    client, _ = _fake_llm(content)
    monkeypatch.setattr(deviation_judge, "_get_client", lambda: client)
    with pytest.raises(ValueError):
        asyncio.run(deviation_judge.judge_deviation("a", None, "b", "c"))


def test_deviated_without_deepseek_configured_returns_none(monkeypatch):
    _stub_jev(monkeypatch, 0.05)
    monkeypatch.setattr(deviation_judge, "_get_client", lambda: None)
    assert asyncio.run(deviation_judge.judge_deviation("a", None, "b", "c")) is None


def test_reason_and_texts_are_passed_to_decide_follows(monkeypatch):
    _, _, decide = _judge_with_jev(monkeypatch, 0.9, reason="because")
    decide.assert_awaited_once_with("the chunk", "the reply", "the transcript", "because")


def test_summary_prompt_includes_reason_only_when_given(monkeypatch):
    _, create, _ = _judge_with_jev(monkeypatch, 0.0, SUMMARY_JSON, reason="because")
    assert "because" in create.await_args.kwargs["messages"][1]["content"]
    _, create, _ = _judge_with_jev(monkeypatch, 0.0, SUMMARY_JSON)
    assert "stated reason" not in create.await_args.kwargs["messages"][1]["content"]


def test_summary_prompt_excludes_caller_transcript(monkeypatch):
    _, create, _ = _judge_with_jev(monkeypatch, 0.0, SUMMARY_JSON)
    assert "the transcript" not in create.await_args.kwargs["messages"][1]["content"]


@pytest.mark.parametrize(
    "probability, content, source, verdict",
    [
        (0.87, None, "source=jev", "verdict=followed"),
        (0.01, SUMMARY_JSON, "source=jev", "verdict=deviated"),
        (None, json.dumps({"verdict": "followed"}), "source=deepseek-fallback", "verdict=followed"),
    ],
)
def test_logs_source_verdict_and_probability_without_text(monkeypatch, caplog, probability, content, source, verdict):
    caplog.set_level("INFO", logger="deviation_judge")
    _judge_with_jev(monkeypatch, probability, content)
    lines = [r.getMessage() for r in caplog.records if r.name == "deviation_judge"]
    assert len(lines) == 1
    assert source in lines[0] and verdict in lines[0]
    if probability is not None:
        assert f"p_follows={probability:.3f}" in lines[0]
    for text in ("the reply", "the transcript", "the chunk", "Advised water"):
        assert text not in lines[0]


def _setup_with_jev(monkeypatch, probability, content=None):
    fake, _ = _setup(monkeypatch, None)
    monkeypatch.setattr(server, "judge_deviation", deviation_judge.judge_deviation)
    _stub_jev(monkeypatch, probability)
    client, create = _fake_llm(content)
    monkeypatch.setattr(deviation_judge, "_get_client", lambda: client)
    return fake, create


def test_endpoint_jev_followed_writes_nothing_and_contract_unchanged(monkeypatch):
    fake, create = _setup_with_jev(monkeypatch, 0.87)
    response = _post()
    assert response.status_code == 200
    assert set(response.json()) == {"verdict", "devLog"}
    assert response.json()["verdict"] == "followed"
    create.assert_not_awaited()
    fake.add_docs.assert_not_awaited()
    fake.create_index.assert_not_awaited()


def test_endpoint_jev_deviated_writes_one_doc_with_jev_summary(monkeypatch):
    fake, create = _setup_with_jev(monkeypatch, 0.01, json.dumps({"deviationSummary": "Advised water instead of thrusts."}))
    response = _post()
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"verdict", "deviationSummary", "id", "retrievable", "devLog"}
    assert data["verdict"] == "deviated"
    assert data["deviationSummary"] == "Advised water instead of thrusts."
    create.assert_awaited_once()
    fake.add_docs.assert_awaited_once()
    docs = fake.add_docs.await_args.args[1]
    assert len(docs) == 1
    assert docs[0].metadata["deviationSummary"] == "Advised water instead of thrusts."


def test_endpoint_jev_deviated_without_deepseek_returns_503(monkeypatch):
    fake, _ = _setup_with_jev(monkeypatch, 0.01)
    monkeypatch.setattr(deviation_judge, "_get_client", lambda: None)
    response = _post()
    assert response.status_code == 503
    assert response.json()["detail"] == "LLM not configured"
    fake.add_docs.assert_not_awaited()


REPLY_TEXT = "the reply"
CHUNK_TEXT = "the chunk"
TRANSCRIPT_TEXT = "the transcript"


def _dev_log(monkeypatch, probability, content=None):
    result, _, _ = _judge_with_jev(monkeypatch, probability, content)
    return result["devLog"]


def test_devlog_jev_followed_entry(monkeypatch):
    log = _dev_log(monkeypatch, 0.87)
    assert len(log) == 1
    entry = log[0]
    assert set(entry) == {"service", "callType", "latencyMs", "summary"}
    assert entry["service"] == "jev" and entry["callType"] == "verdict"
    assert entry["summary"] == "P(follows)=0.87 → followed"
    assert isinstance(entry["latencyMs"], float) and entry["latencyMs"] >= 0


def test_devlog_jev_deviated_entry(monkeypatch):
    log = _dev_log(monkeypatch, 0.12, SUMMARY_JSON)
    assert len(log) == 1
    assert log[0]["service"] == "jev" and log[0]["callType"] == "verdict"
    assert log[0]["summary"] == "P(follows)=0.12 → deviated"


def test_devlog_probability_formatted_to_two_decimals(monkeypatch):
    assert _dev_log(monkeypatch, 0.8712345)[0]["summary"] == "P(follows)=0.87 → followed"


def test_devlog_fallback_entry_with_measured_latency(monkeypatch):
    log = _dev_log(monkeypatch, None, json.dumps({"verdict": "followed"}))
    assert len(log) == 1
    assert log[0]["service"] == "jev" and log[0]["callType"] == "verdict"
    assert log[0]["summary"] == "skipped (unavailable), DeepSeek fallback"
    latency = log[0]["latencyMs"]
    assert latency >= 0
    assert latency == round(latency, 1)


def test_devlog_latency_is_measured_around_jev_call(monkeypatch):
    async def slow_decide(*args):
        await asyncio.sleep(0.05)
        return 0.9

    monkeypatch.setattr(deviation_judge, "decide_follows", slow_decide)
    result = asyncio.run(deviation_judge.judge_deviation("a", None, "b", "c"))
    assert result["devLog"][0]["latencyMs"] >= 40


@pytest.mark.parametrize(
    "probability, content",
    [
        (0.87, None),
        (0.01, json.dumps({"deviationSummary": "Advised water instead of thrusts."})),
        (None, json.dumps({"verdict": "deviated", "deviationSummary": "Gave water."})),
    ],
)
def test_devlog_contains_no_transcript_reply_or_chunk_text(monkeypatch, probability, content):
    decide = _stub_jev(monkeypatch, probability)
    client, _ = _fake_llm(content)
    monkeypatch.setattr(deviation_judge, "_get_client", lambda: client)
    result = asyncio.run(
        deviation_judge.judge_deviation(
            "SECRET-REPLY-TEXT", "SECRET-REASON", "SECRET-CHUNK-TEXT", "SECRET-TRANSCRIPT-TEXT"
        )
    )
    dumped = json.dumps(result["devLog"])
    for text in ("SECRET-REPLY-TEXT", "SECRET-REASON", "SECRET-CHUNK-TEXT", "SECRET-TRANSCRIPT-TEXT"):
        assert text not in dumped
    assert "Gave water" not in dumped and "Advised water" not in dumped
    decide.assert_awaited_once()


def test_devlog_threshold_boundary_is_followed_entry(monkeypatch):
    log = _dev_log(monkeypatch, deviation_judge.JEV_FOLLOW_THRESHOLD)
    assert log[0]["summary"] == "P(follows)=0.30 → followed"


def test_judge_still_returns_none_without_deepseek_after_fallback(monkeypatch):
    _stub_jev(monkeypatch, None)
    monkeypatch.setattr(deviation_judge, "_get_client", lambda: None)
    assert asyncio.run(deviation_judge.judge_deviation("a", None, "b", "c")) is None


def test_endpoint_followed_response_keys_and_devlog_passthrough(monkeypatch):
    _setup_with_jev(monkeypatch, 0.87)
    data = _post().json()
    assert set(data) == {"verdict", "devLog"}
    assert data["devLog"][0]["service"] == "jev"
    assert data["devLog"][0]["summary"] == "P(follows)=0.87 → followed"


def test_endpoint_deviated_response_keys_and_devlog_passthrough(monkeypatch):
    _setup_with_jev(monkeypatch, 0.12, SUMMARY_JSON)
    data = _post().json()
    assert set(data) == {"verdict", "deviationSummary", "id", "retrievable", "devLog"}
    assert data["devLog"][0]["summary"] == "P(follows)=0.12 → deviated"


def test_endpoint_fallback_devlog_visible(monkeypatch):
    _setup_with_jev(monkeypatch, None, json.dumps({"verdict": "followed"}))
    data = _post().json()
    assert data["verdict"] == "followed"
    assert data["devLog"][0]["summary"] == "skipped (unavailable), DeepSeek fallback"


def test_endpoint_503_has_no_devlog(monkeypatch):
    _setup(monkeypatch, None)
    response = _post()
    assert response.status_code == 503
    assert "devLog" not in response.json()


@pytest.mark.parametrize("error", [ValueError("x"), RuntimeError("y")])
def test_endpoint_502_has_no_devlog(monkeypatch, error):
    _setup(monkeypatch, error)
    response = _post()
    assert response.status_code == 502
    assert "devLog" not in response.json()


def test_endpoint_500_has_no_devlog(monkeypatch):
    _setup(monkeypatch, DEVIATED, add_docs=AsyncMock(side_effect=RuntimeError("boom")))
    response = _post()
    assert response.status_code == 500
    assert "devLog" not in response.json()


def test_stored_document_unaffected_by_devlog(monkeypatch):
    log = [{"service": "jev", "callType": "verdict", "latencyMs": 1.0, "summary": "MARKER-DEVLOG"}]
    fake, _ = _setup(monkeypatch, {**DEVIATED, "devLog": log})
    assert _post().status_code == 200
    doc = fake.add_docs.await_args.args[1][0]
    assert "MARKER-DEVLOG" not in doc.text
    assert "MARKER-DEVLOG" not in json.dumps(doc.metadata)
    assert "devLog" not in doc.metadata
