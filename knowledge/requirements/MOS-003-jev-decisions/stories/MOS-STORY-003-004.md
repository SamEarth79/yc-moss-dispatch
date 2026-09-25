# MOS-STORY-003-004: Worker integration

## Description

As a dispatcher, I want Jev's corrections to arrive in the background without flicker, so that the panel stays fast and stable while the caller talks.

## Acceptance criteria

1. `transcript_worker` starts a Jev extraction task separate from the DeepSeek headline task; it waits ~600 ms for the transcript to stop changing, keeps at least ~800 ms between Jev call starts, and is cancelled when a newer transcript arrives.
2. The task calls `decide_extraction` with the full transcript, merges via `merge_jev_fields`, stores confident overrides in a sticky Jev state in `llm_state`, and re-sends `extraction_update`.
3. Every `extraction_update` is built as rule fields, then the DeepSeek headline, then the sticky Jev overrides, and carries a `sources` map (`{}` when none); the rule-only update on a new transcript never reverts a sticky Jev value; a newer confident Jev answer replaces it; the sticky state resets on `set_caller`.
4. A dev-feed line `jev / decisions` reports checked/overridden fields with latency (e.g. `6 checked, 2 overridden (weapons: no→yes)`); a fallback line (e.g. `skipped (timeout 1.5s), rule values kept`) is sent when Jev returns `None`; nothing user-facing changes on fallback.
5. The protocol query, deviation retrieval and DeepSeek headline paths are unaffected; the worker never blocks on Jev.
6. Feature tests (fake `jev_client`, `TestClient` websocket) cover override, stickiness across transcripts, replacement by a newer confident answer, reset on caller change, cancellation on a newer transcript, min-gap/trailing-edge behaviour, fallback, and unchanged `extraction_update` shape for existing keys.

## Requirements implemented

- User flows steps 2-3, 5
- Business rules #1, #2, #6
- architecture.md Extraction data flow; Key decisions (call policy, sticky state)

## Depends on

- MOS-STORY-003-003

## Agents likely needed

- [ ] frontend
- [x] backend
- [ ] infrastructure

## Status

- [ ] Implemented
- [ ] Tested
- [ ] Committed
