import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.testclient import TestClient

import server
from live_panel import PROTOCOL_INDEX_NAME

MAX_MESSAGES = 80
POLL_TIMEOUT_S = 5.0


class _Moss:
    async def query(self, index, text, options):
        doc = SimpleNamespace(id="choking-1", text="Back blows.", score=0.9, metadata={"priority": "high", "suggestedAction": "EMS"})
        return SimpleNamespace(docs=[doc] if index == PROTOCOL_INDEX_NAME else [], time_taken_ms=1.0)


class FakeJev:
    """Stands in for server.decide_extraction. Answers are chosen by call index; a call
    whose gate is unset blocks (in flight) until the test releases it."""

    def __init__(self, answers=None):
        self.answers = answers or []
        self.calls = []
        self.starts = []
        self.gates = {}

    def hold(self, index):
        self.gates[index] = threading.Event()
        return self.gates[index]

    async def __call__(self, text):
        import asyncio

        index = len(self.calls)
        self.calls.append(text)
        self.starts.append(time.monotonic())
        gate = self.gates.get(index)
        while gate is not None and not gate.is_set():
            await asyncio.sleep(0.005)
        return self.answers[index] if index < len(self.answers) else None


def _setup(monkeypatch, fake_jev, settle=0.02, gap=0.02, headline="Headline"):
    monkeypatch.setattr(server, "moss_client", _Moss())
    monkeypatch.setattr(server, "extract_llm_fields", AsyncMock(return_value={"whatHappened": headline}))
    monkeypatch.setattr(server, "decide_extraction", fake_jev)
    monkeypatch.setattr(server, "JEV_SETTLE_DELAY_S", settle)
    monkeypatch.setattr(server, "JEV_MIN_GAP_S", gap)

    async def caller_context(address, lat, lon, county, websocket, send_lock):
        return {"type": "caller_context", "address": address}

    monkeypatch.setattr(server, "caller_context_payload", caller_context)


def _until(ws, predicate):
    seen = []
    for _ in range(MAX_MESSAGES):
        message = ws.receive_json()
        seen.append(message)
        if predicate(message):
            return seen
    raise AssertionError(f"predicate never matched; saw {seen}")


def _is_dev(message, service, call_type=None):
    return message["type"] == "dev_log" and message["service"] == service and (call_type is None or message["callType"] == call_type)


def _updates(messages):
    return [m["fields"] for m in messages if m["type"] == "extraction_update"]


def _send(ws, text):
    ws.send_json({"type": "transcript", "text": text})


def _settle_transcript(ws, text):
    """Sends a transcript and reads through its Jev dev line (Jev call must be ungated)."""
    _send(ws, text)
    return _until(ws, lambda m: _is_dev(m, "jev", "decisions") and m["type"] == "dev_log")


def _through_rule_and_llm(ws, text):
    """Sends a transcript and reads through the rule update and the DeepSeek dev line
    (Jev call may still be pending)."""
    _send(ws, text)
    return _until(ws, lambda m: _is_dev(m, "llm", "extraction"))


def _wait_for_calls(fake, count):
    deadline = time.monotonic() + POLL_TIMEOUT_S
    while len(fake.calls) < count:
        assert time.monotonic() < deadline, f"expected {count} Jev calls, saw {len(fake.calls)}"
        time.sleep(0.005)


WEAPON_YES = {"weapon": 0.95}
WEAPON_NO = {"weapon": 0.05}
WEAPON_UNSURE = {"weapon": 0.5}


