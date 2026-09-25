# MOS-STORY-002-003: Deviation retrieval on live call

## Description

As a dispatcher, I want related past deviations retrieved for the current caller transcript, so that I see how others handled similar situations.

## Acceptance criteria

1. `transcript_worker` runs a top-2 query on `deviation-index` with the same trailing-window `query_text` as the protocol query, concurrently with it.
2. Results below a minimum relevance score are dropped, so 0-2 deviations are sent.
3. A `deviation_update` WS message `{deviations: [{id, summary, dispatcherTranscript, reason, timestamp, score}]}` is sent after each `protocol_update`.
4. A dev-feed log entry (`moss`, `deviation-query`) with latency is sent.
5. If `deviation-index` is not loaded, the worker sends an empty `deviation_update` and the protocol path is unaffected.
6. A deviation stored via the judge endpoint appears in a subsequent retrieval without a server restart.

## Requirements implemented

- User flows step 6
- Business rules #3, #4
- architecture.md Data flow step 7

## Depends on

- MOS-STORY-002-001

## Agents likely needed

- [ ] frontend
- [x] backend
- [ ] infrastructure

## Status

- [x] Implemented
- [x] Tested
- [x] Committed
