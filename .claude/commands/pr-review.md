# /pr-review

## Position in the framework

Runs inside the PR phase (after `pr-create.md`, and after every
`fix-review.md` cycle) and is also independently invocable. Wherever it is
invoked from, it **never shares context** with the conversation that
produced the code — the `reviewer` agent is spawned fresh, by design.

- **Previous step**: none formal — the precondition is that a PR already
  exists (created via `commands/pr-create.md` or otherwise).
- **This step**: spawn the `reviewer` agent with **no conversation
  history** — only the PR diff and `rules/` — and have it post a review.
- **Next step**: in the PR phase, the verdict feeds `fix-review.md`
  (changes requested → fix loop; approved → merge confirmation in
  `implement.md` step 5). Standalone, nothing runs automatically after it.
  The merge decision always belongs to the user.

## Trigger

`/pr-review <pr-number>`

e.g. `/pr-review 42`

## What this command does

1. Fetch the PR diff and description via `gh pr diff <pr-number>` and
   `gh pr view <pr-number>`.
2. Spawn the `reviewer` agent (`agents/reviewer.md`) as a **fresh agent
   with no prior conversation context**. Pass it only:
   - The PR diff
   - The PR description
   - `rules/coding-style.md`, `rules/security.md`, `rules/testing.md`
   Do not pass it `knowledge/`, the chat history that led to this PR, or any
   other context from this session — the independence is the point.
3. The `reviewer` agent reviews and produces:
   - Inline comments on specific lines for concrete, actionable issues
     (via `gh api repos/.../pulls/.../comments`).
   - One overall verdict, submitted as an actual GitHub PR review (not a
     plain comment) via `gh pr review <pr-number> --approve|
     --request-changes|--comment --body "..."` — so the PR's real review
     state reflects the verdict, not just text saying so.
4. Show the user the same review output directly in this conversation —
   don't make them go read GitHub to see what was found.
5. Record the verdict in `knowledge/state.json` (feature's `pr.state`:
   `approved` or `changes_requested`; a comment-only review leaves the
   state as-is) — when the PR maps to a tracked feature.
6. Stop. This command itself never merges and never pushes fixes. Acting
   on a changes-requested verdict is `commands/fix-review.md`'s job — run
   automatically when inside the PR phase, or via `/fix-review
   <pr-number>` when the user wants it standalone.

## Rules

- The `reviewer` agent must never be given this session's conversation
  history. If the harness/tool used to spawn it would otherwise carry
  context forward, explicitly strip it — the value of this command is an
  independent second opinion, not a continuation of the same reasoning that
  produced the code.
- Never auto-merge, regardless of verdict.
