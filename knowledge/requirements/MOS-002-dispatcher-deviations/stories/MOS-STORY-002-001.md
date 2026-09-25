# MOS-STORY-002-001: Deviation index + seed

## Description

As a developer, I want a `deviation-index` in Moss seeded with realistic deviations that the server loads optionally, so that retrieval and the deviations page have data from the first run.

## Acceptance criteria

1. `DEVIATION_INDEX_NAME = "deviation-index"` is defined in `backend/live_panel.py` and imported where used.
2. `backend/deviation_seed.py` holds 3-4 synthetic deviation records (choking / cardiac arrest scenarios) referencing real `protocolChunkId` values from `protocol_chunks.py`, each with the metadata fields in `architecture.md` (all string values, `type: "deviation"`, `seed: "true"`).
3. `backend/build_deviation_index.py` deletes-then-creates `deviation-index` from the seed, mirroring `build_protocol_index.py`.
4. `lifespan` loads `deviation-index` alongside the other indexes; if it is missing or fails to load, the server logs a warning and starts normally (existing two indexes still fail hard).
5. `deviation-index` is in `LIVE_LOADED_INDEXES` so manage-page edits reload it, and it is unloaded on shutdown when it was loaded.
6. The index appears in `/api/indexes` and in the Manage Indexes page.

## Requirements implemented

- Business rules #1, #4
- Technical constraints #1, #2
- architecture.md Data model changes; Key decisions (optional startup)

## Depends on

-

## Agents likely needed

- [ ] frontend
- [x] backend
- [ ] infrastructure

## Status

- [x] Implemented
- [x] Tested
- [x] Committed
