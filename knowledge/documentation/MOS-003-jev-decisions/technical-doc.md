# MOS-003: Jev Decision Model Integration

Technical deep dive for engineers who did not build this feature. Source: `backend/jev_client.py` (new), `backend/server.py`, `backend/structured_extraction.py`, `backend/deviation_judge.py`, `backend/conftest.py` (new), and the summary-panel UI in `backend/static/`.

## What it does

Jev is a decision model served through OpenRouter's alpha Decisions API (`POST https://openrouter.ai/api/alpha/decisions`, model `typesafe/jev-1.13`). It answers structured questions ("noul" yes/no probabilities and "choice" distributions) about a piece of text. The feature uses it in two places:

1. **Live extraction refinement.** Keyword rules still produce the instant first answer for the Structured Summary (patients, consciousness, weapons, departments). A background Jev task later overrides a rule value only when Jev is confident. Overridden rows are marked in the UI.
2. **Deviation verdict.** `judge_deviation` asks Jev whether the dispatcher reply follows the protocol chunk. DeepSeek is only used to write the one-sentence deviation summary when Jev says "deviated". If Jev is unavailable, the previous full DeepSeek verdict runs unchanged.

DeepSeek stays the only source of prose (`whatHappened`, `deviationSummary`).

## Requirements and fallback behavior

- `OPENROUTER_API_KEY` (in `backend/.env`, placeholder in `backend/.env.example`) is required for Jev. Without it, `_get_client()` returns `None` and every Jev function returns `None`. Nothing errors: extraction stays on rules (plus DeepSeek headline) and the judge uses the DeepSeek-only path. The only visible trace is a dev-feed line (see below).
- The client is rebuilt if the env var value changes between calls.
- The endpoint is an **alpha** API (`/api/alpha`). Its path, request shape or response shape can change without notice; all parsing is isolated in `jev_client.py` so a change is a one-file fix.
- Security lens: the design was drafted without security sign-off; the user explicitly skipped the security lens for this feature. Notably, caller transcripts and dispatcher replies are sent to a third party (OpenRouter). Logs contain no transcript text or API key (tests assert this).

## Components

### `backend/jev_client.py` (new)

Public functions, both async, both never raise (except `asyncio.CancelledError`) and return `None` on missing key, timeout, any exception, or a response without an `answers` object:

- `decide_extraction(text) -> dict | None`: one batched request with six questions: `weapon`, `unconscious`, `police`, `ems`, `fire` (noul) and `patients` (choice with keys `"0"` to `"10"`; `"0"` means nobody hurt). `state` is `{"caller_transcript": text}` (full transcript). Returns `{field: probability}` for noul answers and `"patients": (choice_str, confidence)`. Malformed individual answers (wrong type, bool, out-of-range number, unknown patients choice) are dropped while the rest are returned; an empty dict is possible.
- `decide_follows(protocol_chunk_text, dispatcher_text, caller_transcript, reason) -> float | None`: one noul question `follows_protocol`; `state` has `caller_transcript`, `protocol_instruction`, `dispatcher_reply`, plus `dispatcher_reason` only when a reason is given. Returns P(follows).

Constants (single tuning point):

| Constant | Value | Meaning |
|---|---|---|
| `JEV_MODEL` | `typesafe/jev-1.13` | model id |
| `JEV_BASE_URL` | `https://openrouter.ai/api/alpha` | |
| `JEV_CONFIDENCE_HIGH` | 0.7 | noul >= this is confident true; patients confidence >= this is used |
| `JEV_CONFIDENCE_LOW` | 0.3 | noul <= this is confident false |
| `JEV_FOLLOW_THRESHOLD` | 0.3 | P(follows) >= this is "followed" |
| `EXTRACTION_TIMEOUT_S` | 1.5 | per-request timeout, extraction |
| `JUDGE_TIMEOUT_S` | 3.0 | per-request timeout, judge |

Values between 0.3 and 0.7 (exclusive) are "uncertain" and never override anything. The thresholds were validated on only a few cases.

