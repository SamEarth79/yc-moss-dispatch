# fix-review.md

## Position in the framework

Step run inside the PR phase of `/implement` / `/implement-epic`
(`implement.md` step 5), immediately after `pr-create.md` has opened (or
updated) the PR and `pr-review.md` has posted the first review. It can also
be invoked standalone as `/fix-review <pr-number>` against an existing PR
with an outstanding changes-requested review.

- **Previous step**: `commands/pr-review.md`. Its output is a submitted
  GitHub review (approve / request-changes / comment) plus inline comments.
- **This step**: if the review requested changes, loop fix → push →
  re-review until approved, capped at **5 cycles**.
- **Next step**: the merge confirmation in `implement.md` step 5 (approval
  reached), or a stop with the situation surfaced (cap reached / blocked).

## The loop

Track the cycle count in `knowledge/state.json` under
`features.<feature-folder>.pr.reviewCycles`. The cap is 5 total review
cycles for the PR's lifetime, not per invocation — a standalone re-run does
not reset the counter.

For each cycle:

1. **Read the verdict** of the latest review (`gh pr view <number> --json
   reviewDecision` plus the review body and inline comments via `gh api`).
   - **Approved** → exit the loop successfully.
   - **Commented only (no blocking verdict)** → treat as approved for loop
     purposes, but list the non-blocking observations to the user so they
     can decide whether any deserve a follow-up story.
   - **Changes requested** → continue to step 2.
2. **Triage the findings.** For each inline comment / blocking item in the
   review body, decide:
   - Actionable within this feature's existing scope → assign it to the
     right specialist agent (`frontend`/`backend`/`infrastructure`), the
     same routing the `orchestrator` uses in `execute.md`.
   - Out of scope (the reviewer is asking for a new capability, not a fix
     to what was built) → do not silently expand scope; record it as a
     candidate follow-up story and reply to that comment explaining it's
     deferred.
   - Reviewer is factually wrong (it happens — the reviewer has no
     `knowledge/` context by design) → do not "fix" correct code to
     appease a review. Reply to the comment with the reasoning, and count
     the item as addressed.
3. **Apply the fixes** via the specialist agents, with the same discipline
   as `execute.md`: agents read `rules/` first, and every agent's claimed
   changes are verified against `git diff` before being trusted.
4. **Re-test.** Run the test layers affected by the fixes plus the full
   existing suite (per `rules/testing.md`). If a fix breaks tests, that is
   a failed cycle step — go back to step 3 within the same cycle; do not
   push red code.
5. **Commit and push.** One commit per cycle:
   `<feature-folder>: address review (round <N>)`. Push to the feature
   branch.
6. **Re-review.** Run `commands/pr-review.md` against the same PR — fresh
   `reviewer` agent, no context from this loop, exactly as that command
   specifies. Increment `reviewCycles` in `state.json`. Return to step 1.

## Exit conditions

- **Approved** (or comment-only): report the verdict, cycles used, and
  hand back to `implement.md` step 5 for the merge confirmation.
- **Cap reached (5 cycles) without approval**: stop. Show the user the
  still-open findings, what was tried across cycles, and ask how to
  proceed (manual fix, override and merge anyway, or park the PR). Never
  loop past the cap "just once more."
- **Blocked** (a finding requires a decision only the user can make — e.g.
  a scope question, an external-contract ambiguity per `rules/testing.md`):
  stop mid-loop and surface it. In headless mode (`/resume headless`),
  record it in `state.json` and stop without deciding.

## Rules

- Never merge from inside this loop — approval only ends the loop; the
  merge confirmation lives in `implement.md` step 5 and always requires an
  explicit human yes.
- Every push in this loop is real shared state: only push after the full
  test suite is green.
- Update `state.json`'s `pr.state` (`changes_requested` / `approved`) and
  `pr.reviewCycles` after every cycle, so `/status` and `/resume` see an
  interrupted loop accurately.
