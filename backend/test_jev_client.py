import asyncio
import logging

import pytest

import jev_client

TRANSCRIPT = "SECRET-CALLER-TEXT my dad is choking"


def _noul(value):
    return {"type": "noul", "noul": value}


def _patients_answer(choice="2", confidence=0.9):
    return {"type": "choice", "choice": choice, "confidence": confidence}


def _full_answers():
    return {
        "weapon": _noul(0.9),
        "unconscious": _noul(0.8),
        "police": _noul(0.7),
        "ems": _noul(0.6),
        "fire": _noul(0.2),
        "patients": _patients_answer("2", 0.98),
    }


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    async def post(self, path, body=None, cast_to=None, options=None):
        self.calls.append({"path": path, "body": body, "cast_to": cast_to, "options": options})
        if self.error is not None:
            raise self.error
        return self.response


def _install(monkeypatch, response=None, error=None):
    client = FakeClient(response=response, error=error)
    monkeypatch.setattr(jev_client, "_get_client", lambda: client)
    return client


def _extract(monkeypatch, answers):
    client = _install(monkeypatch, response={"answers": answers})
    return asyncio.run(jev_client.decide_extraction(TRANSCRIPT)), client


def _follows(monkeypatch, answers, reason=None):
    client = _install(monkeypatch, response={"answers": answers})
    result = asyncio.run(jev_client.decide_follows("chunk text", "reply text", "caller text", reason))
    return result, client


def test_constants_have_specified_values():
    assert jev_client.JEV_CONFIDENCE_HIGH == 0.7
    assert jev_client.JEV_CONFIDENCE_LOW == 0.3
    assert jev_client.JEV_FOLLOW_THRESHOLD == 0.3
    assert jev_client.EXTRACTION_TIMEOUT_S == 1.5
    assert jev_client.JUDGE_TIMEOUT_S == 3.0


