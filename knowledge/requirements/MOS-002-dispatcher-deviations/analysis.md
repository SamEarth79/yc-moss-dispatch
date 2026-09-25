# Analysis: Dispatcher Deviation Tracking

## Summary

Capture the dispatcher's own response to a caller, compare it against the protocol chunk on screen, and record any deviation in a new Moss index (`deviation-index`). On later calls, retrieve related past deviations alongside protocol chunks so the dispatcher sees where experienced dispatchers went off-protocol. Serves dispatchers (and demo viewers) of the Dispatch Copilot.

Security review was explicitly skipped by the user for this feature; there was no `design-security` lens and no sign-off.

## Relevant existing code

- `backend/server.py` — `moss_client`, `LIVE_LOADED_INDEXES`, `_reload_if_live` (swallows failures), `lifespan` (hardcoded index list, fails hard if a load fails), `transcript_worker` (protocol top-1 query on a trailing window; the hook for deviation retrieval), `/ws` voice handling, `AddDocRequest` validators and `HTTPException` patterns.
- `backend/live_panel.py` — home of `PROTOCOL_INDEX_NAME` / `LIVE_DATA_INDEX_NAME`; add `DEVIATION_INDEX_NAME`.
- `backend/structured_extraction.py` — DeepSeek client `_get_client()` (returns `None` when unconfigured), model id, JSON-mode call params (`thinking` disabled). Reuse for the judge.
- `backend/build_protocol_index.py`, `protocol_chunks.py` — seed script and chunk-data pattern to mirror; seeds must reference real protocol chunk ids.
- `backend/voice_stream.py` — Deepgram relay, generic over its callback; reusable unchanged for a second channel.
- `backend/static/index.html`, `app.js` — three-column layout, single shared voice state (`stopActiveVoice`, `voiceReadyResolver`) that must become channel-aware; `ws.onmessage` dispatch by `msg.type`.
- `backend/static/manage.html`, `manage.js`, `style.css` — header/nav, `.panel`, `.incident-card`, `.badge`, `.source-tag--moss/--llm`, `.error-banner`, `.empty-state`, `.chunk-row`, show-more clamp logic; reuse for the deviations page and new cards.
- `knowledge/requirements/MOS-001-index-management/architecture.md` — the generic index docs API (`/api/indexes/{name}/docs`) already works on any index, including the new one; `manage.html` lists it automatically.

## Constraints and risks

- **Startup**: the current `lifespan` raises if any index fails to load. `deviation-index` must be optional, or a missing seed crashes the server. Decided: optional, degrade gracefully, created on first deviation if missing (`create_index` needs at least one doc).
- **Reload semantics**: `_reload_if_live` swallows failures; a swallowed reload failure would silently break "retrievable immediately". Judge endpoint reports `retrievable: false` if the reload fails after a successful write (200 with warning).
- **Chunk-on-screen authority**: the WS worker's state is per-connection and not addressable from REST; the client snapshots chunk id/text at Submit click and sends it. A stale client can send a stale chunk; accepted.
- **Retrieval-key mismatch**: stored text is `caller situation + deviation summary` but queries are the caller trailing window only, so relevance is not guaranteed. Mitigated by a minimum score cutoff and by storing `whatHappened` plus a trailing slice of the caller transcript as the situation, falling back to the transcript. `protocolChunkId` stored in metadata for future exact-match filtering.
- **Voice**: the caller mic/sample and the dispatcher mic share one client voice state; sample-call audio through speakers would bleed into a live dispatcher mic. Decided: separate channel, mutually exclusive.
- **LLM judgment is heuristic**: "deviated" ≠ "wrong"; copy must be neutral; a deviation can be a good judgment call. Junk input ("asdf") judged "deviated" would pollute the shared index (no delete); short-input guard and validators mitigate.
- **Unreviewed vs authoritative**: protocol index is SME-gated; the deviation index is not. UI must label deviations "unreviewed" and never alter or re-rank the suggested protocol.
- **Testing caveat** (`rules/testing.md`): the LLM verdict quality is an unverified external behavior; mocked-LLM tests only prove self-consistency. Mark the judge story `PASS WITH CAVEATS` unless verified against live DeepSeek.
- **Theme**: `DESIGN.md` describes dark tokens; shipped `style.css` is light (commit c05cd32). New UI uses existing CSS variables only.
- **Privacy/compliance (flag only, no requirements)**: records contain caller transcripts and dispatcher words; demo uses synthetic data; no per-dispatcher attribution stored; caller text goes to DeepSeek.
- **Scope creep risk**: keep the core latency proof and existing loop first in build order.

## Design decisions resolved in the convergence round

- Startup: optional index, graceful degrade.
- Dispatcher mic: separate channel field on `voice_start`, mutually exclusive with caller mic/sample.
- Mock buttons: fill the textarea with canned text (written for the sample call's chunk), user presses Submit, real LLM judges.
- Retrieval: top 2, minimum score cutoff, labelled "Moss retrieved" and "unreviewed", neutral wording.
- Defaults chosen without asking: REST endpoint for Submit (not WS); Submit disabled when text is empty, no protocol chunk is on screen, or a request is in flight; verdict card persists until next Submit and shows submitted text; input/reason clear on success and are preserved on failure; Ctrl/Cmd+Enter submits; new-record retrieval has no special highlight; deviations page has no pagination; dedicated `GET /api/deviations` returning parsed, newest-first records; Related Deviations placed between the instruction steps and the dispatch action button; Dispatcher panel in the left column under Caller Transcript; card accent teal (Moss family), red reserved for the verdict.

## Open questions

- Non-blocking: exact score cutoff value — tune against the seed data during implementation.
- Non-blocking: whether seeded records need a visible "sample" marker on the deviations page (recommend a `seed` metadata flag shown as a small tag).
- Non-blocking: `DESIGN.md` still documents the dark theme; reconcile later.