### `backend/structured_extraction.py`

- `merge_jev_fields(rule_fields, jev_answers) -> (fields, sources)`: pure. Weapon true/false maps to `weapons` True/False; unconscious true/false maps to `consciousness` `"unconscious"`/`"conscious"`; a confident `patients` choice sets `numberOfPatients` (int); departments start from the rule list and Jev's confident police/ems/fire answers add or remove `Police`, `Emergency Medical`, `Fire`, returned in that canonical order. `sources` is `{field: "jev"}` only where the merged value differs from the rule value. Inputs are not mutated.
- `jev_confident_fields(jev_answers, rule_fields=None) -> set`: which fields Jev was confident about (used to decide when to clear sticky overrides, including when Jev agrees with the rules).
- Both share `_applies_bool`: a confident **False** on weapons/unconscious does **not** apply when the rule value is `None` (unknown). Unknown is not "no". A confident True still applies from `None`.

### `backend/server.py`

- Constants `JEV_SETTLE_DELAY_S = 0.6` (trailing-edge wait) and `JEV_MIN_GAP_S = 0.8` (minimum gap between Jev call starts).
- `new_llm_state()` builds per-connection state: DeepSeek fields/task, `jev_task`, `jev_last_start`, and `jev_state` (`overrides`, `sources`). `ws_session` creates it and passes it to `transcript_worker` (new optional `llm_state` argument) so `set_caller` can reset it.
- `run_jev_extraction`: sleeps the settle delay, then sleeps whatever remains of the minimum gap since the previous call start, records the start, calls `decide_extraction`, and merges. A newer transcript cancels the task (so during the settle delay no call is made).
- `build_extraction_payload(rule_fields, llm_state)`: every `extraction_update` is built as rule fields + DeepSeek fields + sticky Jev overrides, plus a `sources` map inside `fields`.
- `reset_jev`: cancels the Jev task and clears sticky state.

### `backend/deviation_judge.py`

`judge_deviation` now: Jev first (`decide_follows`); `None` runs `_judge_with_deepseek` (the original path, unchanged prompt and result); P >= 0.3 returns `{"verdict": "followed", "deviationSummary": ""}` without calling DeepSeek; P < 0.3 calls `_summarize_deviation_with_deepseek` (new `SUMMARY_SYSTEM_PROMPT`, max 150 tokens, no caller transcript) and returns `deviated`. Empty/missing/non-string/non-JSON summaries raise `ValueError` (the endpoint maps that to 502 as before); DeepSeek unconfigured after a Jev "deviated" verdict returns `None` (endpoint 503). One info log line per judgement with `source` (`jev` or `deepseek-fallback`), verdict and `p_follows`; no text content.

`devLog` entries have the shape `{service, callType, latencyMs, summary}`, built by `_jev_verdict_entry` with `service` `"jev"`, `callType` `"verdict"` and `latencyMs` the Jev call duration in milliseconds (rounded to 0.1). The `summary` is exactly one of:
- `P(follows)=0.xx → followed` (two decimals)
- `P(follows)=0.xx → deviated`
- `skipped (unavailable), DeepSeek fallback` (Jev returned `None`; the DeepSeek verdict decided)

If the judge returns `None` (503) or raises, there is no `devLog`.

### Frontend (`backend/static/`)

