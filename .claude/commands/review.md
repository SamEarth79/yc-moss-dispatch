# review.md

## Position in the framework

Step 4 of 4 in the `/design` workflow, invoked by `commands/design.md`. This
is the last step — there is no separate finalize step.

- **Previous step**: `commands/draft.md`. Its output is the full set of
  files in `knowledge/requirements/<feature-folder>/`: `gather.md`,
  `analysis.md`, `architecture.md`, `stories/*.md`.
- **This step**: present those files to the user, take feedback, patch in
  place, loop.
- **Next step**: none within `/design`. Once the user stops giving
  feedback, `/design` ends and control returns to `commands/design.md`'s
  closing message. The files as they stand at that point are what
  `/implement` and `/implement-epic` will read.

## What this command does

1. Present a summary of what was drafted: the architecture approach and the
   list of stories (codes + titles). Don't dump full raw file contents
   unprompted — summarize, and let the user ask to see any file in full.
2. Take the user's feedback.
3. Identify exactly which file(s) the feedback affects:
   - Feedback about technical approach/components → `architecture.md`
   - Feedback about what a specific story delivers or its criteria →
     that story's file in `stories/`
   - If feedback changes scope in a way that affects multiple files
     (e.g. a new requirement implies a new story), update all affected
     files together — don't leave them inconsistent.
   - If a story is added or removed during this loop, mirror it in
     `knowledge/state.json` (add a `pending` entry / remove the entry) and
     keep `config.json`'s story counter monotonic — never reuse a story
     number, even for a deleted story. Also update the corresponding Asana
     subtask: create it if added (Notes = the new story file's full
     verbatim body, per `draft.md`'s "Create subtasks" step), complete/
     delete it if removed.
   - If an existing story file's body is patched (not added/removed), also
     push the updated content to its Asana subtask's Notes via
     `asana_update_task`, using the subtask GID from
     `state.json["features"]["<feature-folder>"]["asana"]["stories"]["<STORY-CODE>"]`
     — the subtask must never go stale relative to the story file it
     mirrors.
4. Patch only the affected file(s) in place — do not regenerate unaffected
   files from scratch.
5. Re-summarize the change made and ask if there's more feedback.
6. Repeat from step 2 until the user gives no further feedback or
   indicates they're satisfied.

## Output

- In-place edits to whichever files in
  `knowledge/requirements/<feature-folder>/` the feedback touched.
- Asana subtask updates if stories are added or removed.
- No new "finalized" marker or file — absence of further feedback is the
  end signal.
