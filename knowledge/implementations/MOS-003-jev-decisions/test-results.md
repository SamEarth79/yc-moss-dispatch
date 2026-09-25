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

## MOS-STORY-003-003 - Merge Jev answers into rule fields

Verdict: PASS WITH CAVEATS

| Layer | Result |
|---|---|
| Unit (backend/test_jev_merge.py, pure function, no network) | 36 passed, 0 failed (yes/no bands with exact 0.7 and 0.3 boundaries and 0.31-0.69 uncertain; weapon->weapons; unconscious->consciousness labels; patients 0.7 boundary, 0.69 ignored, '0' and '10', rule None replaced; departments add/remove/uncertain, canonical order, removal of a rule-added department; sources only on change; None/empty answers give an equal non-identical copy and {}; partial answers; no input mutation; key parity; sample-call and no-injury gas-leak scenarios) |
| Feature | Not applicable: pure function, not yet wired into an endpoint |
| E2E (Playwright) | Skipped: no user-facing UI change |
| Full suite (`cd backend && uv run pytest --ignore=tests/e2e -q`) | 208 passed, 0 failed (was 172) |

Caveats:
- Pure-logic unit tests only. The confidence thresholds (0.7 / 0.3) were validated in the design session on a few real cases and are unverified at scale.

## MOS-STORY-003-004 - Worker integration

Verdict: PASS WITH CAVEATS

| Layer | Result |
|---|---|
| Unit (backend/test_jev_merge.py, jev_confident_fields) | 26 new, all passed (boolean mappings weapon/unconscious with 0.7/0.3 boundaries and 0.31-0.69 uncertain; patients 0.7 boundary, 0.69, None; departments any-of; all-uncertain; full set; None/empty) |
| Feature (backend/test_jev_worker.py, TestClient /ws, fake decide_extraction, mocked Moss and extract_llm_fields) | 23 passed, 0 failed (override as second extraction_update with sources and dev line with latency; unchanged key shape; fallback dev line only; stickiness across transcripts while next Jev call pending; uncertain keeps sticky; newer confident replaces; regression 1: confident agreement on weapons/consciousness/patients/departments clears sticky; regression 2: empty transcript and set_caller reset state and cancel in-flight Jev; cancellation before settle delay (no decide_extraction call); min gap between call starts; whatHappened untouched; protocol/deviation paths unaffected; worker not blocked by slow Jev; clean exit on disconnect with pending Jev) |
| E2E (Playwright) | Skipped: no UI change |
| Full suite (`cd backend && uv run pytest --ignore=tests/e2e -q`) | 257 passed, 0 failed (was 208) |

Caveats:
- Mock-only: a real Jev websocket session was not run by these tests.
- Observation (not an AC failure): when the rule value is None, the dev-feed line reads `weapons: None→yes` (raw None), while the AC example `no→yes` is reproduced only when the rule said False.

Live-run findings (websocket run) and fixes, MOS-STORY-003-004:
- Stale sticky: a sticky Jev override (weapons=False) masked a fresher rule value (weapons=True on "knife") until the next Jev answer. Each override now stores the rule value it was decided against and is applied (and kept) only while the current rule value equals it; otherwise it is dropped. Tests: stale sticky dropped through the worker, sticky still applies when rule unchanged, direct payload test incl. departments.
- Unknown != no: Jev turned a None rule value into a definite "no" (weapons) / "conscious". A confident-False answer now applies only when the rule value is not None; confident-True still applies from None; jev_confident_fields(answers, rule_fields) treats an ignored False as not confident. Dev-feed now renders None as "unknown". Tests updated (merge, worker summary strings) and added.
- Full suite: 268 passed, 0 failed.

## MOS-STORY-003-005: Jev tag in the summary panel

Verdict: PASS WITH CAVEATS

| Layer | Result |
|---|---|
| Unit | Skipped: frontend-only DOM/CSS change, no new pure logic module; behavior covered at E2E |
| Feature | Covered by E2E against the real static files (no separate layer for static UI) |
| E2E (Playwright, `backend/tests/e2e/test_jev_tag.py`, own stub app with /ws pushing extraction_update and recording set_caller) | 18 passed, 0 failed (no tag before override; none for sources {} or absent; tag with exact title/aria-label and LLM tag retained; dots only on Jev rows with hidden "refined by Jev" text; `.kv-row--changed` only on Jev-sourced AND changed rows, not on plain rule change, not on unchanged Jev row; #jevStatus text only for Jev change, not plain change or first render; tag/dots/status cleared on caller change and set_caller sent; reduced motion -> animation-name none, normal motion -> kv-row-flash 0.6s; row and panel heights unchanged with dots/tag; heading text and tag group do not overlap; whatHappened rendered as text) |
| Existing e2e | 93 passed total in tests/e2e (75 pre-existing, all still green) |
| Non-e2e | 268 passed |
| Full suite (`cd backend && uv run pytest -q`) | 361 passed, 0 failed |

Caveats:
- E2E runs against a stub /ws; not verified with real Jev output in a real browser.
- Lavender tag text contrast was computed, not measured by a tool.
- Observation: the initial page render (renderExtraction({})) seeds previous values, so the first extraction_update after load compares against empty values; the "no cue on first render" guarantee is tested for the initial render and for the first render after a caller reset.