def test_override_arrives_as_second_extraction_update_with_sources_and_dev_line(monkeypatch):
    fake = FakeJev([{"weapon": 0.95, "unconscious": 0.5}])
    _setup(monkeypatch, fake)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        seen = _settle_transcript(ws, "my dad is hurt")
    updates = _updates(seen)
    rule_only, llm_update, jev_update = updates
    assert rule_only["weapons"] is None and rule_only["sources"] == {}
    assert llm_update["whatHappened"] == "Headline" and llm_update["sources"] == {}
    assert jev_update["weapons"] is True
    assert jev_update["sources"] == {"weapons": "jev"}
    assert jev_update["whatHappened"] == "Headline"
    dev = [m for m in seen if _is_dev(m, "jev", "decisions")][-1]
    assert dev["summary"] == "6 checked, 1 overridden (weapons: unknown→yes)"
    assert isinstance(dev["latencyMs"], float)


def test_summary_reports_no_to_yes_when_rule_said_no(monkeypatch):
    fake = FakeJev([WEAPON_YES])
    _setup(monkeypatch, fake)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        seen = _settle_transcript(ws, "there was no weapon")
    dev = [m for m in seen if _is_dev(m, "jev", "decisions")][-1]
    assert dev["summary"] == "6 checked, 1 overridden (weapons: no→yes)"
    assert _updates(seen)[0]["weapons"] is False
    assert _updates(seen)[-1]["weapons"] is True


def test_extraction_update_shape_for_existing_keys_plus_sources(monkeypatch):
    fake = FakeJev([WEAPON_YES])
    _setup(monkeypatch, fake)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        seen = _settle_transcript(ws, "my dad is hurt")
    for fields in _updates(seen):
        assert set(fields) == {"numberOfPatients", "consciousness", "weapons", "departments", "whatHappened", "sources"}
    assert _updates(seen)[0]["numberOfPatients"] == 1


def test_jev_summary_lists_multiple_overrides_and_departments(monkeypatch):
    fake = FakeJev([{"weapon": 0.9, "unconscious": 0.9, "patients": (2, 0.9), "police": 0.9, "ems": 0.5, "fire": 0.5}])
    _setup(monkeypatch, fake)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        seen = _settle_transcript(ws, "my dad is hurt")
    summary = [m for m in seen if _is_dev(m, "jev", "decisions")][-1]["summary"]
    assert summary.startswith("6 checked, 4 overridden (")
    for piece in ("weapons: unknown→yes", "consciousness: unknown→unconscious", "numberOfPatients: 1→2", "departments:"):
        assert piece in summary
    assert _updates(seen)[-1]["sources"] == {
        "weapons": "jev", "consciousness": "jev", "numberOfPatients": "jev", "departments": "jev"
    }


def test_fallback_sends_only_dev_line_and_no_extra_update(monkeypatch):
    fake = FakeJev([None])
    _setup(monkeypatch, fake)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        seen = _settle_transcript(ws, "my dad is hurt")
        # the DeepSeek update and dev line may arrive on either side of the Jev line
        if not any(_is_dev(m, "llm", "extraction") for m in seen):
            seen += _until(ws, lambda m: _is_dev(m, "llm", "extraction"))
    jev_lines = [m for m in seen if _is_dev(m, "jev", "decisions")]
    assert [m["summary"] for m in jev_lines] == ["skipped (unavailable), rule values kept"]
    updates = _updates(seen)
    assert len(updates) == 2
    assert all(u["weapons"] is None and u["sources"] == {} for u in updates)


def test_confident_override_is_sticky_on_next_transcripts_rule_only_update(monkeypatch):
    fake = FakeJev([WEAPON_YES, WEAPON_UNSURE])
    _setup(monkeypatch, fake)
    fake_gate = fake.hold(1)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        _settle_transcript(ws, "my dad is hurt")
        seen = _through_rule_and_llm(ws, "my dad is hurt badly")
        rule_only = _updates(seen)[0]
        assert rule_only["weapons"] is True
        assert rule_only["sources"] == {"weapons": "jev"}
        _wait_for_calls(fake, 2)
        fake_gate.set()
        after = _until(ws, lambda m: _is_dev(m, "jev", "decisions"))
    assert _updates(after)[-1]["weapons"] is True
    assert _updates(after)[-1]["sources"] == {"weapons": "jev"}


