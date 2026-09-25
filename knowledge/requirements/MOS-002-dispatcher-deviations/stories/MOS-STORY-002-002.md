# MOS-STORY-002-002: Judge endpoint

## Description

As a dispatcher, I want my reply compared against the protocol chunk on screen and any deviation saved, so that off-protocol practice is captured for future calls.

## Acceptance criteria

1. `backend/deviation_judge.py` exposes `judge_deviation(...)` that makes one DeepSeek JSON-mode call (reusing the shared client/model, `max_tokens` about 200) and returns `{verdict: "followed"|"deviated", deviationSummary}`; it returns `None` when the LLM is not configured and validates the verdict value and JSON parsing.
2. `POST /api/deviations/judge` validates the body (non-empty `dispatcherText`, `protocolChunkId`, `protocolChunkText`, `callerTranscript`; length caps) and returns 422 on failure.
3. LLM not configured returns 503 `LLM not configured`; LLM error/malformed output returns 502 `Could not judge response`; in both cases nothing is written.
4. `followed` returns `{verdict: "followed"}` and writes nothing.
5. `deviated` writes one document to `deviation-index` (id `dev-<uuid hex>`, `text` = caller situation + newline + deviation summary, metadata per `architecture.md`, `reason` empty string when absent, ISO-8601 UTC `timestamp`), creating the index first if it does not exist.
6. After a successful write the index is reloaded; the response is `{verdict: "deviated", deviationSummary, id, retrievable}` where `retrievable` is `false` if the reload failed. A write failure returns 500 `Failed to save deviation`.
7. Errors never leak stack traces or provider details.

## Requirements implemented

- User flows steps 3-5
- Business rules #1-#5
- Technical constraints #1, #3
- architecture.md API surface

## Depends on

- MOS-STORY-002-001

## Agents likely needed

- [ ] frontend
- [x] backend
- [ ] infrastructure

## Status

- [ ] Implemented
- [ ] Tested
- [ ] Committed
