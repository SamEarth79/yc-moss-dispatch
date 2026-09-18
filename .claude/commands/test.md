# test.md

## Position in the framework

Step 3 of 5 in the `/implement` workflow, invoked by `commands/implement.md`
(and, per-story, by `commands/implement-batch.md`).

- **Previous step**: `commands/execute.md`. Its output is the combined
  change report (all files touched, across all specialist agents that ran),
  held in conversation context.
- **This step**: the `qa` agent writes and runs the three test layers
  defined in `rules/testing.md`, then records results.
- **Next step**: `commands/commit.md`, but only if this step passes. On
  failure, this step is the end of the line for this `/implement` run —
  control returns to the user for a decision.

## What this command does

1. Spawn/invoke the `qa` agent (`agents/qa.md`) with: the story file (for
   acceptance criteria), the combined change report from `execute.md`, and
   `rules/testing.md`.
2. The `qa` agent determines required layers (unit, feature, E2E) per the
   scoping rules in `rules/testing.md`, writes the tests, and runs them
   plus the existing suite.
3. Append results to:
   - `knowledge/implementations/<feature-folder>/test-results.md` — pass/
     fail counts per layer, failure detail if any, under a heading for this
     story code.
   - `knowledge/implementations/<feature-folder>/implementation-summary.md`
     — a plain-text note (no code) of what was tested and why, under a
     heading for this story code.
4. **Verify the qa agent's claim before trusting it**, per `CLAUDE.md`'s
   "Agent completion verification" rule. A self-reported green run is the
   costliest possible false positive in this pipeline, so:
   - Confirm the claimed test files actually exist on disk and are
     non-stub (they contain assertions tied to the acceptance criteria).
   - Re-run the test command(s) the qa agent says it ran, directly, and
     confirm the pass/fail counts match what was reported.
   - Confirm the appended sections in `test-results.md` /
     `implementation-summary.md` exist and are non-empty.
5. Show the results directly in the conversation — do not just write the
   files silently and assume the user will go read them.
6. **If all required layers pass**: set the story to `tested` in
   `knowledge/state.json` and proceed to `commit.md`. A `PASS WITH
   CAVEATS` (per `rules/testing.md`) also proceeds, but the caveat must be
   restated in `commit.md`'s confirmation — and in headless runs it does
   NOT qualify for auto-commit.
7. **If any layer fails**: stop. Set the story to `failed` in `state.json`
   with the failure summarized in `resume.note`. Tell the user exactly
   which layer, which test, and the error. Ask: fix, skip this story, or
   abort the `/implement` run. Do not auto-retry silently.
   - **The fix path, concretely**: route the failing test output plus the
     relevant change report back to the specialist agent whose code is
     implicated (the orchestrator decides which, as in `execute.md`).
     After the agent's fix is disk-verified, re-run the failed layer
     first, then all required layers plus the existing suite. Cap at 3
     fix attempts per story; after the third failure, stop and hand the
     decision back to the user rather than iterating further.

## Output

- `knowledge/implementations/<feature-folder>/test-results.md` (appended)
- `knowledge/implementations/<feature-folder>/implementation-summary.md`
  (appended)
- Pass/fail verdict, which gates whether `commit.md` runs at all.
- `knowledge/state.json` story status updated to `tested` or `failed`.