def test_uncertain_later_answer_keeps_sticky_value(monkeypatch):
    fake = FakeJev([WEAPON_YES, WEAPON_UNSURE])
    _setup(monkeypatch, fake)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        _settle_transcript(ws, "my dad is hurt")
        seen = _settle_transcript(ws, "my dad is hurt badly")
    last = _updates(seen)[-1]
    assert last["weapons"] is True and last["sources"] == {"weapons": "jev"}


def test_newer_confident_answer_replaces_sticky_value(monkeypatch):
    fake = FakeJev([{"weapon": 0.95, "unconscious": 0.95}, {"unconscious": 0.05}])
    _setup(monkeypatch, fake)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        first = _settle_transcript(ws, "my dad is hurt")
        assert _updates(first)[-1]["consciousness"] == "unconscious"
        second = _settle_transcript(ws, "my dad is hurt and talking")
    last = _updates(second)[-1]
    assert last["consciousness"] == "conscious"
    assert last["weapons"] is True
    assert last["sources"]["weapons"] == "jev"


@pytest.mark.parametrize(
    "first_text, second_text, first, second, field, rule_value",
    [
        ("my dad is hurt", "there was no weapon", {"weapon": 0.95}, {"weapon": 0.05}, "weapons", False),
        ("my dad is hurt", "he is awake", {"unconscious": 0.95}, {"unconscious": 0.05}, "consciousness", "conscious"),
        ("my dad is hurt", "two people are hurt", {"patients": (3, 0.9)}, {"patients": (2, 0.9)}, "numberOfPatients", 2),
        ("my dad is hurt", "there is a fire", {"police": 0.95}, {"police": 0.05}, "departments", ["Fire"]),
    ],
)
def test_confident_agreement_with_rule_clears_sticky_state(monkeypatch, first_text, second_text, first, second, field, rule_value):
    fake = FakeJev([first, second])
    _setup(monkeypatch, fake)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        first_seen = _settle_transcript(ws, first_text)
        assert field in _updates(first_seen)[-1]["sources"]
        second_seen = _settle_transcript(ws, second_text)
        last = _updates(second_seen)[-1]
        assert field not in last["sources"]
        assert last[field] == rule_value
        third = _through_rule_and_llm(ws, second_text + " again")
    assert field not in _updates(third)[0]["sources"]
    assert _updates(third)[0][field] == rule_value


def test_rule_flip_then_confident_agreement_clears_sticky_weapons(monkeypatch):
    fake = FakeJev([WEAPON_YES, WEAPON_NO, None])
    _setup(monkeypatch, fake)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        _settle_transcript(ws, "my dad is hurt")
        seen = _settle_transcript(ws, "there was no weapon")
        last = _updates(seen)[-1]
        assert last["weapons"] is False
        assert "weapons" not in last["sources"]
        later = _through_rule_and_llm(ws, "there was no weapon at all")
    assert _updates(later)[0]["weapons"] is False
    assert "weapons" not in _updates(later)[0]["sources"]


def test_empty_transcript_resets_sticky_state_and_cancels_in_flight_jev(monkeypatch):
    fake = FakeJev([WEAPON_YES, None])
    _setup(monkeypatch, fake)
    gate = fake.hold(0)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        _through_rule_and_llm(ws, "my dad is hurt")
        _wait_for_calls(fake, 1)
        _send(ws, "")
        _send(ws, "my mom is hurt")
        gate.set()
        seen = _until(ws, lambda m: _is_dev(m, "jev", "decisions"))
    updates = _updates(seen)
    assert all(u["sources"] == {} and u["weapons"] is None for u in updates)
    assert [m["summary"] for m in seen if _is_dev(m, "jev", "decisions")] == ["skipped (unavailable), rule values kept"]
    assert fake.calls[-1] == "my mom is hurt"


