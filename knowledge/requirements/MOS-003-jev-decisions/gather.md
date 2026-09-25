# Gather: Jev Decision Model Integration

## Feature summary
Add Jev (`typesafe/jev-1.13`, a structured decision model reached through the OpenRouter Decisions API) to two places: (1) a background check that corrects the keyword-rule extraction fields (weapon, unconscious, patient count, departments) on each caller transcript update, and (2) the deviation verdict in the dispatcher deviation judge. DeepSeek stays only for prose (the `whatHappened` headline and the deviation summary sentence). Serves dispatchers and demo viewers by making the summary panel more accurate and the deviation judgment faster and confidence-aware.

## User flows
1. Caller transcript updates; instant keyword rules fill the Structured Summary as today.
2. In the background, one batched Jev call (weapon, unconscious, patients, police, ems, fire) runs, cancelled and replaced if a newer transcript arrives (same pattern as the existing DeepSeek headline call).
3. When Jev is confident and disagrees with a rule value, the panel updates to Jev's value; the panel shows a small "Jev" tag and the dev feed logs a `jev / decisions` line with latency.
4. Dispatcher presses Submit: one Jev noul question ("does the reply give the same guidance as the protocol instruction?") decides. If P(follows) >= 0.3 the reply counts as followed and nothing is saved. If P(follows) < 0.3 the reply is a deviation: DeepSeek writes the one-line deviation summary, and the record is stored as before.
5. If Jev is slow, down, unconfigured or errors, the old behaviour runs silently: rule values stay (extraction) and the DeepSeek judge runs (deviation). No user-visible error.

## Scope boundaries
### In scope
- New Jev client module (OpenRouter Decisions API, httpx/openai-compatible dependency check), key `OPENROUTER_API_KEY` from env
- Batched extraction questions and override-when-confident policy in the transcript worker
- Jev noul verdict in `deviation_judge.py` with DeepSeek fallback and DeepSeek summary-only on deviation
- UI "Jev" tag on the summary panel, dev-feed logging
- Tests with mocked Jev, flagged PASS WITH CAVEATS

### Out of scope
- Replacing the DeepSeek `whatHappened` headline or the deviation summary sentence
- Replacing the instant keyword rules (they remain the first answer)
- `score` question type (an 11-level score returned HTTP 400)
- Security review (skipped by the user), rate limiting, prompt-injection hardening
- Any other feature changes

## Business rules
1. Rules answer instantly; Jev only refines afterwards.
2. Jev overrides a rule value only when confident: yes/no probability >= 0.7 or <= 0.3; choice confidence >= 0.7. Uncertain answers leave the rule value.
3. Patients is a choice over 0-10 (with a "nobody hurt" option for 0); 1-10 alone forced a wrong answer on a no-injury call.
4. Departments are three independent yes/no questions (police, emergency medical, fire), because a single "first department" choice cannot fill a multi-department field.
5. Deviation verdict threshold: deviated when P(follows) < 0.3 (constant, tunable). Validated on 8 cases: deviations scored 0.01-0.02, clear follows 0.79-0.90, one correct-but-terse CPR reply scored 0.49-0.51, so 0.5 would have wrongly flagged it.
6. Fallback is silent: extraction keeps rule values; the judge uses DeepSeek for the whole verdict.
7. Jev never writes prose; DeepSeek is still the source of `whatHappened` and `deviationSummary`.

## Security & reliability constraints
Security lens deliberately skipped by the user. Reliability: Jev failures must never break the panel or the Submit flow; timeouts required.

## Technical & integration constraints
1. Endpoint `POST https://openrouter.ai/api/alpha/decisions`, model `typesafe/jev-1.13`, Bearer `OPENROUTER_API_KEY`. Body `{model, state, questions}`. Noul criteria `{true, false}` returns `{noul: 0..1}`; choice criteria `{option: description}` returns `{choice, probabilities, confidence}`.
2. Measured latency: one call with 4 questions about 370-400 ms median; extra questions cost about nothing; occasional outliers up to about 1.2 s. Timeouts: about 1.5 s for extraction, longer (about 3 s) for the judge.
3. The alpha endpoint may change; the client isolates the request/response shapes in one module.
4. Follow existing patterns: `structured_extraction.py`, `deviation_judge.py`, `transcript_worker` cancel-if-newer, `dev_log_payload`, `.source-tag`.
5. Tests use mocks; real Jev behaviour is unverified in CI (PASS WITH CAVEATS per `rules/testing.md`).
6. Throwaway scripts from the design session (weapon, multi-question, patients, verdict) inform choices but are not part of the repo.

## Key decisions made
- Override only when confident; not "always override".
- Threshold 0.3 (changed from the initially proposed 0.5 after the verdict test).
- Attribution: dev feed line plus a small "Jev" tag on the summary panel.
- Verdict test ran before drafting, not as a spike story.

## Deferred / open questions
- Vaguer patient phrasing ("a bunch of people", "several") not yet tested.
- Whether to also run Jev on every partial transcript or throttle (extraction already debounces at the transcript worker).
