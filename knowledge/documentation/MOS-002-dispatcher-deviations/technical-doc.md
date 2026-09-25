# MOS-002: Dispatcher Deviation Tracking

## What it does

While a dispatcher handles a (simulated) call, the UI shows the protocol instruction matched to the caller's words. The dispatcher can now record what they actually said or plan to say (typed, spoken via a second mic, or filled from two mock-reply buttons), optionally with a reason, and click Submit. A single DeepSeek call judges the reply against the protocol chunk that was on screen:

- `followed`: nothing is stored; the UI shows a verdict card.
- `deviated`: a one-sentence summary is generated, saved as a document in a Moss index named `deviation-index`, and the in-memory copy of that index is reloaded so the record can be retrieved right away.

On later transcript updates, the server queries `deviation-index` (top 2, same trailing-window text as the protocol query) and pushes up to 2 "Related Deviations" cards shown under the protocol instruction. A read-only page, `/deviations.html`, lists every stored deviation, newest first.

## Operational step: build the index once

The server starts without `deviation-index` (it is loaded as optional). Until the index exists, deviation retrieval returns nothing and `GET /api/deviations` returns `[]`. To create it with the synthetic seed records, run once per Moss project:

```
cd backend && uv run python build_deviation_index.py
```

Requires `MOSS_PROJECT_ID` / `MOSS_PROJECT_KEY` in `backend/.env`. The script lists indexes, deletes `deviation-index` if it already exists, then creates it from `deviation_seed.py` (3 records: choking and cardiac arrest scenarios, ids `dev-seed-N`). Re-running it wipes any deviations saved through the UI. If the server is already running, restart it (or submit a deviation, which reloads the index) so the new index is loaded.

If the index is absent when the first deviation is judged as `deviated`, the endpoint creates it with that one record.

## Components

| File | Role |
|---|---|
| `backend/server.py` | `POST /api/deviations/judge`, `GET /api/deviations`, deviation query inside `transcript_worker`, optional load of `deviation-index` in `lifespan`, `LIVE_LOADED_INDEXES` includes it, dispatcher voice channel on `/ws` |
| `backend/deviation_judge.py` | `judge_deviation(...)`: DeepSeek JSON-mode call (`temperature=0`, `max_tokens=200`); reuses `_get_client` and `DEEPSEEK_MODEL` from `structured_extraction.py`. Returns `None` if no API key. Raises `ValueError` on empty, non-JSON, invalid verdict, or a `deviated` verdict without a summary |
| `backend/deviation_seed.py`, `backend/build_deviation_index.py` | Seed records and the one-time build script |
| `backend/live_panel.py` | `DEVIATION_INDEX_NAME = "deviation-index"` |
| `backend/static/index.html`, `app.js`, `style.css` | Dispatcher Transcript panel, verdict card, Related Deviations block, dispatcher mic |
| `backend/static/deviations.html`, `deviations.js` | Read-only list page (loading, empty, error+Retry states) |
| `backend/voice_stream.py` | Unchanged; `DeepgramStream` is instantiated per channel |

## How it works

### Judge flow
1. The client snapshots the on-screen protocol chunk (id and text) at click time and posts it with the dispatcher text, optional reason, caller transcript and optional structured caller summary.
2. Server validates (Pydantic), calls `judge_deviation`. Any exception -> 502 `Could not judge response`; `None` (no key) -> 503 `LLM not configured`. Nothing is written in either case.
3. On `deviated` it builds a `DocumentInfo` with id `dev-<uuid4 hex>`. `text` is the retrieval key: `"<caller situation>\n<deviation summary>"`, where the caller situation is `callerSummary.whatHappened` followed by a space and the last 8 words (`WINDOW_WORDS`) of the caller transcript (just the 8-word tail if there is no `whatHappened`).
4. `save_deviation` calls `list_indexes`; if `deviation-index` exists it uses `add_docs`, otherwise `create_index` with the single doc.
5. `load_index` reloads the local copy. If that fails, the response still succeeds with `retrievable: false` (the write went through). A save failure returns 500 `Failed to save deviation`.

### Retrieval flow
`transcript_worker` runs the protocol top-1 query and `query_deviations` (top 2) concurrently on the same `query_text`. `query_deviations` swallows any exception (logged) and returns `None`, so a missing or broken deviation index never breaks the protocol path. Results with `score >= DEVIATION_MIN_SCORE` (0.3) are kept. Message order per update: `protocol_update`, `dev_log` (protocol-query), `deviation_update` (always sent, possibly empty), `dev_log` (deviation-query, only if the query succeeded), then `extraction_update`.

