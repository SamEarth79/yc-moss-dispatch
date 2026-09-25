# Gather: Dispatcher Deviation Tracking

## Feature summary
Capture the dispatcher's own response to a caller, compare it against the protocol chunk that was on screen, and record any deviation in a new Moss index (`deviation-index`). On later calls, retrieve related past deviations alongside protocol chunks so the dispatcher sees where experienced dispatchers went off-protocol. Serves dispatchers (and demo viewers) of the Dispatch Copilot.

## User flows
1. Caller talks; the existing protocol chunk appears.
2. Dispatcher responds in a new "Dispatcher Transcript" panel on the main page: type, use the mic, or click one of two mock buttons ("follows protocol" / "deviates"). Optional "reason" field. One Submit button; no periodic/live updates.
3. Backend sends dispatcher text, the protocol chunk on screen at Submit time (id + text), and the caller transcript + structured summary to the LLM (DeepSeek), which returns followed/deviated plus a one-line deviation summary.
4. Followed: nothing stored; inline verdict card says it matched protocol; input clears.
5. Deviated: record written to `deviation-index`; verdict card shows the LLM summary; index reloaded so it is retrievable immediately.
6. During a live call, "Related Deviations" (top 2, tagged "Moss retrieved") appears just below the existing protocol chunk, retrieved from the same caller transcript query as the protocol chunk.
7. `/deviations.html` lists all records, read-only, newest first.

## Scope boundaries
### In scope
- Dispatcher panel: text input, mic input, two mock-reply buttons, optional reason, Submit, verdict card
- LLM followed/deviated judgment and summary
- New `deviation-index` in Moss, seed script with 3-4 realistic deviations
- Deviation retrieval (top 2) on each caller transcript update, shown under the protocol chunk
- Read-only deviations page

### Out of scope
- Security review/hardening
- Edit/delete on the deviations page
- Storing followed submissions
- Using deviations to alter the suggested protocol
- Periodic/streaming dispatcher transcript updates
- Text-file storage (superseded by the Moss index)

## Business rules
1. Only deviations are stored.
2. Comparison is against the single protocol chunk on screen at Submit time.
3. Retrieval key text = caller situation + deviation summary.
4. A stored deviation is retrievable on the next call without a server restart.
5. Optional reason is stored with the record, never required.

## Security & reliability constraints
Deliberately skipped by the user for this design pass.

## Technical & integration constraints
1. Reuse existing patterns: `MossClient`, `_reload_if_live`, LIVE_LOADED_INDEXES, `DocumentInfo`, DeepSeek client in `structured_extraction.py`, existing voice/Deepgram stream and sample-call UI, FastAPI static pages.
2. `deviation-index` created via a seed script modelled on `build_protocol_index.py`, and loaded at startup with the other indexes.
3. If the LLM is not configured, Submit should fail gracefully without crashing the app.
4. Mirror styling in `DESIGN.md` for all new UI.

## Key decisions made
- LLM-based comparison (not semantic score).
- Stored fields: caller transcript + summary, protocol chunk id/text, dispatcher transcript, LLM deviation summary, timestamp, optional reason.
- Two mock sample buttons; inline verdict card; top-2 retrieval; seeded index.

## Deferred / open questions
- None.
