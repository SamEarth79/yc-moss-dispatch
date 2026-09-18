# /status

## Position in the framework

A standalone, read-only command. It reports where the whole project stands
by reading `knowledge/state.json` (the single source of truth for progress,
maintained by `/design`, `/implement`, `/implement-epic`, `/pr-create`,
`/pr-review`, and `fix-review.md`). It never writes anything.

## Trigger

`/status` or `/status <feature-folder>`

## What this command does

1. Read `knowledge/state.json`. If it doesn't exist, say so and point the
   user at `/design` (which creates it) — do not create it here.
2. Cross-check state against reality before reporting (state is
   authoritative for intent, but drift happens):
   - For each feature marked with committed stories, confirm the branch
     `feature/<feature-folder>` exists and has commits.
   - For each feature with a PR recorded, confirm via `gh pr view <number>
     --json state,reviewDecision` that the recorded PR state still matches.
   - If state and reality disagree, report both and say which one you'd
     trust — do not silently "fix" state from a read-only command.
3. Report, per feature (or only the named feature if an argument was
   given):
   - Design: `in_progress` / `complete`, and the story count.
   - Stories: a table of story code → status (`pending`, `in_progress`,
     `implemented`, `tested`, `committed`, `skipped`, `failed`) with the
     failing step noted for `failed`.
   - PR: none / open / changes_requested / approved / merged, review
     cycles used (of the 5-cycle cap in `fix-review.md`), and URL.
4. End with the single most useful next action, derived from state — e.g.
   "next: `/resume` (picks up LFC-STORY-002-003 at the test step)" or
   "next: `/design` — everything designed is implemented and merged."

## Output

- A concise status report in conversation. No files written, no state
  mutated.