- `index.html`: a `source-tag-group` in the summary panel holding a hidden `#jevTag` ("Jev") next to the existing "LLM generated" tag, and a visually hidden `#jevStatus` (`role="status"`, `aria-live="polite"`).
- `app.js` `renderExtraction`: reads `fields.sources`. Shows the Jev tag when `sources` is non-empty; rows sourced from Jev get a lavender dot plus visually hidden "refined by Jev" text. A row flashes (`kv-row--changed`, 600 ms fade) only when its displayed value changed since the previous render AND it is Jev-sourced; plain rule changes never flash or announce. Changes are announced through `#jevStatus` ("<Row> updated to <value> by Jev"). Rows are now built with `textContent` rather than `innerHTML`. Changing the caller clears the tag, dots and status and resets the change baseline.
- `app.js` `renderDevLog` (used by `dev_log` websocket messages and by judge `devLog` entries) now builds each row with `createElement` and `textContent` instead of `innerHTML`, and reduces the service to a class suffix by lowercasing and stripping everything except `a-z`, `0-9` and `-`. The feed row's visible service text is the raw `service` value.
- `style.css`: `.dev-log-service--jev` (lavender text on a translucent violet background) and `.dev-log-entry--jev .dev-log-latency` (lavender), plus `.source-tag--jev`, `.source-tag-group`, `.jev-dot`, `kv-row-flash`, disabled under `prefers-reduced-motion: reduce`. The hidden tag uses `visibility: hidden` so the layout does not shift.

## Data flow

Extraction:
1. Transcript arrives; rules run; `extraction_update` is sent immediately (with any still-valid sticky Jev overrides applied).
2. DeepSeek headline task and Jev task start in the background; the previous ones are cancelled.
3. Jev task waits 0.6 s, enforces 0.8 s since the last call start, calls `decide_extraction` (1.5 s timeout).
4. On answers: sticky state updated (below), a second `extraction_update` with `sources` is sent, then a `dev_log` line `service "jev"`, `callType "decisions"`, summary like `6 checked, 1 overridden (weapons: no→yes)`.
5. On `None`: only a `dev_log` line `skipped (unavailable), rule values kept`. The UI shows nothing.

Judge: see `deviation_judge.py` above; the REST contract is unchanged apart from the additive `devLog` key (below).

Judge dev log: `judge_deviation` times the `decide_follows` call and attaches `devLog`, a one-entry list, to its result. `POST /api/deviations/judge` passes it through on both 200 responses (`followed` and `deviated`). The client posts the reply, renders the verdict card, then calls `renderJudgeDevLog(result.devLog)`, which ignores non-arrays and skips malformed entries before calling `renderDevLog`.

## Sticky overrides (implementation differs from architecture.md)

`architecture.md` described sticky Jev values as simple values. As built:

- Each sticky override is `{"value": ..., "rule": <rule value it was decided against>}`. `build_extraction_payload` drops any override whose remembered rule value no longer equals the current rule value, so a fresher rule value (e.g. weapons True on "knife" after Jev said False) is not masked until Jev answers again. This came from a live-run finding.
- `sources` lists only applied overrides whose value differs from the current rule value.
- After a Jev answer, every field Jev was confident about is first removed from sticky state, then re-added only if the merged value differs from the rule value. So a confident Jev answer that agrees with the rules clears the override; an uncertain answer leaves the previous sticky value in place; a newer confident answer replaces it.
- An empty transcript (`text` falsy) calls `reset_jev` (cancels the task, clears sticky state). `set_caller` also calls `reset_jev`, but it does **not** send an `extraction_update`; the client clears its own Jev tag/dots on caller change and re-renders with `sources: {}`.
- Jev confident-False on weapons/unconscious does not override an unknown (`None`) rule value (see `_applies_bool`).

## Other differences from `architecture.md`

- **Transport**: the installed `openai` SDK's raw `client.post("/decisions", body=..., cast_to=dict, options={"timeout": ..., "max_retries": 0})` worked against the alpha path (confirmed live), so the `httpx` fallback was not needed and `httpx` stays a dev-only dependency. No runtime dependency was added.
- **Fallback dev-feed line** is always `skipped (unavailable), rule values kept`. The design's example `skipped (timeout 1.5s)` is not produced; timeout, missing key and malformed response are indistinguishable there (the reason is only in the warning log: exception class name or "no answers object").
- **Dev-feed value rendering**: `format_jev_value` renders `None` as `unknown` (so `weapons: unknown→yes`), booleans as yes/no, lists comma-joined or `none`.
- **Judge summary-only prompt** receives the protocol chunk, dispatcher reply and optional reason, but not the caller transcript.
- `merge_jev_fields`/`jev_confident_fields` gained the `rule_fields` unknown-handling described above, which the architecture did not specify.
- **Test isolation**: `backend/conftest.py` has two autouse fixtures stubbing `deviation_judge.decide_follows` and `server.decide_extraction` to return `None`, so pre-existing tests stay offline and deterministic on the fallback paths even if `OPENROUTER_API_KEY` is exported. Jev-specific tests override them.
- The Jev task and the DeepSeek headline task are separate; they touch disjoint keys (`whatHappened` vs. the four rule fields), so they do not race.

