# /pr-create

## Position in the framework

The first step of the **PR phase** (`implement.md` step 5), run
automatically after a feature's last story is committed — and also
independently invocable at any time. Either way it is the only place a PR
gets created.

- **Previous step**: the precondition is that one or more story commits
  already exist on `feature/<feature-folder>` (made via
  `commands/commit.md`).
- **This step**: generate technical documentation for the feature, push the
  branch, open a PR (or update the existing one) with a description
  generated from
  `knowledge/implementations/<feature-folder>/implementation-summary.md`,
  then immediately run `commands/pr-review.md` against it.
- **Next step**: within the PR phase, the review's verdict feeds
  `commands/fix-review.md` and then the merge confirmation in
  `implement.md` step 5. Run standalone, it ends after the review — the
  user can invoke `/fix-review <pr-number>` themselves. Merging always
  requires an explicit human yes, wherever it happens.

## Trigger

`/pr-create <feature-folder>`

e.g. `/pr-create LFC-001-user-auth`

## What this command does

1. Confirm `feature/<feature-folder>` exists and has commits ahead of the
   default branch. If there's nothing to PR, tell the user and stop.
   Check `knowledge/state.json` for an existing PR on this feature: if one
   is already `open`/`changes_requested`/`approved`, this run **updates**
   it (push the new commits, refresh the description via `gh pr edit`,
   re-run the review) instead of opening a duplicate; if `merged`, stop
   and tell the user.
2. Read `knowledge/implementations/<feature-folder>/implementation-summary.md`
   in full — this is the source for the PR description, not a re-derivation
   from the diff.
3. Read `knowledge/requirements/<feature-folder>/requirements.md` for the
   feature-level context (what this PR is for, at a glance).
4. Build the PR:
   - **Title**: `<feature-folder>: <short feature description>` (derived
     from the requirements doc), kept under ~70 characters.
   - **Body**: a summary section (what was built, pulled from
     implementation-summary.md, organized per story), and a test plan
     section (pulled from test-results.md — pass/fail status per story).
5. Show the proposed title and body to the user before doing anything.
   Get explicit confirmation — this is a visible, shared-state action.
6. On confirmation, generate documentation before opening the PR:
   - Invoke the `docs-writer` agent (`agents/docs-writer.md`) with
     `architecture.md`, `implementation-summary.md`, `test-results.md`, and
     the actual diff on `feature/<feature-folder>`.
   - It writes `knowledge/documentation/<feature-folder>/technical-doc.md`,
     appends an entry to `knowledge/documentation/CHANGELOG.md`, and
     updates `api-reference.md` / `architecture-overview.md` if applicable
     (creating any of these files if they don't exist yet).
   - Show the user a short summary of which doc files were created or
     updated — no separate confirmation needed here, since it's a side
     effect of the PR creation already confirmed in step 5.
   - Commit these documentation changes onto `feature/<feature-folder>` in
     a dedicated commit: `docs: <feature-folder>`.
7. Push `feature/<feature-folder>` to the remote (`git push -u origin
   feature/<feature-folder>`).
8. Create the PR via `gh pr create` with the confirmed title/body, targeting
   the repo's default branch.
9. Report the PR URL back to the user, and mention what documentation was
   generated. Update `knowledge/state.json`:
   `pr = { "number": <n>, "url": "<url>", "state": "open", "reviewCycles": <unchanged or 0> }`.
10. Immediately run `commands/pr-review.md` against the PR number just
    created — same fresh-agent-with-no-context behavior that command
    defines when run standalone. Do not skip this or fold it into a
    continuation of this command's own context: spawn the `reviewer`
    agent exactly as `pr-review.md` specifies (PR diff, PR description,
    `rules/` only — never this conversation's history or `knowledge/`).
11. Show the user the review's output (inline comment summary + the
    approve/request-changes/comment verdict that was just posted to
    GitHub) in this same conversation.

## Rules

- The confirmation in step 5 is required even when this command runs as
  part of `/implement`'s PR phase — pushing and opening a PR is visible
  shared state. Exception: headless runs (`/resume headless`) may proceed
  without it, per `commands/resume.md`.
- Never merge. This command's job ends at opening/updating the PR and
  posting the automatic review from step 10 — the merge confirmation
  lives in `implement.md` step 5 and always requires an explicit human
  yes.
- The review run in step 10 must follow `pr-review.md`'s own
  context-isolation rule: the `reviewer` agent gets no access to this
  command's conversation, only the PR diff/description/`rules/`.
- If `implementation-summary.md` doesn't exist or is empty (e.g. user ran
  this before implementing anything), stop and tell the user rather than
  generating a placeholder description.
