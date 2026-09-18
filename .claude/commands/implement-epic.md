# /implement-epic

## Position in the framework

The **orchestrator for implementing every story in one Epic**. It runs the
exact same steps as `/implement` (`plan.md` → `execute.md` → `test.md` →
`commit.md`) once per story, in dependency order, then the PR phase
(`pr-create.md` → `pr-review.md` → `fix-review.md`) once at the end.

This command is state-driven: if interrupted, re-running it (or letting
`/schedule-resume` fire a headless run) picks up exactly where it stopped.

## Trigger

`/implement-epic <feature-id>`

Where `<feature-id>` is the short Epic identifier, e.g. `LIB-002`. The full
folder name (e.g. `LIB-002-signup`) is resolved automatically. The full
folder name is also accepted if the user types it.

e.g.
```
/implement-epic LIB-002
/implement-epic LIB-002-signup
```

If the argument is missing, ask the user which Epic before proceeding.

## What this command does

### 1. Resolve the feature folder

- Read `knowledge/state.json`. Find the feature whose folder name starts with
  `<feature-id>-` (e.g. `LIB-002-` matches `LIB-002-signup`). If multiple
  match, list them and ask the user to clarify.
- Read `knowledge/config.json` to confirm the prefix.
- The resolved `<feature-folder>` (e.g. `LIB-002-signup`) is used throughout.

### 2. Load and order stories from Asana

The authoritative story list comes from Asana, not just local files. This
ensures the command reflects any story changes made in Asana after design.

1. Look up `state.json["features"]["<feature-folder>"]["asana"]["epicGid"]`.
2. Use the `asana_get_subtasks` MCP tool to fetch all subtasks of the Epic.
3. Build the story list from subtasks:
   - Each subtask name follows the format `<STORY-CODE>: <title>`. Parse the
     story code from the name.
   - Match each story code to its local `.md` file in
     `knowledge/requirements/<feature-folder>/stories/`.
   - If a subtask exists in Asana but has no matching local story file, warn
     the user and skip it (don't fabricate a story file mid-implementation).
   - If a local story file exists but has no matching Asana subtask, treat it
     as an Asana-untracked story — include it in the run (it may have been
     added during `/design`'s review loop before Asana sync caught up) but
     warn the user.
4. Apply ordering:
   - Skip stories already `committed` or `skipped` in `state.json` — tell the
     user upfront which are being skipped and why.
   - For the remaining stories, respect each story file's `Depends on` field:
     never run a story before an uncommitted dependency. If a dependency is
     `skipped`, stop and surface it — skipped dependencies break the chain.
   - Also respect the Asana subtask order (top-to-bottom in the subtask list)
     as a tiebreaker when story files don't specify dependencies.
5. If nothing remains, go straight to step 5 (PR phase) if committed stories
   exist and the PR is not yet `merged`; otherwise report there's nothing to do.

### 3. Ensure the feature branch exists

- Branch name: `feature/<feature-folder>` (e.g. `feature/LIB-002-signup`).
- If it doesn't exist, create it from the default branch and check it out.
- If it exists, check it out.
- Record the branch in `state.json["features"]["<feature-folder>"]["branch"]`
  if not already set.

### 4. Implement stories sequentially

For each remaining story in order:

1. Set `state.json` story status to `in_progress`, step to `plan`.
2. Run `commands/plan.md` for this story.
3. Run `commands/execute.md`.
4. Run `commands/test.md`. Update step to `test` before running.
5. Run `commands/commit.md`. Update step to `commit` before running.
6. On commit: set story status to `committed`, step to `null`, record the
   commit SHA. Also update the matching Asana subtask to mark it complete:
   use `asana_update_task` with `completed: true` on the subtask GID from
   `state.json["features"]["<feature-folder>"]["asana"]["stories"]["<STORY-CODE>"]`.
7. `test.md` and `commit.md` append to the shared files
   `knowledge/implementations/<feature-folder>/test-results.md` and
   `knowledge/implementations/<feature-folder>/implementation-summary.md` —
   these grow across the whole batch, not per story.

**On test failure**: stop the batch at this story (mark it `failed` in
`state.json`). Surface the failure (story code, layer, test output, error) and
ask: fix and retry, skip this story and continue, or abort the batch. If the
user skips, mark it `skipped` in `state.json`; also skip (and tell the user)
any story whose `Depends on` includes this story's code.

**On declined commit**: stop and ask whether to continue to the next story
leaving this one `tested`, or abort.

Only proceed to the next story once the current one is `committed` (or the
user explicitly chose to skip/continue past it).

### 5. PR phase

After the last story, run the PR phase exactly as defined in
`commands/implement.md` step 5:

`pr-create.md` → `pr-review.md` → `fix-review.md` (max 5 cycles) → explicit
merge confirmation.

Skip the PR phase only if no story in the feature was ever committed, or the
feature's `pr.state` is already `merged`.

### 6. End state

Report a summary:
- Stories committed this run vs. skipped vs. failed, with reasons
- PR URL, review verdict, and cycles used (if the PR phase ran)
- Whether the PR was merged
- Anything left needing a human decision

Point to `knowledge/implementations/<feature-folder>/` for full detail.
`/status` reflects everything reported here; `/schedule-resume` can pick up
where this left off if interrupted.

## Resumability contract

Every state transition is written to `state.json` **immediately after** it
happens (not before). An interrupted run leaves `state.json` at the last
completed step. Re-running `/implement-epic <feature-id>` reads that state and continues —
it never redoes work already recorded as `committed`.