def test_empty_transcript_clears_previously_stored_overrides(monkeypatch):
    fake = FakeJev([WEAPON_YES, None])
    _setup(monkeypatch, fake)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        _settle_transcript(ws, "my dad is hurt")
        _send(ws, "")
        seen = _through_rule_and_llm(ws, "my mom is hurt")
    first = _updates(seen)[0]
    assert first["weapons"] is None and first["sources"] == {}


def test_set_caller_resets_sticky_state_and_cancels_in_flight_jev(monkeypatch):
    fake = FakeJev([WEAPON_YES, WEAPON_YES, None])
    _setup(monkeypatch, fake)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        _settle_transcript(ws, "my dad is hurt")
        ws.send_json({"type": "set_caller", "address": "42 Oak Street"})
        _until(ws, lambda m: m["type"] == "caller_context")
        seen = _through_rule_and_llm(ws, "my mom is hurt")
        assert _updates(seen)[0]["sources"] == {} and _updates(seen)[0]["weapons"] is None


def test_set_caller_cancels_in_flight_jev_task(monkeypatch):
    fake = FakeJev([WEAPON_YES, None])
    _setup(monkeypatch, fake)
    gate = fake.hold(0)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        _through_rule_and_llm(ws, "my dad is hurt")
        _wait_for_calls(fake, 1)
        ws.send_json({"type": "set_caller", "address": "42 Oak Street"})
        _until(ws, lambda m: m["type"] == "caller_context")
        gate.set()
        _send(ws, "my mom is hurt")
        seen = _until(ws, lambda m: _is_dev(m, "jev", "decisions"))
    assert all(u["sources"] == {} for u in _updates(seen))
    assert [m["summary"] for m in seen if _is_dev(m, "jev", "decisions")] == ["skipped (unavailable), rule values kept"]


def test_newer_transcript_before_settle_delay_cancels_first_jev_call(monkeypatch):
    fake = FakeJev([WEAPON_YES])
    _setup(monkeypatch, fake, settle=0.4)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        _send(ws, "my dad is hurt")
        _until(ws, lambda m: _is_dev(m, "llm", "extraction"))
        _send(ws, "my dad is hurt badly")
        _until(ws, lambda m: _is_dev(m, "jev", "decisions"))
    assert fake.calls == ["my dad is hurt badly"]


def test_jev_call_starts_are_at_least_min_gap_apart(monkeypatch):
    fake = FakeJev([None, None])
    _setup(monkeypatch, fake, settle=0.01, gap=0.15)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        _settle_transcript(ws, "my dad is hurt")
        _settle_transcript(ws, "my dad is hurt badly")
    assert len(fake.starts) == 2
    assert fake.starts[1] - fake.starts[0] >= 0.15 - 0.005


def test_jev_never_touches_what_happened_and_headline_still_merges(monkeypatch):
    fake = FakeJev([{"weapon": 0.95, "unconscious": 0.95, "patients": (2, 0.9), "police": 0.9}])
    _setup(monkeypatch, fake, headline="Man hurt in fall")
    with TestClient(server.app).websocket_connect("/ws") as ws:
        seen = _settle_transcript(ws, "my dad is hurt")
    updates = _updates(seen)
    assert updates[0]["whatHappened"] is None
    assert updates[-1]["whatHappened"] == "Man hurt in fall"
    assert "whatHappened" not in updates[-1]["sources"]


def test_protocol_and_deviation_updates_unaffected_by_jev(monkeypatch):
    fake = FakeJev([WEAPON_YES])
    _setup(monkeypatch, fake)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        seen = _settle_transcript(ws, "my dad is choking")
    types = [m["type"] for m in seen]
    protocol = next(m for m in seen if m["type"] == "protocol_update")
    assert protocol["matchId"] == "choking-1" and protocol["transcript"] == "my dad is choking"
    assert next(m for m in seen if m["type"] == "deviation_update") == {"type": "deviation_update", "deviations": []}
    assert types.index("protocol_update") < types.index("deviation_update") < types.index("extraction_update")


