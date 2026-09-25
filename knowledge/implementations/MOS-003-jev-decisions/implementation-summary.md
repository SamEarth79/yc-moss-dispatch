## MOS-STORY-003-001 - Jev client module: what was tested and why

Tests in backend/test_jev_client.py (asyncio.run + monkeypatch, style of test_deviation_judge.py). `jev_client._get_client` is replaced with a fake whose async `post(path, body=, cast_to=, options=)` captures its arguments, so no network is used. The tests map to the acceptance criteria as follows:
- Missing OPENROUTER_API_KEY returns None from both functions; the client is rebuilt when the key changes.
- Request contract: path /decisions, model typesafe/jev-1.13, per-call timeouts 1.5 s (extraction) and 3.0 s (judge) with max_retries 0.
- Extraction asks the six question ids with correct types; patients is a choice with keys '0'..'10'; state carries caller_transcript.
- Parsed result shape and patients tuple.
- Malformed answers (bad type, out-of-range probability or confidence, bool value, unknown patient choice, non-dict answer) are omitted while the rest are still returned; an empty dict is returned when nothing is usable.
- None on timeout or generic exceptions and when the response has no answers object; CancelledError propagates.
- Logs (caplog) contain no transcript text or API key.
- decide_follows state fields (dispatcher_reason only when given); it returns a float or None.
- Constants 0.7 / 0.3 / 0.3 / 1.5 / 3.0.

Live smoke test (orchestrator, one path): transport and response shape confirmed against real OpenRouter; extraction values were plausible (weapon 0.96, unconscious 0.97, police 0.99, ems 0.99, fire ~0.21-0.24, patients ('2', 0.98)); latency 935 ms cold, ~325-375 ms warm. Automated tests are mock-only, so real Jev accuracy is unverified in CI. Verdict: PASS WITH CAVEATS.

## MOS-STORY-003-002 - Jev deviation verdict: what was tested and why

Tests are in backend/test_deviation_judge.py; an autouse fixture in the new backend/conftest.py stubs decide_follows to return None so pre-existing tests stay offline and deterministic on the DeepSeek fallback path. Mapping to acceptance criteria:
- AC1: P=0.87, exactly 0.3 and grey zone 0.4 return followed with an empty summary and the fake DeepSeek client is never awaited.
- AC2: P=0.01 and 0.29 return deviated; exactly one summary-only call is made with the summary system prompt, the protocol chunk and dispatcher reply (plus reason only when given) in the user message, and no caller transcript. Empty, missing, non-string or non-JSON summaries raise ValueError.
- AC3: Jev None runs the original full path with identical result, prompt and max_tokens; DeepSeek unconfigured after a Jev deviated verdict returns None (endpoint 503 "LLM not configured"). Reason and texts are passed through to decide_follows.
- AC4: endpoint tests through POST /api/deviations/judge show followed writes nothing and deviated writes one doc with the Jev-path summary; response keys are unchanged.
- AC5: caplog shows exactly one info line with source, verdict and p_follows (3 decimals), containing no reply, chunk, transcript or summary text.
- AC6: existing tests unchanged and passing; 172 passed in the full suite.

Live check (orchestrator): follows reply -> Jev P(follows)=0.87 followed; deviating reply "water" -> P=0.01 deviated with summary "Advised water and rest instead of back blows and abdominal thrusts."; latency followed ~0.9 s cold, deviated ~1.75 s (Jev then DeepSeek in sequence). Automated tests are mock-only and only 2 live cases were tried. Verdict: PASS WITH CAVEATS.

## MOS-STORY-003-003 - QA note: what was tested and why

backend/test_jev_merge.py exercises merge_jev_fields as a pure function. It covers the threshold bands (exact 0.7 and 0.3 boundaries, uncertain zone keeps the rule value), field mapping (weapon, unconscious, patients, departments in canonical order), the sources map (only set when a value actually changes), safe handling of None/empty answers, and input immutability. Two realistic scenarios (sample call, no-injury gas leak) guard the end-to-end intent. No network is used. Caveat: the thresholds were validated on few real cases and are unverified at scale.
