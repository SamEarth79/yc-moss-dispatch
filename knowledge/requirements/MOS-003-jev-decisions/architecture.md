# Architecture: Jev Decision Model Integration

> Drafted by the `design-developer` lens. **No security sign-off** — the user explicitly skipped the security lens.

## Approach

A new isolated module, `backend/jev_client.py`, wraps the OpenRouter Decisions API. It exposes `decide_extraction(text)` and `decide_follows(...)`; each returns parsed plain values or `None` and never raises (except `CancelledError`). Keyword rules stay the instant first answer. A background Jev task in `transcript_worker` refines them: it runs after the transcript settles, overrides rule values only when Jev is confident, and keeps the last confident override sticky across later transcripts in the same call. The deviation judge asks Jev first (one noul question) and calls DeepSeek only to write the deviation summary; if Jev is unavailable, the existing full DeepSeek verdict runs unchanged. DeepSeek remains the only source of prose.

## Components touched

- **Frontend**: `static/app.js` (`renderExtraction` reads `fields.sources`, changed-row cue, panel-level Jev tag), `index.html` (tag group in the summary panel), `style.css` (`.source-tag--jev`, `.source-tag-group`, fade cue with `prefers-reduced-motion`).
- **Backend**: new `jev_client.py`; `server.py` (`transcript_worker` Jev task with trailing-edge + min-gap, sticky Jev state, `extraction_update` `sources`, dev-feed lines, reset on `set_caller`); `structured_extraction.py` or `jev_client.py` (pure `merge_jev_fields`); `deviation_judge.py` (Jev-first flow, summary-only DeepSeek function).
- **Infrastructure**: `OPENROUTER_API_KEY` in `.env` and `.env.example`; no new runtime dependency planned (see decisions).

## Data flow

Extraction:
1. Transcript arrives; rules run; `extraction_update` is sent as today (`sources` empty or carrying the sticky Jev values already applied).
2. The DeepSeek headline task runs as today. A separate Jev task waits ~600 ms for the transcript to stop changing (trailing edge), enforces >= ~800 ms since the previous Jev call start, then calls `decide_extraction(full_transcript)` — one batched request with 6 questions: `weapon`, `unconscious` (noul), `patients` (choice 0-10 with a "nobody hurt" option for 0), `police`, `ems`, `fire` (noul). A newer transcript cancels it.
3. `merge_jev_fields(rule_fields, jev_answers)` returns `(fields, sources)`: yes/no `>=0.7` true / `<=0.3` false else keep; patients choice used only if confidence `>=0.7`; unconscious true -> `unconscious`, false -> `conscious`; departments start from the rule list, add/remove per confident police/ems/fire answers in canonical order. `sources` lists a field only when the Jev value differs from the rule value.
4. Confident answers update the sticky Jev state in `llm_state`; every `extraction_update` is built as rule fields + DeepSeek headline + sticky Jev overrides, so rule updates never flash over Jev values. Sticky state resets on `set_caller`.
5. `dev_log_payload("jev", "decisions", ms, "<n> checked, <m> overridden (weapons: no→yes…)")`, or a fallback line ("skipped (timeout 1.5s), rule values kept").

Judge:
1. `judge_deviation` calls `decide_follows(protocol_chunk_text, dispatcher_text, caller_transcript, reason)` (timeout ~3 s).
2. P(follows) `>= JEV_FOLLOW_THRESHOLD` (0.3) -> `{"verdict": "followed"}`, nothing saved.
3. P(follows) `< 0.3` -> DeepSeek summary-only call writes `deviationSummary`; record stored as today.
4. `None` from Jev -> existing full DeepSeek verdict path, unchanged.

## Data model changes

No storage changes. `extraction_update` gains an additive key `sources: {"weapons": "jev", ...}` inside the payload (only fields where Jev overrode the rule). The judge response is unchanged.

## API surface

- New env var `OPENROUTER_API_KEY`.
- Outbound only: `POST https://openrouter.ai/api/alpha/decisions` with body `{model: "typesafe/jev-1.13", state, questions}`; noul answers `{noul}`, choice answers `{choice, probabilities, confidence}`. Response parsing lives only in `jev_client.py`.
- WS `extraction_update` payload: additive `sources` map. No new routes or messages.

## Key decisions

- **Decision**: separate Jev task instead of folding into `run_llm_extraction`.
  **Rationale**: DeepSeek can be slower and would gate Jev; the tasks touch disjoint keys so they do not race.
- **Decision**: trailing-edge (~600 ms) + minimum gap (~800 ms) call policy, cancel-if-newer retained.
  **Rationale**: bounds cost/endpoint load on an alpha endpoint; a 50 ms-debounced call per update would mostly be cancelled.
- **Decision**: sticky server-side overrides, `sources` map instead of a client diff.
  **Rationale**: prevents rule -> Jev -> rule flicker; the client cannot tell a Jev change from a rule change.
- **Decision**: transport via the installed `openai` SDK's raw `post` with per-request `timeout` and `max_retries=0`; fall back to `httpx` promoted to a runtime dependency if `cast_to=dict` does not work against the alpha path.
  **Rationale**: no new dependency, matches the DeepSeek client pattern; retries would hide timeouts.
- **Decision**: extraction `state` is the full transcript; judge state is the client-sent caller transcript plus protocol chunk and reply.
  **Rationale**: extraction facts may be stated early; judge inputs are already bounded.
- **Decision**: threshold constants (`JEV_CONFIDENCE_HIGH=0.7`, `JEV_CONFIDENCE_LOW=0.3`, `JEV_FOLLOW_THRESHOLD=0.3`, timeouts 1.5 s extraction / 3 s judge) live together in `jev_client.py`.
  **Rationale**: single tuning point; thresholds validated on only a few cases.
- **Decision**: fallback logged in the dev feed only, never surfaced as a UI error.
  **Rationale**: silent fallback must still be diagnosable; user asked for no visible errors.
