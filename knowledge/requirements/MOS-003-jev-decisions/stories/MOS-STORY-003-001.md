# MOS-STORY-003-001: Jev client

## Description

As a developer, I want an isolated Jev client module, so that every Jev call has one place for request shapes, timeouts and failure handling.

## Acceptance criteria

1. `backend/jev_client.py` exposes `decide_extraction(text)` and `decide_follows(protocol_chunk_text, dispatcher_text, caller_transcript, reason)`; each returns plain parsed values or `None` and never raises (except `CancelledError`); failures are logged with `logger.warning` and no secret or transcript text is logged.
2. It reads `OPENROUTER_API_KEY` at call time and returns `None` when unset; calls `POST https://openrouter.ai/api/alpha/decisions` with `{model: "typesafe/jev-1.13", state, questions}` using the installed `openai` SDK raw `post` with per-request timeout and `max_retries=0` (if that does not work against the alpha path, use `httpx` and promote it to a runtime dependency in `pyproject.toml`, noting it in the implementation summary).
3. `decide_extraction` sends one batched request with questions `weapon`, `unconscious` (noul), `patients` (choice `0`-`10`, with `0` described as nobody hurt) and `police`, `ems`, `fire` (noul), and returns `{weapon: p, unconscious: p, patients: (choice, confidence), police: p, ems: p, fire: p}` with missing or malformed answers omitted (partial results are returned).
4. `decide_follows` sends one noul `follows_protocol` question (true = the reply gives the same guidance as the protocol instruction, paraphrase or reassurance allowed; false = contradicts, skips steps, different guidance, or does not address it) and returns P(follows) as a float or `None`.
5. Constants live together: `JEV_CONFIDENCE_HIGH=0.7`, `JEV_CONFIDENCE_LOW=0.3`, `JEV_FOLLOW_THRESHOLD=0.3`, `EXTRACTION_TIMEOUT_S=1.5`, `JUDGE_TIMEOUT_S=3.0`.
6. `OPENROUTER_API_KEY=` is added to `backend/.env.example` (create it if missing) with a placeholder value; the key is never committed.
7. Unit tests use a mocked transport; real Jev behaviour is recorded as an unverified caveat.

## Requirements implemented

- Technical constraints #1-#3, #5
- Business rules #3, #4, #6
- architecture.md Jev client; Key decisions (transport, constants)

## Depends on

-

## Agents likely needed

- [ ] frontend
- [x] backend
- [ ] infrastructure

## Status

- [x] Implemented
- [x] Tested
- [x] Committed
