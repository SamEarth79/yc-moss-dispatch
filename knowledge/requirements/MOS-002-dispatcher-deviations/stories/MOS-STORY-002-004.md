# MOS-STORY-002-004: Dispatcher panel + verdict card

## Description

As a dispatcher, I want to type or pick a mock reply and press Submit once to see whether I followed the protocol, so that deviations are captured without interrupting the call.

## Acceptance criteria

1. A "Dispatcher Transcript" section sits under Caller Transcript in the left panel with a labelled textarea, optional reason input, two clearly labelled demo buttons (follows protocol / deviates), and a Submit button, using existing CSS tokens only.
2. Mock buttons fill the textarea with canned text written for the sample call's protocol chunk (replacing existing text, editable afterward); they do not submit.
3. Submit is disabled when text is empty, when no protocol chunk is on screen (with a helper message), or while a request is in flight; Ctrl/Cmd+Enter in the textarea submits.
4. On click the client snapshots the on-screen chunk id/text and posts to `POST /api/deviations/judge` with caller transcript and structured summary.
5. Followed: an inline verdict card (green rule, text "Followed protocol", compared chunk id, submitted text) appears, inputs and reason clear.
6. Deviated: verdict card (red rule, text "Deviated", LLM summary, "LLM generated" tag, "Saved to deviation index" line, or a not-retrievable warning when `retrievable` is false); inputs clear.
7. Errors (503/502/500/network): inline error card with neutral copy, input and reason preserved, Submit re-enabled.
8. Verdict area uses `role="status"` (errors `role="alert"`); controls have real labels; verdict is conveyed by text, not colour alone; verdict card persists until the next Submit.

## Requirements implemented

- User flows steps 2-5
- Scope in-scope items 1-2
- Business rules #1, #2, #5

## Depends on

- MOS-STORY-002-002

## Agents likely needed

- [x] frontend
- [ ] backend
- [ ] infrastructure

## Status

- [x] Implemented
- [x] Tested
- [x] Committed
