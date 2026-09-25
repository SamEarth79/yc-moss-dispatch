
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