def test_worker_never_blocks_on_slow_jev(monkeypatch):
    fake = FakeJev([WEAPON_YES])
    _setup(monkeypatch, fake)
    gate = fake.hold(0)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        seen = _through_rule_and_llm(ws, "my dad is choking")
        assert any(m["type"] == "protocol_update" for m in seen)
        _wait_for_calls(fake, 1)
        gate.set()
        _until(ws, lambda m: _is_dev(m, "jev", "decisions"))


def test_worker_exits_cleanly_on_disconnect_with_pending_jev(monkeypatch, recwarn):
    fake = FakeJev([WEAPON_YES])
    _setup(monkeypatch, fake, settle=5.0)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        _through_rule_and_llm(ws, "my dad is hurt")
    assert fake.calls == []
    assert not [w for w in recwarn if "never awaited" in str(w.message) or "pending" in str(w.message).lower()]


def test_stale_sticky_dropped_when_rule_value_changes(monkeypatch):
    fake = FakeJev([WEAPON_YES, WEAPON_UNSURE])
    _setup(monkeypatch, fake)
    fake_gate = fake.hold(1)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        _settle_transcript(ws, "my dad is hurt")
        seen = _through_rule_and_llm(ws, "there was no weapon")
        rule_only = _updates(seen)[0]
        assert rule_only["weapons"] is False
        assert "weapons" not in rule_only["sources"]
        _wait_for_calls(fake, 2)
        fake_gate.set()
        after = _until(ws, lambda m: _is_dev(m, "jev", "decisions"))
    assert _updates(after)[-1]["weapons"] is False
    assert "weapons" not in _updates(after)[-1]["sources"]


def test_sticky_still_applies_while_rule_value_is_unchanged(monkeypatch):
    fake = FakeJev([WEAPON_YES, WEAPON_UNSURE])
    _setup(monkeypatch, fake)
    fake_gate = fake.hold(1)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        _settle_transcript(ws, "my dad is hurt")
        seen = _through_rule_and_llm(ws, "my dad is hurt and bleeding")
        rule_only = _updates(seen)[0]
        assert rule_only["weapons"] is True and rule_only["sources"] == {"weapons": "jev"}
        _wait_for_calls(fake, 2)
        fake_gate.set()
        _until(ws, lambda m: _is_dev(m, "jev", "decisions"))


def test_sticky_false_is_dropped_when_rule_becomes_true():
    llm_state = server.new_llm_state()
    llm_state["jev_state"]["overrides"]["weapons"] = {"value": False, "rule": True}
    llm_state["jev_state"]["overrides"]["departments"] = {"value": ["Fire"], "rule": ["Police"]}
    still_true = server.build_extraction_payload({"weapons": True, "departments": ["Police"]}, llm_state)["fields"]
    assert still_true["weapons"] is False and still_true["departments"] == ["Fire"]
    assert still_true["sources"] == {"weapons": "jev", "departments": "jev"}
    changed = server.build_extraction_payload({"weapons": None, "departments": ["Police", "EMS"]}, llm_state)["fields"]
    assert changed["weapons"] is None and changed["departments"] == ["Police", "EMS"]
    assert changed["sources"] == {}
    assert llm_state["jev_state"]["overrides"] == {}


def test_unknown_rule_value_is_not_turned_into_no_by_jev(monkeypatch):
    fake = FakeJev([{"weapon": 0.05, "unconscious": 0.05}])
    _setup(monkeypatch, fake)
    with TestClient(server.app).websocket_connect("/ws") as ws:
        seen = _settle_transcript(ws, "911 please help")
    last = _updates(seen)[-1]
    assert last["weapons"] is None and last["consciousness"] is None
    assert last["sources"] == {}
    dev = [m for m in seen if _is_dev(m, "jev", "decisions")][-1]
    assert dev["summary"] == "6 checked, 0 overridden"


def test_format_jev_value_renders_none_as_unknown():
    assert server.format_jev_value(None) == "unknown"
    assert server.format_jev_value(True) == "yes"
