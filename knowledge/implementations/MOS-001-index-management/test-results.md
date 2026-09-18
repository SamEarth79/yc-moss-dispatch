# Test Results — MOS-001-index-management

## MOS-STORY-001-001

Command: `cd backend && .venv/bin/python -m pytest test_server.py -v`

Result: 5 passed, 0 failed, 1 warning (unrelated `anyio.abc.BlockingPortal`
deprecation warning from Starlette's TestClient, not from this story's code).

### Layers

- **Unit tests: none written.** This story is a thin route/mapping layer
  over an already-tested Moss SDK (`list_indexes`, `get_index`, `get_docs`).
  A unit test would isolate the same dict-comprehension mapping that the
  feature tests below already exercise through the real route (request →
  handler → response body), so a separate unit layer would just re-assert
  the same logic through a narrower lens. Per `rules/testing.md`'s carve-out
  ("not required for trivial pass-through code"), feature-level tests are
  the right and sufficient layer here.
- **Feature tests: 5 written, 5 passed**, in `backend/test_server.py`, using
  Starlette's `TestClient` against the real FastAPI app and routes, with
  `server.moss_client` monkeypatched to a `SimpleNamespace` carrying
  `AsyncMock` methods. No real Moss credentials or network calls are used.
  - `test_list_indexes_returns_mapped_shape` — AC1
  - `test_get_index_docs_returns_mapped_shape_when_index_exists` — AC2
  - `test_get_index_docs_returns_404_when_index_missing` — AC3 (also
    confirms `get_docs` is never called)
  - `test_list_indexes_returns_500_without_leaking_details_on_unexpected_error`
    — AC5
  - `test_get_index_docs_returns_500_when_get_docs_fails_after_index_found`
    — AC5
- **E2E tests: none written.** Backend-only story, no user-facing UI change
  yet — the frontend consuming these endpoints is a separate story.

### AC4 confirmation

Confirmed implicitly: tests monkeypatch the module-level `server.moss_client`
global itself, and the route handlers pick up the patched fake object at
call time — confirming they read the shared global rather than holding a
private/captured reference.

### Framework setup

No test framework existed in this repo before this story. Added `pytest`
and `httpx` as dev dependencies via `uv add --dev pytest httpx` in
`backend/pyproject.toml` / `uv.lock`.

**Verdict: PASS.**
