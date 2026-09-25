# Analysis: Jev Decision Model Integration

## Summary

Add Jev (`typesafe/jev-1.13`, structured decision model via the OpenRouter Decisions API) to refine the keyword-rule extraction fields (weapon, unconscious, patients, departments) in the background, and to decide the deviation verdict, with DeepSeek kept only for prose. Security lens skipped by the user (no `design-security` review or sign-off).

## Relevant existing code

- `backend/structured_extraction.py` — `extract_rule_fields` (instant regex rules), DeepSeek `_get_client`/`extract_llm_fields` (headline only), model constants.
- `backend/server.py` — `transcript_worker` (latest-wins, cancel-if-newer, `llm_state`), `run_llm_extraction`, `timed`, `dev_log_payload`, `extraction_update` payload `{**rule_fields, **llm_state["fields"]}`, `POST /api/deviations/judge`, `set_caller` reset points.
- `backend/deviation_judge.py` — current DeepSeek verdict + summary call and `judge_deviation` contract (dict|None, raises on bad output).
- `backend/static/app.js`, `index.html`, `style.css` — `renderExtraction`/`makeRow`, `.source-tag--llm`/`--moss`, summary panel, `latestFields`.
- `backend/pyproject.toml` — `openai` is a runtime dep (httpx transitively); `httpx` itself is dev-only.
- Tests: `test_server.py`, `test_deviation_judge.py`, `test_deviation_retrieval.py`, `tests/e2e/*` (stub-app Playwright pattern).

## Measurements from the design session (throwaway scripts, real Jev)

- 1 question ~350-390 ms; 4-6 batched questions ~370-400 ms median; outliers up to ~1.2 s.
- Weapon: correct incl. negation (0.97 / 0.92 yes cases, 0.01-0.04 no cases).
- Patients as choice 0-10: correct on 1/2/3/5; a 1-10-only choice forced a wrong answer on a no-injury call, so include a 0 option. An 11-level `score` question returned HTTP 400 (avoid `score`).
- Department single choice is insufficient (stabbing: police 0.77 / ems 0.23), so one noul per department.
- Verdict (dispatcher reply vs protocol chunk): deviations scored 0.01-0.02, clear follows 0.79-0.90, one correct-but-terse CPR reply 0.49-0.51. Threshold set at deviated when P(follows) < 0.3.

## Constraints and risks

- **Alpha endpoint** (`/api/alpha/decisions`): shapes may change; isolate in one module. Pricing/rate limits unknown — verify before the demo.
- **Flicker**: rules answer instantly, Jev 400 ms-1.2 s later; overrides must be sticky server-side and re-applied over fresh rule output (decided).
- **Call volume**: transcript worker wakes on every update; use trailing-edge (~600 ms after the transcript settles) plus a minimum gap (~800 ms) between call starts; cancel-if-newer still applies (decided).
- **Confidence policy**: yes/no `>=0.7`/`<=0.3`, choice confidence `>=0.7` (decided); thresholds validated on the verdict, only lightly on extraction — tune later.
- **Semantic leaps**: confident "not unconscious" maps to `conscious`; departments are add/remove by confident yes/no; "0 patients" must be displayable (panel currently shows a number; 0 is a valid value).
- **Full transcript vs window**: extraction uses the full transcript (facts may be stated early); the judge uses the caller transcript already sent by the client.
- **Two Jev outputs can disagree** (extraction panel vs judge); acceptable, no reconciliation planned.
- **Silent fallback hides regressions**: log `jev / decisions` fallback lines in the dev feed.
- **Third-party data flow**: 911-style transcripts go to OpenRouter/TypeSafe; use synthetic data for the demo (flag only, no requirements).
- **Testing** (`rules/testing.md`): mocks prove only self-consistency; real Jev behaviour is `PASS WITH CAVEATS`; run a live check before the demo.
- The `dispatch-copilot-idea.md` file referenced by the business lens is not present in the repo root; not blocking.

## Decisions resolved

Override only when confident and sticky until Jev re-answers; trailing-edge + min-gap call policy; per-panel "Jev" tag plus subtle changed-row cue (no per-field tag clutter); dev feed lines for extraction and verdict; no demo on/off toggle; judge built first; grey zone (0.3-0.5) counts as followed.

## Open questions

- Non-blocking: real Jev pricing / credit cap on the OpenRouter key; whether a fixture/replay mode is wanted in case the alpha endpoint is down during judging.
- Non-blocking: vaguer patient phrasing ("a bunch of people") untested.
- Non-blocking: whether `openai` SDK's raw `post` works against the alpha base path (implementation checks; fall back to promoting `httpx` to a runtime dependency).
