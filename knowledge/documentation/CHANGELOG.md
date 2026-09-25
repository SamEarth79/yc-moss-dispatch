# Changelog

Newest first. Format follows Keep a Changelog. No versioning convention exists in the repo, so entries are dated.

## 2026-09-25: Jev shadow mode

### Changed
- Jev extraction now runs in shadow mode by default: it still runs and logs `jev / decisions` lines to the developer feed, but no longer changes the Structured Summary (no overrides, `sources` stays empty, no Jev tag). Set `JEV_AFFECTS_SUMMARY=true` to restore overrides. The deviation judge is unaffected.

## 2026-09-25: MOS-003 Jev Decision Model Integration

### Added
- Jev (OpenRouter Decisions API, `typesafe/jev-1.13`) client in `backend/jev_client.py`. Requires the new `OPENROUTER_API_KEY` env var (placeholder in `backend/.env.example`); without it the app silently keeps using rules and DeepSeek.
- Background Jev refinement of the Structured Summary (patients, consciousness, weapons, departments): overrides rule values only when confident (>= 0.7 true, <= 0.3 false), stays sticky across later transcripts in the same call, and resets on caller change or empty transcript.
- `extraction_update.fields.sources` (e.g. `{"weapons": "jev"}`): lists fields where a Jev value differs from the rule value.
- Summary panel shows a "Jev" tag, a dot on Jev-refined rows, a short fade on Jev-changed rows (off under reduced motion) and a polite screen-reader announcement.
- Dev feed lines `jev / decisions` with latency and what was overridden, or `skipped (unavailable), rule values kept` on fallback.
- `POST /api/deviations/judge` 200 responses gain an additive `devLog` array; the developer feed shows a `jev / verdict` line (e.g. `P(follows)=0.87 → followed`, or `skipped (unavailable), DeepSeek fallback`) with lavender `jev` styling.
- `backend/conftest.py`: autouse stubs keep tests offline on the fallback paths.

### Changed
- `POST /api/deviations/judge` asks Jev first (P(follows) >= 0.3 is `followed`); DeepSeek is then only called to write the summary of a deviation. If Jev is unavailable the original DeepSeek verdict runs. Request and response shapes are unchanged.
- Jev extraction calls are rate-limited: 0.6 s after the transcript settles and at least 0.8 s between calls (`JEV_SETTLE_DELAY_S`, `JEV_MIN_GAP_S` in `server.py`).
- Structured Summary rows and developer-feed rows are now built with `textContent` instead of `innerHTML`.

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
