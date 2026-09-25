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
