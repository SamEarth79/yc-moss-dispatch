# MOS-STORY-002-007: Deviations page

## Description

As a user, I want a page listing every recorded deviation, so that I can review what dispatchers did differently.

## Acceptance criteria

1. `GET /api/deviations` returns all records from `deviation-index` as `{id, timestamp, callerTranscript, callerSummary, protocolChunkId, protocolChunkText, dispatcherTranscript, deviationSummary, reason, seed}` sorted newest first; returns an empty array if the index does not exist; 500 with a safe message on Moss failure.
2. `backend/static/deviations.html` + `deviations.js` render a read-only list styled like the manage page (header, `.panel` records, key-value grid, show-more clamp), with loading, empty, error (with Retry) and populated states and a record count.
3. Seeded records show a small "sample" tag.
4. Timestamps use `<time datetime>`; the page has `<main>`, `lang`, and a `<title>`; the grid collapses to one column under 640px.
5. A "Deviations" nav link exists in the headers of `index.html` and `manage.html`, and the new page links back to both.
6. No edit or delete controls appear.

## Requirements implemented

- User flows step 7
- Scope in-scope item 5
- Out of scope: edit/delete

## Depends on

- MOS-STORY-002-001

## Agents likely needed

- [x] frontend
- [x] backend
- [ ] infrastructure

## Status

- [x] Implemented
- [x] Tested
- [x] Committed
