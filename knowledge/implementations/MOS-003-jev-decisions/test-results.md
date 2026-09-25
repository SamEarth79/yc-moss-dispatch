## MOS-STORY-003-001 - Jev client module

Verdict: PASS WITH CAVEATS

| Layer | Result |
|---|---|
| Unit (backend/test_jev_client.py, mocked at AsyncOpenAI.post boundary) | 42 passed, 0 failed |
| Feature | Covered by the unit layer; the module has no HTTP handler or DB of its own |
| E2E (Playwright) | Skipped: no user-facing surface (backend client module only) |
| Full suite (`cd backend && uv run pytest --ignore=tests/e2e -q`) | 149 passed, 0 failed |

Caveats (external-contract assumption, per rules/testing.md):
- The module was smoke-tested live once by the orchestrator against the real OpenRouter endpoint. Transport and request/response shape were confirmed. Sample-call extraction returned weapon 0.96, unconscious 0.97, police 0.99, ems 0.99, fire ~0.21-0.24, patients ('2', 0.98). The first call took 935 ms cold; later calls took ~325-375 ms. The transport/response-shape assumption is therefore verified for that one path.
- The automated tests are mock-only and never touch the network. Real Jev accuracy is not verified in CI.

## MOS-STORY-003-002 - Jev deviation verdict

Verdict: PASS WITH CAVEATS

| Layer | Result |
|---|---|
| Unit (backend/test_deviation_judge.py, Jev and DeepSeek both mocked) | 20 new passed, 0 failed (followed, deviated, boundary 0.3, 0.29, grey zone 0.4, Jev None fallback, 7 invalid-summary cases, DeepSeek unconfigured, argument pass-through, prompt contents, 3 logging cases) |
| Feature (POST /api/deviations/judge via TestClient, real judge_deviation, patched decide_follows, fake moss_client) | 3 new passed, 0 failed (followed writes nothing; deviated writes one doc with the Jev-path summary and unchanged response keys; deviated with DeepSeek unconfigured returns 503) |
| E2E (Playwright) | Skipped: no user-facing UI change; response contract unchanged |
| Full suite (`cd backend && uv run pytest --ignore=tests/e2e -q`) | 172 passed, 0 failed (was 149) |

Isolation: new backend/conftest.py has an autouse fixture that replaces deviation_judge.decide_follows with an async stub returning None, so existing tests keep exercising the DeepSeek fallback path and never reach the network even if OPENROUTER_API_KEY is exported. New tests override it.

Caveats (external-contract assumption, per rules/testing.md):
- The orchestrator ran one live end-to-end check with real Jev and DeepSeek. A reply that follows the protocol got Jev P(follows)=0.87 -> followed. A deviating reply ("water") got P=0.01 -> deviated with summary "Advised water and rest instead of back blows and abdominal thrusts." Latency: followed ~0.9 s on a cold client; deviated ~1.75 s because Jev and DeepSeek run one after the other.
- The automated tests are mock-only, and only 2 live cases were tried. Real Jev verdict quality, and the 0.3 threshold, are not verified beyond those cases.
