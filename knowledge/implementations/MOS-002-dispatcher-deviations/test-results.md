
## MOS-STORY-002-001: Deviation index + seed

Command: `cd backend && uv run pytest --ignore=tests/e2e -q`

Verdict: PASS WITH CAVEATS

| Layer | Result |
|---|---|
| Unit (seed shape, constants, LIVE_LOADED_INDEXES) | 8 passed, 0 failed |
| Feature (lifespan, reload-on-mutation, /api/indexes; fake MossClient + TestClient) | 6 passed, 0 failed |
| E2E | skipped: no user-facing surface in this story |
| Full backend suite (excluding tests/e2e) | 34 passed, 0 failed (14 new in `backend/test_deviation_index.py`) |

Acceptance criteria mapping: AC1 constant test; AC2 seed count/type/seed/all-string/real protocolChunkId tests; AC4 lifespan tests (load ok, reported failure, raised exception, required-index failure still raises); AC5 LIVE_LOADED_INDEXES + reload on add/delete + unload only what loaded; AC6 /api/indexes lists deviation-index. AC3 (`build_deviation_index.py`) has no automated test.

Caveats (unverified):
- `build_deviation_index.py` was not run or tested; real Moss index creation (delete-then-create) is unverified against a live Moss project.
- All Moss behavior (load_indexes result shape, missing-index failure mode) is exercised only against a mocked client, so the real SDK's failure behavior for a nonexistent index is an unverified assumption.
- The Manage Indexes page rendering (frontend) was not tested; only the /api/indexes payload.

## MOS-STORY-002-002: Judge endpoint

Command: `cd backend && uv run pytest --ignore=tests/e2e -q`

Verdict: PASS WITH CAVEATS

| Layer | Result |
|---|---|
| Unit (`deviation_judge` with fake AsyncOpenAI-style client) | 14 passed, 0 failed |
| Feature (`POST /api/deviations/judge`; fake `moss_client`, mocked `judge_deviation`, TestClient) | 23 passed, 0 failed |
| E2E | skipped: no user-facing surface in this story (backend endpoint only) |
| Full backend suite (excluding tests/e2e) | 71 passed, 0 failed (37 new in `backend/test_deviation_judge.py`) |

Acceptance criteria mapping: AC1 None client, followed/deviated JSON, JSON mode and max_tokens=200, raises on invalid verdict/empty/None/non-JSON/deviated-without-summary; AC2 422 for empty/whitespace/missing fields and over-length caps; AC3 503 `LLM not configured` and 502 `Could not judge response` (ValueError and generic exception), nothing written; AC4 followed returns `{verdict}` and writes/reloads nothing; AC5 one doc, `dev-<32 hex>` id, text = situation + newline + summary, all-string metadata, empty `reason` when absent, ISO-8601 UTC timestamp, `create_index` when missing vs `add_docs` when present; AC6 reload called, `retrievable` false when `load_index` raises, 500 `Failed to save deviation` when list/add/create fails; AC7 error bodies checked for absence of provider/secret text and tracebacks.

Caveats (unverified, mocked only):
- Real DeepSeek verdict quality (prompt accuracy for followed vs deviated) is unverified.
- Real Moss `create_index` / `add_docs` behavior is unverified against a live project.
- `load_index` reload semantics (whether it makes new docs retrievable) are unverified.

## MOS-STORY-002-003: Deviation retrieval on live call

Command: `cd backend && uv run pytest --ignore=tests/e2e -q`

Verdict: PASS WITH CAVEATS

| Layer | Result |
|---|---|
| Unit/feature (`transcript_worker` via `/ws` TestClient with fake `moss_client`, mocked `extract_llm_fields`; judge-endpoint integration) | 8 passed, 0 failed |
| E2E | skipped: no user-facing surface in this story (no UI change) |
| Full backend suite (excluding tests/e2e) | 79 passed, 0 failed (8 new in `backend/test_deviation_retrieval.py`) |

Acceptance criteria mapping: AC1 both queries recorded with identical trailing-window text, top_k 1 (protocol) and 2 (deviation); AC2 score below cutoff dropped, exactly `DEVIATION_MIN_SCORE` kept, all-below yields empty list, max 2 sent; AC3 payload keys id/summary/dispatcherTranscript/reason/timestamp/score and ordering after `protocol_update`; AC4 `moss`/`deviation-query` dev_log with latency; AC5 raising deviation query gives empty `deviation_update`, no deviation dev_log, `protocol_update` identical to the healthy run; AC6 stateful fake client: POST `/api/deviations/judge` then a later transcript on the same app returns the new deviation (empty before).

Caveats (unverified):
- `DEVIATION_MIN_SCORE=0.3` is an untuned guess and the real Moss score scale is unverified.
- Retrieval was tested only with a mocked Moss client; real query ranking/latency and real `load_index` making new docs retrievable are unverified.
