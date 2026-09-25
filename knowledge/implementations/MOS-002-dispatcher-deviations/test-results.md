
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

## MOS-STORY-002-007: Deviations page

Command: `cd backend && uv run pytest -q` (after `uv run playwright install chromium`)

Verdict: PASS WITH CAVEATS

| Layer | Result |
|---|---|
| Unit/feature (`GET /api/deviations`; fake `moss_client`, TestClient; `backend/test_deviations_list.py`) | 9 passed, 0 failed |
| E2E (Playwright/Chromium; `backend/tests/e2e/test_deviations_page.py`, stub harness extended in `conftest.py` with `/api/deviations`) | 11 passed, 0 failed |
| Full backend suite incl. e2e | 115 passed, 0 failed (20 new: 9 API + 11 E2E; 88 non-E2E, 27 E2E) |

Acceptance criteria mapping: AC1 empty array when index missing (RuntimeError) and when empty, newest-first sort, exact 10-key shape, missing metadata defaults, malformed/non-object/empty callerSummary -> `{}`, seed only for `"true"`, 500 `Failed to retrieve deviations` for index-lookup and get_docs failures with no secret text leaked. AC2 populated, empty, error + Retry recovery, loading-to-populated, count badge (singular/plural), show-more clamp toggle, no clamp for short text. AC3 sample tag only on seeded records. AC4 `time[datetime]`, single `<main>`, `lang="en"`, title, no horizontal overflow at 375px with 600-char unbroken text. AC5 nav link on index.html and manage.html, deviations page links back to both (click-through verified). AC6 no edit/delete/input controls.

Caveats (unverified):
- E2E runs against a stub server returning fixture data (order supplied by the stub); real Moss and the real `/api/deviations` route were not exercised together in the browser. Sorting is verified only at the API layer with a fake client.
- Real Moss `get_index` error type for a missing index is assumed to be `RuntimeError` (per implementation), not confirmed against a live project.
- The 1-column layout under 640px was checked only indirectly (no horizontal overflow at 375px), not via computed grid columns.
- Google Fonts are external and not loaded/verified in the test environment.

## MOS-STORY-002-004: Dispatcher panel + verdict card

Command: `cd backend && uv run pytest -q`

Verdict: PASS WITH CAVEATS

| Layer | Result |
|---|---|
| Unit/feature | none added: frontend-only story; the judge endpoint is already covered by earlier stories' tests |
| E2E (Playwright/Chromium; `backend/tests/e2e/test_dispatcher_panel.py`, own stub app serving the real static files, `/ws` stub that pushes `protocol_update`, recording `POST /api/deviations/judge` stub) | 17 passed, 0 failed |
| Full backend suite incl. e2e | 132 passed, 0 failed (88 non-E2E, 44 E2E) |

Acceptance criteria mapping: AC1 panel heading, labelled textarea/reason input, two demo buttons, Submit. AC2 mock buttons replace text, do not submit (no request), `aria-pressed` toggles and clears on typing. AC3 `aria-disabled` for empty/blank text, no chunk (helper shown, hidden once chunk arrives), in flight ("Checking…", double click plus Ctrl+Enter send one request); Ctrl+Enter submits, plain Enter does not. AC4 request body carries the chunk snapshotted at click time even when a new `protocol_update` arrives before the response, callerTranscript, trimmed text, `reason` only when non-empty. AC5 followed card, inputs and selection cleared. AC6 deviated card with summary, "LLM generated" tag, "Saved to deviation index" or the not-retrievable warning; inputs cleared. AC7 503/502/500 error cards with exact copy, inputs preserved, Submit re-enabled. AC8 `role="status"` / `role="alert"`, verdict conveyed by text, card persists until the next Submit and is replaced by it; caller change clears inputs and card.

Notes: Playwright treats `aria-disabled` buttons as not actionable, so clicks on a disabled Submit use `force=True`. Network-failure (status 0) error path is not separately tested. No arbitrary sleeps.

Caveats (unverified):
- E2E runs against stubs: the real LLM verdict and the real WebSocket/protocol matching were not exercised together with the UI.
- Keyboard-only and screen-reader behaviour is asserted only via attributes (`aria-disabled`, `aria-pressed`, `role`, label association), not with assistive technology.
- Google Fonts are blocked in tests, so final visual rendering was not verified.
