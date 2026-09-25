# MOS-STORY-003-002: Jev deviation verdict

## Description

As a dispatcher, I want the followed/deviated verdict decided faster and with a confidence score, so that Submit responds quickly and borderline replies are not saved as deviations.

## Acceptance criteria

1. `judge_deviation` calls `decide_follows` first; if P(follows) >= `JEV_FOLLOW_THRESHOLD` it returns `{verdict: "followed", deviationSummary: ""}` without calling DeepSeek.
2. If P(follows) < `JEV_FOLLOW_THRESHOLD` it calls a new summary-only DeepSeek function (one sentence, at most 25 words describing how the reply differs) and returns `{verdict: "deviated", deviationSummary}`; a missing or empty summary raises like the existing invalid-output path.
3. If `decide_follows` returns `None` (down, slow, unconfigured, error) the existing full DeepSeek verdict-plus-summary path runs unchanged; if DeepSeek is also unavailable the existing 503/502 behaviour holds; no new user-visible error text.
4. The `POST /api/deviations/judge` request/response contract, stored record fields and status codes are unchanged; the grey zone (0.3 to 0.5) counts as followed.
5. The verdict source and P(follows) are logged server-side (`logger.info`, no transcript text) for tuning.
6. Existing judge and endpoint tests still pass; new tests cover followed, deviated, boundary at the threshold, and Jev fallback with mocked clients; the caveat that real Jev verdict quality is unverified is recorded.

## Requirements implemented

- User flows step 4-5
- Business rules #5-#7
- architecture.md Judge data flow

## Depends on

- MOS-STORY-003-001

## Agents likely needed

- [ ] frontend
- [x] backend
- [ ] infrastructure

## Status

- [x] Implemented
- [x] Tested
- [x] Committed
