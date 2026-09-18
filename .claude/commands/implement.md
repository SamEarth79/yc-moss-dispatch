# /implement

## Position in the framework

This is the **entry point and orchestrator** for implementing a single
story. It does not do any work itself — it runs these steps in order, each
defined in its own command file:

1. `commands/plan.md`
2. `commands/execute.md`
3. `commands/test.md`
4. `commands/commit.md`
5. **PR phase** — only when the story just committed was the feature's last
   remaining story: `commands/pr-create.md` → `commands/pr-review.md` →
   `commands/fix-review.md` → merge confirmation.

It reads finalized output from `/design` and writes implementation output.
It does not modify anything under `knowledge/requirements/` except the
story file's own `## Status` checklist (via `commit.md`). It updates
`knowledge/state.json` at every transition per `CLAUDE.md`'s State
tracking section — always after the transition is real on disk, never
before.

## Trigger

`/implement <feature-folder> <story-code>`

e.g. `/implement LFC-001-user-auth LFC-STORY-001-001`

If either argument is missing, ask the user for it before proceeding — do
not guess which feature or story is intended.

## What this command does

### 1. Load context and preflight

- Read `knowledge/requirements/<feature-folder>/stories/<story-code>.md` —
  this is the unit of work. If it doesn't exist, stop and tell the user.
- Check `knowledge/state.json`: if this story is already `committed` or
  `skipped`, say so and stop rather than re-implementing it. If it is
  `in_progress` or `failed`, say what state says and resume from the
  earliest step whose output is missing (verify against `git status`/
  `git diff` and the implementation files — see `commands/resume.md`'s
  verification rules), instead of blindly starting from `plan.md`.
- If the story has a `Depends on` field listing stories not yet
  `committed`, stop and tell the user which dependency is missing.
- Read `knowledge/requirements/<feature-folder>/analysis.md` and
  `architecture.md` in full for surrounding context — `analysis.md` carries
  the security/UX/business constraints the six `design-*` agents surfaced
  during `/design`, not just the technical approach.
- Preflight the environment before spending a story's worth of agent work:
  dependencies installed, the project's test runner actually runs (e.g.
  an empty/filtered test invocation exits cleanly), and — if the story is
  user-facing — Playwright is installed. If preflight fails, surface it
  and stop; don't discover it in `test.md`.
- Ensure `knowledge/implementations/<feature-folder>/` exists; create
  `implementation-summary.md` and `test-results.md` there if they don't
  exist yet (empty files with a top-level heading) — they grow across
  stories, they are not recreated per story.

### 2. Ensure the feature branch exists

- Branch name: `feature/<feature-folder>`.
- If it doesn't exist, create it from the current default branch. If it
  exists, check it out (or confirm it's already checked out).
- All work for this story happens on this branch.
- Record the branch in `state.json` and set the story to `in_progress`,
  `step: plan`.

### 3. Run the steps in order

Update the story's `step` in `state.json` as each step starts.

1. **`plan.md`** — orchestrator agent reads the story, decides which
   specialist agents are needed and in what order, presents the plan to the
   user.
2. **`execute.md`** — runs the planned specialist agents in sequence,
   collects and disk-verifies their change reports.
3. **`test.md`** — `qa` agent writes/runs the three test layers, writes
   results into `knowledge/implementations/<feature-folder>/test-results.md`
   and `implementation-summary.md`, shows results to the user. On pass, set
   the story to `tested`.
   - **On failure**: set the story to `failed` (with the failure recorded
     in `state.json`'s `resume.note`), surface it to the user (which layer,
     which test, the error) and ask: fix, skip, or abort. Do not proceed to
     `commit.md`.
4. **`commit.md`** — only runs if `test.md` passed. Shows the proposed
   commit message and the test results, asks for explicit confirmation,
   commits onto `feature/<feature-folder>` only after the user confirms.
   On success, sets the story to `committed` (with the commit hash) in
   `state.json` and ticks the story file's `## Status` checklist.

### 4. Story end state

Report to the user: story code, pass/fail, whether it was committed, which
stories remain for this feature (from `state.json`), and where the
summary/test-results files live.

### 5. PR phase (last story only)

Runs only when, after step 4, every story of this feature is `committed`
or `skipped` in `state.json` (with at least one committed). If stories
remain, stop here and name the next one. The user can also trigger this
phase directly on an already-complete feature via `/pr-create`.

1. **`pr-create.md`** — generates docs via `docs-writer`, shows the
   proposed PR title/body for confirmation, pushes the branch, opens the PR
   (or updates an existing one). Sets `pr` in `state.json` to
   `{number, url, state: "open"}`.
2. **`pr-review.md`** — fresh-context `reviewer` agent reviews and submits
   a real GitHub review. Record the verdict in `state.json`
   (`approved` / `changes_requested`).
3. **`fix-review.md`** — if changes were requested, run the fix → re-test
   → push → re-review loop, capped at 5 cycles total for this PR. Exits on
   approval, cap, or a blocking question.
4. **Merge confirmation** — once the PR is approved: show the user the PR
   URL, the final verdict, review cycles used, and ask explicitly whether
   to merge (and with which method — default `--squash`). Only on an
   explicit yes, run `gh pr merge` and set `pr.state: "merged"` in
   `state.json`. Any other answer: stop, leaving the approved PR open.
   Headless runs (`/resume headless`) never merge.

### 6. End state

Report: what was implemented, PR URL and state (if the PR phase ran),
review cycles used, and — if not merged — that merging is available with
an explicit confirmation. `/status` will reflect all of it.
