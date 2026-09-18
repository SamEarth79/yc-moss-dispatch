# /resume

## Position in the framework

A standalone entry point that continues work from wherever the project last
stopped, using `knowledge/state.json` as the source of truth. It exists so
a session that ended mid-feature (context exhausted, token limit reset,
machine slept, scheduled run) can pick up without the user reconstructing
where things stood. It does no work itself — it dispatches to the same
command files everything else uses.

## Trigger

- `/resume` — interactive resume in a normal session.
- `/resume headless` — non-interactive resume. Same logic, different
  confirmation rules (below). The headless rules defined here are the
  canonical ones — `/implement-epic <feature-id> headless` (what scheduled
  runs execute, via `/schedule-resume`) follows them.

Scope note: `/resume` targets the single next stall point and continues
from it. To implement an entire Epic from where it stopped, use
`/implement-epic <feature-id>` — it is fully state-driven and resumes
naturally.

## What this command does

### 1. Read and verify state

- Read `knowledge/state.json`. If missing or empty, report there is
  nothing to resume and stop.
- Verify state against reality before acting on it (a crashed session can
  leave state behind reality, never ahead of it):
  - If a story is marked `in_progress`, check `git status`/`git diff` on
    `feature/<feature-folder>` for uncommitted work and check
    `knowledge/implementations/<feature-folder>/` for test results already
    recorded for that story. Real work on disk wins over the recorded
    step — resume from the earliest step whose output is missing, not
    blindly from the recorded step.
  - If a story is marked `committed`, confirm the commit actually exists
    (`git log --oneline --grep "<STORY-CODE>:"` on the feature branch). If
    it doesn't, downgrade to the last verifiable status before continuing.

### 2. Pick the resume point (first match wins)

1. A story with status `failed` → surface the recorded failure and ask
   fix / skip / abort, exactly as `test.md` would have. (Headless: skip
   this story, leave it `failed`, move to the next rule.)
2. A story with status `in_progress` → re-enter `/implement` for it at the
   step determined in step 1's verification.
3. A feature with design `complete` and stories still `pending` → run the
   next pending story via the `/implement` steps, respecting each story's
   `Depends on` field.
4. A feature with all stories `committed` but PR state not `merged` → run
   the PR phase (`implement.md` step 5: `pr-create.md` →
   `pr-review.md` → `fix-review.md`).
5. A feature with design `in_progress` → tell the user design is
   unfinished; `/design` is conversational, so it cannot be resumed
   headless — report and stop. (Interactive: offer to reopen `review.md`
   for it.)
6. Nothing matches → report that everything tracked is done and suggest
   `/design` or `/strategize`.

If multiple features match the same rule, take the lowest feature number
first. State the chosen resume point out loud before doing anything.

### 3. Continue until a stopping point

Interactive: keep going story-by-story (same rules as
`/implement-epic`) until done or a confirmation/decision is needed.

Headless (scheduled run) confirmation rules — these deviations from the
interactive defaults are explicit and limited:

- **Commits**: allowed without asking, but only when `test.md` recorded a
  clean pass (not `PASS WITH CAVEATS`) for the story in this run. The
  message format is fixed (`<STORY-CODE>: <short summary>`), so there is
  nothing to negotiate.
- **Test failure / `PASS WITH CAVEATS` / a blocked agent**: do not decide.
  Mark the story `failed` (or leave it `tested` with the caveat recorded),
  write what happened into `state.json`'s `resume.note`, and continue to
  the next independent story if one exists; otherwise stop.
- **PR creation and pushing**: allowed (it's reviewable, reversible
  shared state), including the automatic review and fix-review loop.
- **Merging: never.** No exceptions in headless mode, regardless of an
  approved review.

### 4. End state

Report (or, headless, append to `state.json`'s `resume.note` and print to
stdout for the scheduled run's log): what was resumed, what was completed,
what stopped and why, and the exact next action for the user.
