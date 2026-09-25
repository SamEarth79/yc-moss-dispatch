# Architecture: Dispatcher Deviation Tracking

> Drafted by the `design-developer` lens. **No security sign-off** — the user explicitly skipped the security lens for this feature.

## Approach

Add a single-shot judge endpoint, `POST /api/deviations/judge`. The dispatcher panel posts one Submit containing the dispatcher text, the protocol chunk on screen at click time, and the caller context. The endpoint makes one DeepSeek call that returns a verdict (`followed` or `deviated`) plus a one-line summary. Only on `deviated` it writes a document to a new Moss index, `deviation-index`, and reloads the in-memory copy before responding so the record is retrievable on the next transcript update. `followed` stores nothing. If the LLM is not configured or fails, nothing is written and the UI shows a graceful error.

Retrieval piggybacks on the existing `transcript_worker`: alongside the protocol top-1 query it runs a top-2 query on `deviation-index` with the same trailing-window text (concurrently), applies a minimum score cutoff, and pushes a `deviation_update` WS message rendered as "Related Deviations" between the instruction steps and the dispatch action. A read-only `GET /api/deviations` backs the new `/deviations.html`. The dispatcher mic reuses `DeepgramStream` on a second channel of the existing WS. No new services, dependencies, or env vars.

## Components touched

- **Frontend**:
  - `backend/static/index.html` — "Dispatcher Transcript" section in the left `.transcript-panel` (textarea, mic, two mock-reply buttons, optional reason, Submit, verdict card); "Related Deviations" block in the instruction panel; "Deviations" nav link.
  - `backend/static/app.js` — submit handler (chunk snapshot at click), verdict rendering, `deviation_update` rendering, channel-aware voice state, mutual exclusion of caller and dispatcher mics.
  - `backend/static/deviations.html` + `deviations.js` — read-only list, newest first, loading/empty/error states.
  - `backend/static/style.css` — `.verdict-card`, `.deviation-card`, `.deviation-record` built from existing tokens only.
  - `backend/static/manage.html` — nav link to Deviations.
- **Backend**:
  - `backend/server.py` — judge and list endpoints, second query in `transcript_worker`, `deviation-index` optional load in `lifespan`, `LIVE_LOADED_INDEXES` addition, dispatcher voice channel.
  - `backend/live_panel.py` — `DEVIATION_INDEX_NAME`.
  - New `backend/deviation_judge.py` — prompt and LLM call (uses `_get_client` and model id from `structured_extraction.py`).
  - New `backend/build_deviation_index.py` and `backend/deviation_seed.py` — 3–4 seeded synthetic deviations referencing real protocol chunk ids.
  - `backend/voice_stream.py` — unchanged.
- **Infrastructure**: none. Seed script is run once per environment (README note).

## Data flow

1. The caller talks; the existing flow shows a protocol chunk. The client already holds `matchId`/`matchText`, the caller transcript, and the structured summary.
2. The dispatcher types, speaks (dispatcher mic channel), or clicks a mock button (fills the textarea with canned text). Optional reason. Submit is enabled only when text is non-empty, a chunk is on screen, and no request is in flight.
3. On click the client snapshots chunk id/text and posts `POST /api/deviations/judge`.
4. The server validates the body and calls `judge_deviation(...)`. LLM unconfigured → 503; LLM error or malformed JSON → 502; nothing written.
5. `followed` → `{"verdict":"followed"}`, nothing stored; UI shows a verdict card with the submitted text, clears inputs.
6. `deviated` → build a `DocumentInfo` (id `dev-<uuid hex>`, `text` = caller situation + "\n" + deviation summary, string-only metadata); `add_docs` (creating the index first if it does not exist); reload the index; respond `{"verdict":"deviated","deviationSummary":...,"id":...,"retrievable":true|false}`. UI shows the deviated card and a "saved" line, or a "not retrievable yet" warning.
7. On the next transcript update, `transcript_worker` runs both queries on the same `query_text` and sends `protocol_update` then `deviation_update` (0–2 cards after the score cutoff) plus a dev-feed log line.
8. `GET /api/deviations` returns all docs sorted by `timestamp` descending; `/deviations.html` renders them read-only.

## Data model changes

New Moss index `deviation-index`; no other index or schema changes. One document per deviation:

- `id`: `dev-<uuid hex>` (seeds: `dev-seed-N`)
- `text`: `"<caller situation>\n<deviation summary>"` — the retrieval key. Caller situation = structured `whatHappened` plus a trailing slice of the caller transcript, falling back to the transcript.
- `metadata` (all string values): `type: "deviation"`, `callerTranscript`, `callerSummary` (JSON-stringified), `protocolChunkId`, `protocolChunkText`, `dispatcherTranscript`, `deviationSummary`, `reason` (empty string if none), `timestamp` (ISO-8601 UTC), `seed` ("true" for seeded records).

## API surface

```
POST /api/deviations/judge
  body: { dispatcherText, reason?, protocolChunkId, protocolChunkText, callerTranscript, callerSummary? }
  200 { verdict: "followed" }
  200 { verdict: "deviated", deviationSummary, id, retrievable: bool }
  422 validation failure (non-empty dispatcherText/chunk/transcript, length caps)
  503 { detail: "LLM not configured" }
  502 { detail: "Could not judge response" }
  500 { detail: "Failed to save deviation" }

GET /api/deviations
  200 [{ id, timestamp, callerTranscript, callerSummary, protocolChunkId, protocolChunkText,
         dispatcherTranscript, deviationSummary, reason, seed }]  newest first
  500 on Moss failure

WS server -> client (new):
  { type: "deviation_update", deviations: [{ id, summary, dispatcherTranscript, reason, timestamp, score }] }
  { type: "dispatcher_voice_transcript", text }
WS client -> server (extended):
  { type: "voice_start", channel: "caller" | "dispatcher" }   // default "caller"
```

`/api/indexes/{name}/docs` from MOS-001 also works on this index unchanged.

## Key decisions

- **Decision**: REST for the judge, not a WebSocket message.
  **Rationale**: one-shot request/response needs status codes (LLM unconfigured); the WS worker is latest-wins per connection and would collide with a slow LLM call.
- **Decision**: `deviation-index` is optional at startup and created on first deviation if absent.
  **Rationale**: a missing seed must not take the server down; `create_index` needs at least one doc, so the first record creates it.
- **Decision**: report reload failure to the client (`retrievable: false`) instead of using the swallowing `_reload_if_live` path.
  **Rationale**: "retrievable immediately" is a business rule; silent failure would break it.
- **Decision**: semantic retrieval with a minimum score cutoff and `protocolChunkId` stored as metadata.
  **Rationale**: agreed semantic retrieval; cutoff avoids trust-eroding weak matches; the id keeps exact-match filtering open.
- **Decision**: dispatcher mic is a second channel on the existing WS, mutually exclusive with caller mic/sample.
  **Rationale**: reuses `DeepgramStream` unchanged and avoids speaker bleed; requires a channel-aware client voice state.
- **Decision**: client sends the chunk on screen at click time and the server trusts it.
  **Rationale**: the WS worker's state is not addressable from REST; the chunk on screen is a client-side fact. Trade-off accepted (security skipped by the user).
- **Decision**: separate `deviation_judge.py`, importing the shared client and model id; `max_tokens` ≈ 200; verdict validated against the two allowed values; JSON parse errors handled.
  **Rationale**: keeps `structured_extraction.py` single-purpose without a second client.
- **Decision**: LLM verdict testing is `PASS WITH CAVEATS` unless verified against live DeepSeek.
  **Rationale**: `rules/testing.md` external-contract rule.