### Dispatcher voice
`voice_start` / `voice_stop` accept an optional `channel` (`"caller"` default, or `"dispatcher"`). The server keeps one `DeepgramStream` per channel. Dispatcher transcripts are sent as `dispatcher_voice_transcript` and are never fed to the transcript worker (no Moss query). Binary audio frames carry no channel tag and go to the dispatcher stream if open, else the caller stream. The client keeps the caller and dispatcher mics mutually exclusive.

## Where the implementation differs from `architecture.md`

- **`seed` on live records is `"false"`**: judged deviations store `metadata.seed = "false"` (architecture only specified `"true"` for seeds). `GET /api/deviations` returns `seed: true` only when the value is exactly `"true"`.
- **`deviation_update` carries an extra field**: each item includes `protocolChunkText` in addition to the documented `id, summary, dispatcherTranscript, reason, timestamp, score`.
- **Index existence check**: creation-vs-append uses `list_indexes()` then `create_index`/`add_docs` (a list-then-create fallback), not a try/except on `add_docs`. The build script similarly does `list_indexes` -> `delete_index` -> `create_index`.
- **Caller-situation join**: `whatHappened` and the transcript tail are joined with a space, not a newline (only the summary is separated by a newline).
- **Submit uses `aria-disabled`**: the Submit button is set `aria-disabled="true"` (not the `disabled` attribute) while text is empty, no chunk is on screen, a request is in flight, or the dispatcher mic is listening.
- **Dispatcher mic text is appended**: live dispatcher transcript is appended to any existing text in the reply textarea rather than replacing it.
- **Unknown voice channel** returns `voice_status {state:"error", reason:"unknown voice channel"}` and keeps the session alive. Dispatcher-channel `voice_status` messages are tagged `channel: "dispatcher"`.
- The story-004 test locator collision (group `aria-label` "Dispatcher reply input") was resolved by relabelling the group "Dispatcher input controls" (per test-results.md).

## Known caveats (unverified; from test-results.md)

All stories are PASS WITH CAVEATS. All Moss and LLM behavior was tested against mocks or stubs only (final full run: 174 passed).

- `build_deviation_index.py` was never run; real index creation (delete-then-create) is unverified against a live Moss project.
- Real DeepSeek verdict quality (followed vs deviated accuracy) is unverified.
- Real Moss `create_index` / `add_docs` behavior and whether `load_index` makes new docs retrievable are unverified.
- `DEVIATION_MIN_SCORE = 0.3` is an untuned guess and Moss's real score scale is unverified. Retrieval ranking and latency were not measured against a real index.
- Moss's error type for a missing index in `GET /api/deviations` is assumed to be `RuntimeError` (as `get_index_docs` already does), not confirmed live.
- E2E tests use stub servers; real Deepgram ASR, real microphone use and speaker-bleed between caller playback and the dispatcher mic are unverified.
- Accessibility was checked via attributes only (`aria-disabled`, `aria-pressed`, roles, labels), not with assistive technology. Visual styling (teal accent, spacing, Google Fonts) was not eyeballed. The network-failure (status 0) error path of Submit is not tested. The Manage Indexes page rendering was not tested for this index.
- Security lens was skipped by the user for this feature. The server trusts the protocol chunk sent by the client, and the judge endpoint is unauthenticated apart from the optional global `DEMO_PASSWORD` Basic-auth middleware. Length caps are the only abuse limit; there is no rate limiting.

## Extending safely

- Deviation documents must have all-string metadata values (Moss requirement); JSON-stringify structured values as done for `callerSummary`.
- `text` is what is embedded and searched. Changing its composition changes retrieval; existing records are not re-embedded.
- To tune retrieval, adjust `DEVIATION_MIN_SCORE` in `server.py` (and the top_k of 2 in `query_deviations`). The frontend caps displayed cards at 2.
- To add seeds, edit `deviation_seed.py` using real `protocolChunkId` values from `protocol_chunks.py`, then re-run the build script (this deletes UI-saved deviations).
- Keep judge changes inside `deviation_judge.py`; the endpoint depends on its contract (`None`, or `{verdict, deviationSummary}`, or `ValueError`).
- Free-form docs can also be edited through the MOS-001 endpoints (`/api/indexes/deviation-index/docs`), which reload the live index after mutation.
