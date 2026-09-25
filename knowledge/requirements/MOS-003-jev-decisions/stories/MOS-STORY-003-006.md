# MOS-STORY-003-006: Jev calls in the developer feed

## Description

As a developer watching the demo, I want every Jev call to show up in the developer feed with its latency, so that the model's contribution and speed are visible next to the Moss and LLM calls.

## Acceptance criteria

1. The developer feed styles `jev` entries like the existing `moss`/`llm`/`asr` entries: a `.dev-log-service--jev` label using the lavender token and matching `.dev-log-entry--jev .dev-log-latency` styling, using existing CSS variables only.
2. `POST /api/deviations/judge` responses gain an additive `devLog` array (the existing keys and status codes are unchanged) whose entries have the same fields as WS dev-log messages (`service`, `callType`, `latencyMs`, `summary`).
3. When Jev decides the verdict, `devLog` contains a `jev` / `verdict` entry with the measured Jev latency and a summary such as `P(follows)=0.01 → deviated` or `P(follows)=0.87 → followed`, with no transcript or reply text.
4. When Jev is unavailable and the DeepSeek fallback runs, `devLog` contains a `jev` / `verdict` entry `skipped (unavailable), DeepSeek fallback` with its latency, so the fallback is visible in the feed.
5. After each Submit response the frontend appends every `devLog` entry to the developer feed using the existing renderer (newest first, existing max-entries trimming); error responses (503/502/500) add nothing.
6. The feed renderer does not interpret entry fields as HTML for the new entries (use `textContent`), and the existing `moss`/`llm`/`asr`/`jev` WS entries continue to render unchanged.
7. Backend tests cover Jev-decided followed and deviated, the fallback entry, and no `devLog` secrets/text; E2E tests cover the feed entries after Submit, the `jev` label class, and no entries on error.

## Requirements implemented

- Key decisions (attribution: dev feed line plus panel tag)
- User flows step 3-4
- architecture.md Judge data flow (dev-feed wording)

## Depends on

- MOS-STORY-003-002
- MOS-STORY-003-004

## Agents likely needed

- [x] frontend
- [x] backend
- [ ] infrastructure

## Status

- [x] Implemented
- [x] Tested
- [x] Committed
