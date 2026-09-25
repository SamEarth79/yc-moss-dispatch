# Architecture Overview

A demo 911 dispatcher UI backed by Moss (semantic search) and DeepSeek (LLM), served by one FastAPI process. Source in `backend/`.

## Components

- **FastAPI server** (`backend/server.py`): HTTP API, the `/ws` WebSocket, and static file hosting. Optional shared-password Basic auth (`basic_auth.py`, active when `DEMO_PASSWORD` is set).
- **Static frontend** (`backend/static/`): `index.html` + `app.js` (live dispatcher UI), `manage.html` (index/document management), `deviations.html` + `deviations.js` (read-only deviation list). Plain HTML/JS/CSS, no build step.
- **Moss indexes** (cloud-stored, loaded into memory at startup for local queries):
  - `protocol-index`: protocol chunks (required).
  - `live-data-index`: incidents and facilities (required).
  - `deviation-index`: recorded dispatcher deviations (optional; created by `build_deviation_index.py` or by the first judged deviation).
- **DeepSeek LLM** (via `structured_extraction.py` client): structured field extraction (`extraction_update`) and deviation judging (`deviation_judge.py`). Both degrade gracefully when no API key is configured.
- **Jev decision model** (`backend/jev_client.py`, MOS-003): OpenRouter Decisions API (alpha), called through the `openai` SDK's raw `post` with per-request timeouts and no retries. Refines rule-based extraction and makes the first-pass deviation verdict. Optional: needs `OPENROUTER_API_KEY`; every function returns `None` on any failure so callers fall back. Thresholds and timeouts live in `jev_client.py`.
- **Deepgram** (`voice_stream.py`): streaming speech-to-text; one stream per voice channel (caller, dispatcher) per WebSocket session.

## Startup
`lifespan` loads `protocol-index` and `live-data-index` (retries once, then fails startup), then tries `deviation-index` separately; failure only logs a warning. On shutdown only the indexes that loaded are unloaded. Local disk cache: `MOSS_CACHE_DIR` or `backend/.moss-cache`.

## Data flows

1. **Live protocol matching**: transcript (typed, or caller-channel speech) -> `transcript_worker` (latest-wins, one per connection) -> concurrent Moss queries on the trailing 8-word window: `protocol-index` top 1 and `deviation-index` top 2 (score cutoff 0.3) -> `protocol_update` and `deviation_update` to the client. LLM extraction runs in the background and is cancelled by newer transcripts. Rule fields go out immediately; two background tasks per transcript then refine them: the DeepSeek headline task and a Jev task (`run_jev_extraction`: wait 0.6 s for the transcript to settle, at least 0.8 s between call starts, one batched 6-question request). Confident Jev answers become sticky per-connection overrides (`{value, rule}`, dropped if the rule value changes), and every `extraction_update` is built by `build_extraction_payload` (rules + DeepSeek + sticky Jev, plus a `sources` map). Sticky state resets on `set_caller` and on an empty transcript.
2. **Deviation judging** (REST, not WS): client posts the reply plus the on-screen chunk -> `deviation_judge` (Jev first: P(follows) >= 0.3 is `followed`; otherwise DeepSeek only writes the summary; if Jev is unavailable, the full DeepSeek verdict) -> on `deviated`, write to `deviation-index` (`add_docs` or `create_index` if absent) -> `load_index` reload so it is queryable on the next transcript update. `followed` stores nothing. Both 200 responses carry a `devLog` entry (`jev` / `verdict`, latency and P(follows), or `skipped (unavailable), DeepSeek fallback`) that the client renders into the developer feed.
3. **Deviation listing**: `GET /api/deviations` reads all docs from `deviation-index`, newest first.
4. **Index management**: `/api/indexes*` endpoints mutate any index; live-loaded indexes (`LIVE_LOADED_INDEXES`) are reloaded after each mutation.
5. **Voice**: `voice_start`/`voice_stop` with channel; caller transcripts feed flow 1, dispatcher transcripts only go back to the client as `dispatcher_voice_transcript` and are never used for retrieval.

## Operational notes
- Required env: `MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY`. Optional: `DEEPSEEK_API_KEY` (LLM features), `OPENROUTER_API_KEY` (Jev; silent fallback to rules/DeepSeek when absent, visible only as dev-feed `jev` fallback lines), a Deepgram key (voice; see `voice_stream.py`), `DEMO_PASSWORD`, `MOSS_CACHE_DIR`.
- Run `cd backend && uv run python build_deviation_index.py` once per Moss project to create `deviation-index` with seed data. The server runs without it, but deviation retrieval returns nothing and the list page is empty until the index exists.
- Tests: `cd backend && uv run pytest -q` (Playwright E2E needs `uv run playwright install chromium`).

See `api-reference.md` for endpoint and WebSocket message details.