## Operational notes

- Set `OPENROUTER_API_KEY` in `backend/.env`. Without it the app silently uses rules and DeepSeek; check the dev feed for `jev / decisions: skipped (unavailable)` lines to diagnose.
- Cost/load: at most one extraction call per ~0.8 s per connection, and only after the transcript is quiet for 0.6 s. Tune `JEV_SETTLE_DELAY_S` / `JEV_MIN_GAP_S` in `server.py`, and thresholds/timeouts in `jev_client.py`.
- Judge latency with Jev is sequential: about 0.9 s (followed, cold) and about 1.75 s (deviated, Jev then DeepSeek), as measured live.
- Tests: `cd backend && uv run pytest -q` (361 passed at the end of the feature including 93 Playwright e2e; non-e2e 268 passed).

## Verification performed and caveats

Live checks by the orchestrator:
- Transport and response shape against real OpenRouter for extraction (sample call: weapon 0.96, unconscious 0.97, police 0.99, ems 0.99, fire ~0.21-0.24, patients `('2', 0.98)`; 935 ms cold, ~325-375 ms warm).
- Judge on 2 cases: a following reply gave P(follows)=0.87 (followed); a deviating reply ("water") gave 0.01 (deviated, summary "Advised water and rest instead of back blows and abdominal thrusts.").
- One live websocket session on the sample call: Jev overrode nothing because the rules were already right. This session also produced the two fixes above (stale sticky, unknown != no).

Unverified (from `test-results.md`, verdict PASS WITH CAVEATS on stories 001, 002, 003, 004, 005):
- Automated tests are mock-only; real Jev accuracy is not verified in CI, and the 0.7 / 0.3 / 0.3 thresholds were validated on few cases.
- Only 2 live judge cases were tried.
- No real-Jev override was observed end to end in a browser; e2e runs against a stub `/ws`. Lavender tag contrast was computed, not tool-measured.
- Observation: the initial `renderExtraction({})` seeds previous values, so the first `extraction_update` after page load compares against empty values.

## How to extend safely

- Add a new Jev question in `jev_client.py` (question dict, parse it in `decide_extraction`), map it in `merge_jev_fields` and `jev_confident_fields` together (they must stay in agreement so sticky clearing works), and add its row key to `renderExtraction` if it is a displayed field.
- Keep all response parsing in `jev_client.py`; callers should only see plain values or `None`.
- Any new `extraction_update` sender must go through `build_extraction_payload` so sticky overrides and `sources` are not lost.
- Do not let Jev supply prose; keep DeepSeek for summaries.

## Shadow mode (summary toggle)

Jev extraction runs in **shadow mode by default**: `decide_extraction` is still called on every settled transcript and a `jev / decisions` line is sent to the developer feed (for example `6 checked, 2 differ from rules (weapons: yes→no) — shadow mode, summary unchanged`), but Jev never changes the Structured Summary: no sticky overrides are stored, no `extraction_update` is sent by the Jev task, `sources` stays `{}` and the "Jev" tag never appears. The fallback line (`skipped (unavailable), rule values kept`) is unchanged.

Set the environment variable `JEV_AFFECTS_SUMMARY` to `1`, `true`, `yes` or `on` (case-insensitive) to let Jev override the rule values again. It is read on every call (`server.jev_affects_summary()`), so it needs no code change, only an environment change and restart. The deviation judge is not affected by this flag: it still asks Jev first, then DeepSeek.
