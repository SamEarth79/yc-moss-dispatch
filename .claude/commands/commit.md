# commit.md

## Position in the framework

Step 4 of 5 in the `/implement` workflow, invoked by `commands/implement.md`
(and, per-story, by `commands/implement-batch.md`). This is the last
per-story step; step 5 (the PR phase) runs once per feature, after the
last story commits.

- **Previous step**: `commands/test.md`. This step only runs if `test.md`
  reported all required layers passing. Its output is the test results
  already shown to the user and recorded in
  `knowledge/implementations/<feature-folder>/test-results.md`.
- **This step**: propose a commit message, show it alongside the test
  results, get explicit user confirmation, then commit.
- **Next step**: control returns to `implement.md`'s (or
  `implement-batch.md`'s) closing/looping logic. If this was the feature's
  last remaining story, `implement.md` step 5 (the PR phase) runs next.

## What this command does

1. Assemble the proposed commit message from the combined specialist
   agent reports (from `execute.md`) and the story title:
   `<STORY-CODE>: <short summary>` — e.g.
   `LFC-STORY-001-001: add login form`.
2. Show the user:
   - The proposed commit message.
   - A short recap of the test results (already shown in `test.md`, but
     restate the pass summary here so the confirmation is self-contained).
   - The list of files that will be included in the commit.
3. Ask for explicit confirmation before doing anything. Do not commit
   silently or proceed on an assumed "yes."
4. If confirmed:
   - First tick all three boxes in the story file's `## Status` checklist
     (Implemented / Tested / Committed) so the story file rides along in
     the same commit.
   - Stage exactly the files changed for this story plus that story file
     (not an unrelated `git add -A`).
   - Commit onto `feature/<feature-folder>` with the confirmed message.
   - Confirm the commit succeeded and show the commit hash.
   - Only after the commit verifiably exists (`git log -1`), update
     `knowledge/state.json`: story `status: "committed"`, `step: null`,
     `commit: "<hash>"`.
   - Headless runs (`/resume headless`): the confirmation in step 3 is
     replaced by the rule in `commands/resume.md` — commit automatically,
     but only on a clean `test.md` pass (never on `PASS WITH CAVEATS`).
5. If the user wants changes to the message, update and re-confirm before
   committing.
6. If the user declines to commit at all, stop here — do not commit, and
   tell them the changes remain uncommitted on the working tree.

## Output

- A git commit on `feature/<feature-folder>`, only after explicit user
  confirmation (or the headless clean-pass rule).
- `knowledge/state.json` and the story file's `## Status` checklist updated
  to `committed`.
- Nothing is pushed and no PR is created here — that happens in the PR
  phase (`implement.md` step 5) once the feature's last story is committed.