def test_both_functions_return_none_when_api_key_unset(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert asyncio.run(jev_client.decide_extraction("text")) is None
    assert asyncio.run(jev_client.decide_follows("a", "b", "c", None)) is None


def test_client_rebuilt_when_key_changes(monkeypatch):
    monkeypatch.setattr(jev_client, "_client", None)
    monkeypatch.setattr(jev_client, "_client_key", None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "key-one")
    first = jev_client._get_client()
    assert jev_client._get_client() is first
    monkeypatch.setenv("OPENROUTER_API_KEY", "key-two")
    second = jev_client._get_client()
    assert second is not first
    monkeypatch.delenv("OPENROUTER_API_KEY")
    assert jev_client._get_client() is None


def test_extraction_request_shape(monkeypatch):
    _, client = _extract(monkeypatch, _full_answers())
    call = client.calls[0]
    assert call["path"] == "/decisions"
    assert call["cast_to"] is dict
    assert call["options"] == {"timeout": 1.5, "max_retries": 0}
    body = call["body"]
    assert body["model"] == "typesafe/jev-1.13"
    assert body["state"]["caller_transcript"] == TRANSCRIPT
    questions = body["questions"]
    assert set(questions) == {"weapon", "unconscious", "police", "ems", "fire", "patients"}
    for field in ("weapon", "unconscious", "police", "ems", "fire"):
        assert questions[field]["type"] == "noul"
    assert questions["patients"]["type"] == "choice"
    assert list(questions["patients"]["criteria"]) == [str(n) for n in range(11)]


def test_extraction_returns_parsed_result_and_patients_tuple(monkeypatch):
    result, _ = _extract(monkeypatch, _full_answers())
    assert result == {
        "weapon": 0.9,
        "unconscious": 0.8,
        "police": 0.7,
        "ems": 0.6,
        "fire": 0.2,
        "patients": ("2", 0.98),
    }
    assert isinstance(result["patients"], tuple)


@pytest.mark.parametrize(
    "bad_answer",
    [
        {"type": "choice", "noul": 0.5},
        {"type": "noul", "noul": 1.5},
        {"type": "noul", "noul": -0.1},
        {"type": "noul", "noul": True},
        {"type": "noul", "noul": "0.5"},
        "not a dict",
        None,
    ],
)
def test_extraction_omits_malformed_noul_but_keeps_others(monkeypatch, bad_answer):
    answers = _full_answers()
    answers["weapon"] = bad_answer
    result, _ = _extract(monkeypatch, answers)
    assert "weapon" not in result
    assert result["police"] == 0.7
    assert result["patients"] == ("2", 0.98)


@pytest.mark.parametrize(
    "bad_answer",
    [
        _patients_answer("11", 0.9),
        _patients_answer("many", 0.9),
        _patients_answer("2", 1.2),
        _patients_answer("2", -0.5),
        _patients_answer("2", True),
        {"type": "noul", "noul": 0.5},
        ["2", 0.9],
    ],
)
def test_extraction_omits_malformed_patients_but_keeps_others(monkeypatch, bad_answer):
    answers = _full_answers()
    answers["patients"] = bad_answer
    result, _ = _extract(monkeypatch, answers)
    assert "patients" not in result
    assert result["weapon"] == 0.9


def test_extraction_returns_empty_dict_when_nothing_usable(monkeypatch):
    result, _ = _extract(monkeypatch, {"weapon": "junk", "patients": {"type": "choice", "choice": "99"}})
    assert result == {}


def test_extraction_returns_empty_dict_for_empty_answers(monkeypatch):
    result, _ = _extract(monkeypatch, {})
    assert result == {}


@pytest.mark.parametrize("error", [asyncio.TimeoutError(), TimeoutError(), RuntimeError("boom")])
def test_extraction_returns_none_on_exception(monkeypatch, error):
    _install(monkeypatch, error=error)
    assert asyncio.run(jev_client.decide_extraction(TRANSCRIPT)) is None


@pytest.mark.parametrize("response", [{}, {"other": 1}, {"answers": "nope"}, {"answers": None}, "text", None, []])
def test_extraction_returns_none_without_answers_object(monkeypatch, response):
    _install(monkeypatch, response=response)
    assert asyncio.run(jev_client.decide_extraction(TRANSCRIPT)) is None


def test_logs_contain_no_transcript_or_key(monkeypatch, caplog):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-super-secret-key")
    _install(monkeypatch, error=RuntimeError(f"failed with {TRANSCRIPT} sk-super-secret-key"))
    with caplog.at_level(logging.DEBUG):
        asyncio.run(jev_client.decide_extraction(TRANSCRIPT))
        _install(monkeypatch, response={})
        asyncio.run(jev_client.decide_extraction(TRANSCRIPT))
    assert caplog.records
    logged = caplog.text
    assert "SECRET-CALLER-TEXT" not in logged
    assert "sk-super-secret-key" not in logged


def test_follows_request_shape_and_optional_reason(monkeypatch):
    _, client = _follows(monkeypatch, {"follows_protocol": _noul(0.9)}, reason=None)
    call = client.calls[0]
    assert call["path"] == "/decisions"
    assert call["options"] == {"timeout": 3.0, "max_retries": 0}
    assert call["body"]["model"] == "typesafe/jev-1.13"
    assert call["body"]["state"] == {
        "caller_transcript": "caller text",
        "protocol_instruction": "chunk text",
        "dispatcher_reply": "reply text",
    }
    assert set(call["body"]["questions"]) == {"follows_protocol"}
    assert call["body"]["questions"]["follows_protocol"]["type"] == "noul"

    _, client = _follows(monkeypatch, {"follows_protocol": _noul(0.9)}, reason="he looks thirsty")
    assert client.calls[0]["body"]["state"]["dispatcher_reason"] == "he looks thirsty"


def test_follows_returns_float_probability(monkeypatch):
    result, _ = _follows(monkeypatch, {"follows_protocol": _noul(1)})
    assert result == 1.0
    assert isinstance(result, float)


@pytest.mark.parametrize(
    "answer",
    [_noul(2), _noul(True), _noul("x"), {"type": "choice", "noul": 0.5}, "bad", None],
)
def test_follows_returns_none_for_malformed_answer(monkeypatch, answer):
    result, _ = _follows(monkeypatch, {"follows_protocol": answer})
    assert result is None


def test_follows_returns_none_on_exception_and_missing_answers(monkeypatch):
    _install(monkeypatch, error=RuntimeError("boom"))
    assert asyncio.run(jev_client.decide_follows("a", "b", "c", None)) is None
    _install(monkeypatch, response={"nope": 1})
    assert asyncio.run(jev_client.decide_follows("a", "b", "c", None)) is None


def test_cancelled_error_propagates(monkeypatch):
    _install(monkeypatch, error=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(jev_client.decide_extraction(TRANSCRIPT))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(jev_client.decide_follows("a", "b", "c", None))
