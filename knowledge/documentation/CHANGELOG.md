# Changelog

Newest first. Format follows Keep a Changelog. No versioning convention exists in the repo, so entries are dated.

## 2026-09-25: MOS-002 Dispatcher Deviation Tracking

### Added
- `POST /api/deviations/judge`: a DeepSeek verdict (`followed` / `deviated`) on a dispatcher reply versus the protocol chunk on screen. Deviations are saved to a new Moss index, `deviation-index`, and are retrievable immediately.
- `GET /api/deviations` and a read-only `/deviations.html` page listing all recorded deviations, newest first.
- "Dispatcher Transcript" panel in the live UI: typed input, dispatcher mic, two mock-reply buttons, optional reason, Submit, and a verdict card.
- "Related Deviations" block under the protocol instruction, fed by a new `deviation_update` WebSocket message (up to 2 matches, minimum score 0.3).
- Dispatcher voice channel on `/ws` (`voice_start` / `voice_stop` with `channel: "dispatcher"`, `dispatcher_voice_transcript` messages).
- `backend/build_deviation_index.py` and `backend/deviation_seed.py` to create `deviation-index` with 3 synthetic records. Must be run once per Moss project.
- Deviations nav link on the main and Manage Indexes pages.

### Changed
- Server startup now tries to load `deviation-index` as an optional index; a missing or failing index only logs a warning.
- `deviation-index` is in `LIVE_LOADED_INDEXES`, so MOS-001 document edits on it reload the in-memory copy.
- Voice messages accept an optional `channel` field (default `caller`, so existing clients are unaffected).
